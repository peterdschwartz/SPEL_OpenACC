"""
The static time step: a depth-first walk of the call tree from elm_drv in
source order, recording every read/write of a module variable (directly, or
through dummy arguments bound to module variables at the call).

Modeled on spel.transforms.compact.inventory.Tracer; the index form of each
access (spel.transforms.compact.index_forms) gives the filter it runs under,
and assignments into a `clumpfilter` instance are the filter-building sites
that spel.scripts.db_export.filters turns into filter relations.
"""

from __future__ import annotations

from typing import Optional

from spel.scripts.db_export.context import CallInfo, ExportContext
from spel.scripts.db_export.resolve import var_columns
from spel.scripts.fortran_parser.scope_walk import Access, AssignEvent, CallEvent, FunctionRef
from spel.scripts.fortran_parser.spel_ast import FuncExpression, Identifier, Node
from spel.scripts.fortran_parser.symbols import Origin
from spel.scripts.nml.namelist_cascade import NML_CASCADES
from spel.scripts.registrations import iter_statements, line_guards
from spel.transforms.compact.index_forms import IndexContext, IndexForm, callee_context


def expr_names(expr) -> set[str]:
    """Variable names an expression reads (base names; function names excluded)."""
    out: set[str] = set()

    def walk(node):
        if isinstance(node, Identifier):
            out.add(str(node.value).split("%")[0].lower())
            return
        if isinstance(node, FuncExpression):
            for a in node.args or []:
                walk(a)
            return
        if isinstance(node, Node):
            for v in vars(node).values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(expr)
    return out

Env = dict[str, frozenset]  # dummy -> canonical module-variable paths bound to it
FILTER_TYPE = "clumpfilter"


def filter_key(form: IndexForm) -> str:
    """
    The filter(s) an access runs under, from its index form: `filter%lakec` for
    `c = filter_lakec(fc)` with the dummy resolved, several joined by `|`.
    A range or mapping applied to a filter element (`do p = pfti(c), pftf(c)`,
    `c = veg_pp%column(p)`) carries the filter of that element. Empty when the
    index is not drawn from a filter or the filter is unresolved (a local or
    unbound array), i.e. when the access may touch any element.
    """
    if form.kind in ("range", "map", "offset"):
        # the patches of a column drawn from a filter, the column of a patch drawn from one, ...:
        # elements mapped from the filter's elements, which the relations compare across levels
        return filter_key(form.inner) if form.inner is not None else ""
    if form.kind not in ("filter", "block"):
        return ""
    names = sorted(form.filter)
    if not names or any(n.startswith(("dummy:", "local:", "host:")) for n in names):
        return ""
    return "|".join(names)


