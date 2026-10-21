"""
The static time step: a depth-first walk of the call tree from elm_drv in
source order, recording every read/write of a module variable (directly, or
through dummy arguments bound to module variables at the call).

Modeled on spel.transforms.compact.inventory.Tracer, without its index forms.
"""

from __future__ import annotations

from typing import Optional

from spel.scripts.db_export.context import CallInfo, ExportContext
from spel.scripts.db_export.resolve import var_columns
from spel.scripts.fortran_parser.scope_walk import Access, CallEvent, FunctionRef
from spel.scripts.fortran_parser.spel_ast import FuncExpression, Identifier, Node
from spel.scripts.fortran_parser.symbols import Origin
from spel.scripts.nml.namelist_cascade import NML_CASCADES
from spel.scripts.registrations import iter_statements


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
            self.visit(sub, {}, None, (sub.id,), None, None, False)
        return self

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

    def visit(self, sub, env: Env, host_env: Optional[Env], chain: tuple, parent: Optional[int], call, guarded: bool) -> None:
        node = self._node(sub, parent, call, len(chain) - 1)
        node["guarded"] = guarded
        order = node["order"]
        if not node["analyzed"]:
            return
        rec = sub.record
        pending: list[Access] = []
        for e in rec.events:
            if isinstance(e, Access):
                if e.status == "arg":
                    pending.append(e)
                else:
                    self.emit(sub, order, e, e.status, env, host_env, guarded)
            elif isinstance(e, CallEvent) or (isinstance(e, FunctionRef) and not e.intrinsic):
                info = self.ctx.call_for_event(sub, e)
                callee = info.callee if info is not None else None
                arg_paths = {a.path for a in e.args if a.path is not None}
                mine = [p for p in pending if p.ln == e.ln and p.path in arg_paths]
                pending = [p for p in pending if p not in mine]
                analyzed = callee is not None and not callee.library and callee.record is not None
                if not analyzed:
                    # unknown effect on the actuals: read and written (conservative)
                    for a in mine:
                        self.emit(sub, order, a, "rw", env, host_env, guarded)
                    if callee is None:
                        self.unresolved_calls += 1
                    else:
                        self._node(callee, order, info, len(chain))
                    continue
                if callee.id in chain:
                    self._node(callee, order, info, len(chain), cut=True)
                    continue
                cenv = self.callee_env(sub, e, callee, env, host_env)
                if callee.is_internal:
                    chost = env if callee.host_id == sub.id else host_env
                else:
                    chost = None
                self.visit(callee, cenv, chost, chain + (callee.id,), order, info, guarded or self.conditional(sub, e.ln))
        for a in pending:
            self.emit(sub, order, a, "rw", env, host_env, guarded)
        node["size"] = len(self.nodes) - order

    # --- resolution ---
    def resolve(self, sub, path: str, origin: Origin, env: Env, host_env: Optional[Env]) -> frozenset:
        base, _, rest = path.partition("%")
        rest = f"%{rest}" if rest else ""
        if origin in (Origin.GLOBAL, Origin.EXTERNAL):
            canon = self.ctx.resolver.canonical(sub, path)
            return frozenset({canon}) if canon else frozenset()
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

    def emit(self, sub, order: int, access: Access, status: str, env: Env, host_env: Optional[Env], guarded: bool = False) -> None:
        conditional = guarded or self.conditional(sub, access.ln)
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
                    "resolved_from": "global" if access.origin in (Origin.GLOBAL, Origin.EXTERNAL) else "dummy",
                    "conditional": conditional,
                }
                | cols
            )