class StaticTrace:
    def __init__(self, ctx: ExportContext, roots: list[str]):
        self.ctx = ctx
        self.roots = roots
        self.nodes: list[dict] = []
        self.accesses: list[dict] = []
        self.unresolved_calls = 0
        self.unresolved_actuals = 0
        self._seen: set[tuple] = set()
        self._cond_lines: dict[str, set[int]] = {}
        self._guards: dict[str, dict[int, tuple]] = {}
        self.filter_sites: list[dict] = []  # assignments building a filter member, see filter_site()
        self.gate_names: set[str] = set(ctx.namelist_names()) | set(NML_CASCADES)

    def is_gate(self, guard) -> bool:
        """An if whose own condition reads only namelist (or cascade) variables: the configuration decides it."""
        node = getattr(guard, "node", None)
        if node is None:
            return False
        names = expr_names(node)
        return bool(names) and names <= self.gate_names

    def conditional(self, sub, ln: int) -> bool:
        """Line inside an if (select, where) that is not a pure namelist gate."""
        if sub.id not in self._cond_lines:
            lines: set[int] = set()
            tree = sub.record.tree if sub.record is not None else None
            body = getattr(tree, "body", None)
            if body is not None:
                try:
                    for stmt, guards in iter_statements(body):
                        if any(not self.is_gate(g) for g in guards):
                            lines.add(stmt.lineno)
                except Exception:
                    pass
            self._cond_lines[sub.id] = lines
        return ln in self._cond_lines[sub.id]

    def run(self) -> "StaticTrace":
        for root in self.roots:
            sub = self.ctx.sub_dict.get(root)
            if sub is None:
                continue
            self.visit(sub, {}, None, (sub.id,), None, None, False, IndexContext(sub.id, sub.record, {}, {}))
        return self

    def guards(self, sub) -> dict[int, tuple]:
        """line -> the conditions of its enclosing ifs (registrations.Guard, with `negated` for else branches)."""
        if sub.id not in self._guards:
            body = getattr(sub.record.tree, "body", None) if sub.record is not None else None
            try:
                self._guards[sub.id] = line_guards(body) if body is not None else {}
            except Exception:
                self._guards[sub.id] = {}
        return self._guards[sub.id]

    # --- nodes ---
    def _node(self, sub, parent: Optional[int], call: Optional[CallInfo], depth: int, cut=False) -> dict:
        caller = self.nodes[parent]["subroutine"] if parent is not None else ""
        node = {
            "order": len(self.nodes),
            "parent_order": parent if parent is not None else "",
            "caller": caller,
            "call_ln": call.ln if call is not None else "",
            "call_position": call.position if call is not None else "",
            "subroutine": sub.id,
            "depth": depth,
            "size": 1,
            "cut": cut,
            "analyzed": sub.record is not None and not sub.library,
        }
        self.nodes.append(node)
        return node

    def visit(self, sub, env: Env, host_env: Optional[Env], chain: tuple, parent: Optional[int], call, guarded: bool, ictx: IndexContext) -> None:
        node = self._node(sub, parent, call, len(chain) - 1)
        node["guarded"] = guarded
        order = node["order"]
        if not node["analyzed"]:
            return
        rec = sub.record
        pending: list[tuple[int, Access]] = []
        for pos, e in enumerate(rec.events):
            if isinstance(e, Access):
                if e.status == "arg":
                    pending.append((pos, e))
                else:
                    self.emit(sub, order, e, e.status, env, host_env, guarded, ictx.access_form(e, pos))
            elif isinstance(e, AssignEvent):
                self.filter_site(sub, e, pos, env, host_env, ictx)
            elif isinstance(e, CallEvent) or (isinstance(e, FunctionRef) and not e.intrinsic):
                info = self.ctx.call_for_event(sub, e)
                callee = info.callee if info is not None else None
                arg_paths = {a.path for a in e.args if a.path is not None}
                mine = [p for p in pending if p[1].ln == e.ln and p[1].path in arg_paths]
                pending = [p for p in pending if p not in mine]
                analyzed = callee is not None and not callee.library and callee.record is not None
                if not analyzed:
                    # unknown effect on the actuals: read and written (conservative)
                    for pos_a, a in mine:
                        self.emit(sub, order, a, "rw", env, host_env, guarded, ictx.access_form(a, pos_a))
                    if callee is None:
                        self.unresolved_calls += 1
                    else:
                        self._node(callee, order, info, len(chain))
                    continue
                if callee.id in chain:
                    self._node(callee, order, info, len(chain), cut=True)
                    continue
                bindings = self.ctx.bindings(sub).get((e.ln, callee.id), [])
                cenv = self.callee_env(sub, e, callee, env, host_env)
                cictx, _ = callee_context(ictx, bindings, e, callee, pos)
                if callee.is_internal:
                    chost = env if callee.host_id == sub.id else host_env
                else:
                    chost = None
                self.visit(callee, cenv, chost, chain + (callee.id,), order, info, guarded or self.conditional(sub, e.ln), cictx)
        for pos_a, a in pending:
            self.emit(sub, order, a, "rw", env, host_env, guarded, ictx.access_form(a, pos_a))
        node["size"] = len(self.nodes) - order

    def filter_site(self, sub, e: AssignEvent, pos: int, env: Env, host_env: Optional[Env], ictx: IndexContext) -> None:
        """
        `this_filter%lakec(fl) = c` (the lhs resolving to a member of a
        `clumpfilter` instance): record the member, the index variable assigned
        (its level), the filter it is drawn from when the loop runs over one
        (`p = this_filter%nolakeurbanp(fp)`: the parent), and the enclosing
        if conditions, for spel.scripts.db_export.filters.
        """
        lhs = e.lhs
        if not lhs.subscripts or lhs.origin not in (Origin.DUMMY, Origin.GLOBAL, Origin.EXTERNAL, Origin.HOST):
            return
        for canon in self.resolve(sub, lhs.path, lhs.origin, env, host_env):
            info = self.ctx.resolver.describe_canonical(canon)
            dtype = info.get("dtype")
            tname = getattr(dtype, "type_name", None) or (dtype if isinstance(dtype, str) else "")
            member = info.get("member") or ""
            if str(tname).lower() != FILTER_TYPE or not member or member.startswith("num_"):
                continue
            level, parent, domain = "", "", ""
            if isinstance(e.rhs, Identifier) and "%" not in e.rhs.value:
                level = e.rhs.value.lower()
                form = ictx.var_form(level, pos, e.ln, 0)
                if form.kind == "range":
                    domain = f"range:{form.text}"
                elif form.kind in ("filter", "block"):
                    key = filter_key(form)
                    if key and "|" not in key:
                        parent = key.rsplit("%", 1)[-1]
                        domain = f"filter:{parent}"
            self.filter_sites.append({
                "name": member, "instance": canon.split("%")[0], "subroutine": sub.id, "ln": e.ln, "level": level,
                "parent": parent, "domain": domain,
                "guards": tuple(str(g) for g in self.guards(sub).get(e.ln, ())),
            })

    # --- resolution ---
    def resolve(self, sub, path: str, origin: Origin, env: Env, host_env: Optional[Env]) -> frozenset:
        base, _, rest = path.partition("%")
        rest = f"%{rest}" if rest else ""
        if origin in (Origin.GLOBAL, Origin.EXTERNAL):
            canon = self.ctx.resolver.canonical(sub, path)
            return frozenset(self.ctx.resolver.expand(canon)) if canon else frozenset()
        if origin is Origin.DUMMY:
            actuals = env.get(base)
            if actuals is None:
                self.unresolved_actuals += 1
                return frozenset()
            return frozenset(a + rest for a in actuals)
        if origin is Origin.HOST and host_env is not None:
            actuals = host_env.get(base)
            return frozenset(a + rest for a in actuals) if actuals else frozenset()
        return frozenset()

    def callee_env(self, sub, event, callee, env: Env, host_env: Optional[Env]) -> Env:
        out: dict[str, set] = {}
        for b in self.ctx.bindings(sub).get((event.ln, callee.id), []):
            out.setdefault(b.dummy, set()).update(self.resolve(sub, b.actual, b.origin, env, host_env))
        return {k: frozenset(v) for k, v in out.items() if v}

    def emit(self, sub, order: int, access: Access, status: str, env: Env, host_env: Optional[Env], guarded: bool, form: IndexForm) -> None:
        conditional = guarded or self.conditional(sub, access.ln)
        direct = access.origin in (Origin.GLOBAL, Origin.EXTERNAL)
        plain = self.ctx.resolver.canonical(sub, access.path) if direct else None
        for canon in sorted(self.resolve(sub, access.path, access.origin, env, host_env)):
            key = (order, canon, access.ln, status)
            if key in self._seen:
                continue
            self._seen.add(key)
            info = self.ctx.resolver.describe_canonical(canon)
            cols = var_columns(info, canon)
            self.accesses.append(
                {
                    "node_order": order,
                    "status": status,
                    "ln": access.ln,
                    "order": len(self.accesses),
                    "resolved_from": "pointer" if (direct and canon != plain) else ("global" if direct else "dummy"),
                    "conditional": conditional,
                    "index_kind": form.kind,
                    "filter": filter_key(form),
                }
                | cols
            )
