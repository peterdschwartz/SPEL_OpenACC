"""
Field inventory for a compact subgrid layout.

For every component of the target types that the per-step zeroing
(`SetValues` called from EcosystemDynNoLeaching1) resets, report:

  * its zeroing class: the conditions guarding the zeroing in SetValues
  * every access in one time step, in elm_drv call order: routine, line,
    status, the elm_drv call it happens under, and the form of its subgrid
    subscript (see index_forms)
  * whether its value lives across steps: read before the zeroing (by the
    previous step's value), or registered for history or restart. Such a
    field needs its compact values unpacked into the full-layout
    (bookkeeping) copy at the unpack point.
  * a verdict for the window between the zeroing and the unpack point, the
    accesses that would use the compact layout: they can use the compact
    index directly, need maps, or block compaction. Accesses after the unpack
    point read the bookkeeping copy and are only listed.

The trace is static: every branch is taken, every call is followed with its
callee's dummies bound to the caller's actuals (so `this%x` in a type-bound
procedure is `veg_cf%x`). Accesses through history/restart pointers are not
in it; registrations cover them.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from spel.scripts.fortran_parser.scope_walk import (
    Access,
    CallEvent,
    FunctionRef,
    SubroutineRecord,
)
from spel.scripts.fortran_parser.symbols import Origin
from spel.scripts.record_access import AccessMapper
from spel.transforms.compact.index_forms import (
    IndexContext,
    IndexForm,
    compaction_class,
)
from spel.transforms.compact.registrations import (
    Registration,
    line_guards,
    parse_routine,
    registrations,
)

DRIVER_ID = "elm_driver::elm_drv"
ZERO_CALLER = "ecosystemdynmod::ecosystemdynnoleaching1"
UNPACK_AFTER = "ecosystemdynleaching"
FLUX_TYPES = (
    "vegetation_carbon_flux",
    "vegetation_nitrogen_flux",
    "vegetation_phosphorus_flux",
    "column_carbon_flux",
    "column_nitrogen_flux",
    "column_phosphorus_flux",
)
SUBGRID_OF_BOUND = {"begp": "p", "begc": "c", "begl": "l", "begt": "t", "begg": "g"}
# compaction classes that don't need anything beyond the compact index
DIRECT = {"main", "zero"}


@dataclass
class Entry:
    """One access to a target field in the step trace."""

    order: int
    field: str  # instance%component
    status: str  # r | w | pass (actual argument to an analyzed callee) | arg? (unknown callee)
    sub: str
    ln: int  # 0-based
    top: str  # the elm_drv call it is under, name@line (1-based)
    top_ln: int  # 0-based line of that call in elm_drv (-1 in elm_drv itself)
    form: str
    cls: str  # compaction class of the form ("zero" for SetValues writes)
    guards: tuple[str, ...]
    zero: bool = False  # written by the per-step zeroing
    path: str = ""  # the access's path in its routine (associate names expanded, unresolved)
    written: str = ""  # the designator as written (associate name or path), no subscripts
    sub0: str = ""  # its first subscript, as source text
    index: Optional[IndexForm] = field(default=None, repr=False, compare=False)

    @property
    def site(self) -> tuple[str, int, str]:
        return (self.sub, self.ln, self.path)

    @property
    def loc(self) -> str:
        return f"{self.sub}@{self.ln + 1}"


@dataclass
class FieldReport:
    field: str
    type: str
    subgrid: str
    rank: int
    bounds: str
    zero_class: str = ""
    verdict: str = ""
    reasons: list[str] = field(default_factory=list)
    lives_across_steps: bool = False
    read_before_zero: list[str] = field(default_factory=list)
    written_before_zero: list[str] = field(default_factory=list)
    first_after_zero: str = ""
    history: list[str] = field(default_factory=list)
    restart: list[str] = field(default_factory=list)
    classes: dict[str, int] = field(default_factory=dict)
    # routine -> ["status line form", ...], window between zeroing and unpack
    users: dict[str, list[str]] = field(default_factory=dict)
    # routine -> ["status line", ...], after the unpack point (bookkeeping copy)
    after_unpack: dict[str, list[str]] = field(default_factory=dict)


class Tracer:
    """Static, in-order trace of the accesses to `instances` from elm_drv."""

    def __init__(
        self,
        sub_dict: dict,
        type_dict: dict,
        instances: dict[str, str],
        zero_procs: set[str],
    ):
        self.sub_dict = sub_dict
        self.type_dict = type_dict
        self.instances = instances  # instance -> type name
        self.zero_procs = zero_procs
        self.components: dict[str, tuple[str, int, str]] = {}  # field -> (subgrid, rank, bounds)
        self.mapper = AccessMapper(sub_dict)
        self.entries: list[Entry] = []
        self.unwalked: set[str] = set()
        self._guards: dict[str, dict[int, tuple[str, ...]]] = {}
        self._bindings: dict[str, dict[tuple[int, str], list]] = {}
        self.visits = 0
        self.visited: set[str] = set()
        # (routine, line, path) -> every path it resolved to, in any visit
        self.site_targets: dict[tuple[str, int, str], set[str]] = {}
        # callee -> (caller, call line, dummy -> resolved actuals) of every call followed
        self.calls: dict[str, list[tuple[str, int, dict[str, frozenset]]]] = {}

    def run(self) -> list[Entry]:
        drv = self.sub_dict[DRIVER_ID]
        self.visit(drv, IndexContext(drv.id, drv.record, {}, {}), (DRIVER_ID,), "", -1)
        return self.entries

    # --- per-routine caches ---
    def guards(self, sub, rec: SubroutineRecord) -> dict[int, tuple[str, ...]]:
        if sub.id not in self._guards:
            self._guards[sub.id] = line_guards(rec.tree.body)
        return self._guards[sub.id]

    def bindings(self, sub) -> dict[tuple[int, str], list]:
        if sub.id not in self._bindings:
            out: dict[tuple[int, str], list] = {}
            maps = sub.record_access
            for b in maps.bindings if maps is not None else []:
                out.setdefault((b.ln, b.callee), []).append(b)
            self._bindings[sub.id] = out
        return self._bindings[sub.id]

    # --- walk ---
    def target(self, path: str) -> Optional[str]:
        parts = path.split("%")
        if len(parts) >= 2 and parts[0] in self.instances:
            return f"{parts[0]}%{parts[1]}"
        return None

    def visit(self, sub, ctx: IndexContext, chain: tuple[str, ...], top: str, top_ln: int) -> None:
        self.visits += 1
        self.visited.add(sub.id)
        rec = ctx.rec
        guards = self.guards(sub, rec)
        zeroing = sub.id in self.zero_procs and ZERO_CALLER in chain
        here = dict(guards=guards, top=top, top_ln=top_ln, zeroing=zeroing)
        pending: list[tuple[int, Access, str]] = []
        for pos, e in enumerate(rec.events):
            if isinstance(e, Access):
                resolved = ctx.resolve(e.path, e.origin)
                if e.origin is not Origin.GLOBAL:
                    self.site_targets.setdefault((sub.id, e.ln, e.path), set()).update(resolved)
                for path in resolved:
                    t = self.target(path)
                    if t is None:
                        continue
                    if e.status == "arg":
                        pending.append((pos, e, t))
                    else:
                        self.emit(ctx, pos, e, t, e.status, **here)
            elif isinstance(e, CallEvent) or (isinstance(e, FunctionRef) and not e.intrinsic):
                callee = self.mapper.callee(sub, rec, e)
                arg_paths = {a.path for a in e.args if a.path is not None}
                mine = [p for p in pending if p[1].ln == e.ln and p[1].path in arg_paths]
                pending = [p for p in pending if p not in mine]
                analyzed = callee is not None and not callee.library and callee.record is not None
                for pos_a, a, t in mine:
                    self.emit(ctx, pos_a, a, t, "pass" if analyzed else "arg?", **here)
                if not analyzed:
                    if callee is not None:
                        self.unwalked.add(callee.id)
                    continue
                if callee.id in chain:
                    continue
                cctx = self.callee_context(ctx, sub, e, callee, pos)
                if top:
                    ctop, ctop_ln = top, top_ln
                else:
                    ctop, ctop_ln = f"{callee.name}@{e.ln + 1}", e.ln
                self.visit(callee, cctx, chain + (callee.id,), ctop, ctop_ln)
        for pos_a, a, t in pending:
            self.emit(ctx, pos_a, a, t, "arg?", **here)

    def callee_context(self, ctx: IndexContext, sub, event, callee, pos: int) -> IndexContext:
        """The callee's dummies bound to this call's actuals."""
        env: dict[str, set] = {}
        idx_env: dict[str, IndexForm] = {}
        inherit: dict[str, IndexForm] = {}
        rec = ctx.rec
        # the access of each designator actual, by path (subscripts kept)
        actual_access: dict[str, tuple[int, Access]] = {}
        for p in range(pos - 1, -1, -1):
            e = rec.events[p]
            if isinstance(e, Access) and e.ln == event.ln:
                if e.status == "arg":
                    actual_access.setdefault(e.path, (p, e))
            elif getattr(e, "ln", event.ln) != event.ln:
                break
        for b in self.bindings(sub).get((event.ln, callee.id), []):
            env.setdefault(b.dummy, set()).update(ctx.resolve(b.actual, b.origin))
            if (hit := actual_access.get(b.actual)) is not None and ctx.fixes_subgrid(hit[1]):
                inherit[b.dummy] = ctx.access_form(hit[1], hit[0])
            if "%" not in b.actual and b.origin in (Origin.LOCAL, Origin.DUMMY):
                d = rec.declaration(b.actual)
                if d is not None and d.dim == 0 and d.type.lower().startswith("integer"):
                    form = ctx.var_form(b.actual, pos, event.ln, 0)
                    if form.kind != "unknown":
                        idx_env[b.dummy] = form
        self.calls.setdefault(callee.id, []).append(
            (sub.id, event.ln, {k: frozenset(v) for k, v in env.items()})
        )
        host = None
        if callee.is_internal:
            host = ctx if callee.host_id == sub.id else ctx.host
        return IndexContext(
            callee.id,
            callee.record,
            {k: frozenset(v) for k, v in env.items()},
            idx_env,
            inherit,
            host,
        )

    def emit(self, ctx, pos, access, t, status, guards, top, top_ln, zeroing) -> None:
        subgrid = self.component(t)[0]
        form = ctx.access_form(access, pos)
        is_zero_proc = ctx.sub_id in self.zero_procs and status == "w"
        self.entries.append(
            Entry(
                order=len(self.entries),
                field=t,
                status=status,
                sub=ctx.sub_id,
                ln=access.ln,
                top=top,
                top_ln=top_ln,
                form=str(form),
                cls="zero" if is_zero_proc else compaction_class(form, subgrid),
                guards=guards.get(access.ln, ()),
                zero=zeroing and is_zero_proc,
                path=access.path,
                written=written_name(ctx.rec, access),
                sub0=access.subs[0] if access.subscripts else "",
                index=form,
            )
        )

    def component(self, t: str) -> tuple[str, int, str]:
        if t not in self.components:
            inst, comp = t.split("%")
            self.components[t] = component_info(self.type_dict[self.instances[inst]], comp)
        return self.components[t]


def written_name(rec: SubroutineRecord, access: Access) -> str:
    """The designator of `access` as written: its associate name plus the rest of the path."""
    if access.via is None:
        return access.path
    target = rec.associations(access.ln).get(access.via) or ""
    return access.via + access.path[len(target):]


def component_info(dtype, comp: str) -> tuple[str, int, str]:
    v = dtype.components.get(comp)
    if v is None:
        return "?", 0, ""
    bounds = (v.bounds or "").replace(" ", "").lower()
    first = bounds.split(":")[0].split("%")[-1]
    return SUBGRID_OF_BOUND.get(first, "?"), v.dim, bounds


def type_registrations(sub_dict: dict, dtype) -> list[Registration]:
    out: list[Registration] = []
    for key in ("init", "restart"):
        sub_id = dtype.procedures.get(key)
        sub = sub_dict.get(sub_id) if isinstance(sub_id, str) else None
        if sub is None:
            continue
        tree = parse_routine(sub.filepath, sub.startline, sub.endline)
        out.extend(registrations(tree))
    return out


def unpack_line(sub_dict: dict, name: str) -> int:
    """0-based line of the last elm_drv call to `name`."""
    lines = [c.ln for c in sub_dict[DRIVER_ID].record.calls if c.name.lower() == name.lower()]
    if not lines:
        raise ValueError(f"elm_drv has no call to {name}")
    return max(lines)


def build_inventory(
    fut,
    types=FLUX_TYPES,
    instances: Optional[list[str]] = None,
    unpack_after: str = UNPACK_AFTER,
):
    sub_dict = fut.subroutine_dict
    type_dict = fut.type_dict
    inst_type: dict[str, str] = {}
    zero_procs: set[str] = set()
    for tname in types:
        dtype = type_dict[tname]
        for inst in dtype.instances:
            if instances is None or inst in instances:
                inst_type[inst] = tname
        if isinstance(sid := dtype.procedures.get("setvalues"), str):
            zero_procs.add(sid)

    tracer = Tracer(sub_dict, type_dict, inst_type, zero_procs)
    entries = tracer.run()
    unpack_ln = unpack_line(sub_dict, unpack_after)

    regs = {t: type_registrations(sub_dict, type_dict[t]) for t in types}

    by_field: dict[str, list[Entry]] = {}
    for e in entries:
        by_field.setdefault(e.field, []).append(e)

    tracer.unpack_ln = unpack_ln
    reports: list[FieldReport] = []
    for t, es in sorted(by_field.items()):
        if not any(e.zero for e in es):
            continue
        inst, comp = t.split("%")
        tname = inst_type[inst]
        sg, rank, bounds = tracer.component(t)
        r = FieldReport(field=t, type=tname, subgrid=sg, rank=rank, bounds=bounds)
        fill_report(r, es, [g for g in regs[tname] if g.field == comp and g.applies_to(inst)], unpack_ln)
        reports.append(r)
    return reports, tracer


def split_window(
    es: list[Entry], unpack_ln: int, passes: bool = False
) -> tuple[list[Entry], list[Entry]]:
    """
    A field's accesses after its last per-step zeroing (actual arguments to
    analyzed callees only if `passes`): those up to the unpack point (the
    window) and those after it.
    """
    zn = max(e.order for e in es if e.zero)
    after = [
        e for e in es if e.order > zn and not e.zero and (passes or e.status != "pass")
    ]
    return [e for e in after if e.top_ln <= unpack_ln], [e for e in after if e.top_ln > unpack_ln]


def fill_report(r: FieldReport, es: list[Entry], regs: list[Registration], unpack_ln: int) -> None:
    zeros = [e for e in es if e.zero]
    z0 = zeros[0].order
    r.zero_class = " & ".join(zeros[0].guards) or "always"

    written = False
    for e in es:
        if e.order >= z0:
            break
        if e.status == "pass":
            continue
        loc = f"{e.loc} ({e.top})"
        if e.status != "w" and not written and loc not in r.read_before_zero:
            r.read_before_zero.append(loc)
        if e.status == "w":
            written = True
            if loc not in r.written_before_zero:
                r.written_before_zero.append(loc)

    for reg in regs:
        label = f"{reg.name}{' (inactive)' if reg.inactive else ''}"
        target = r.history if reg.kind == "hist" else r.restart
        if label not in target:
            target.append(label)

    window, later = split_window(es, unpack_ln)
    if (uses := [e for e in window if e.cls != "zero"]):
        f = uses[0]
        g = f" if {' & '.join(f.guards)}" if f.guards else ""
        r.first_after_zero = f"{f.status} {f.loc}{g}"
    for e in window:
        use = f"{e.status} {e.ln + 1} {e.form}"
        if use not in (uses := r.users.setdefault(e.sub, [])):
            uses.append(use)
    for e in later:
        use = f"{e.status} {e.ln + 1}"
        if use not in (uses := r.after_unpack.setdefault(e.sub, [])):
            uses.append(use)
    r.classes = dict(Counter(e.cls for e in window))

    r.lives_across_steps = bool(r.read_before_zero or r.history or r.restart)
    classes = set(r.classes)
    if not window and not later and not r.read_before_zero:
        r.verdict = "unused"
        r.reasons.append("zeroed but not accessed in the step")
    elif classes <= DIRECT:
        r.verdict = "compact"
    elif all(c in DIRECT or c == "map" or c.startswith("subset:") for c in classes):
        r.verdict = "compact+maps"
    else:
        r.verdict = "blocked"
        for c in sorted(classes):
            if c in DIRECT or c == "map" or c.startswith("subset:"):
                continue
            where = sorted({e.sub for e in window if e.cls == c})
            r.reasons.append(f"{c}: {', '.join(where)}")


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def summary(reports: list[FieldReport]) -> str:
    out = []
    by_inst: dict[str, list[FieldReport]] = {}
    for r in reports:
        by_inst.setdefault(r.field.split("%")[0], []).append(r)
    out.append(
        f"{'instance':14s} {'fields':>6s} {'compact':>8s} {'+maps':>6s} {'blocked':>8s}"
        f" {'unused':>7s} {'unpack':>7s} {'w-first':>8s}"
    )
    for inst, rs in sorted(by_inst.items()):
        c = Counter(r.verdict for r in rs)
        unpack = sum(r.lives_across_steps for r in rs)
        wfirst = sum(r.first_after_zero.startswith("w ") for r in rs)
        out.append(
            f"{inst:14s} {len(rs):6d} {c['compact']:8d} {c['compact+maps']:6d} "
            f"{c['blocked']:8d} {c['unused']:7d} {unpack:7d} {wfirst:8d}"
        )
    blockers: Counter = Counter()
    for r in reports:
        for reason in r.reasons:
            cls, _, subs = reason.partition(": ")
            for s in subs.split(", "):
                blockers[(cls, s)] += 1
    if blockers:
        out.append("\nblocking accesses (class, routine: fields):")
        for (cls, s), n in blockers.most_common():
            out.append(f"  {cls:28s} {s:60s} {n}")
    return "\n".join(out)


def detail(r: FieldReport) -> str:
    lines = [
        f"{r.field}  ({r.type}, subgrid {r.subgrid}, rank {r.rank}, bounds {r.bounds})",
        f"  verdict            : {r.verdict}" + (f"  [{'; '.join(r.reasons)}]" if r.reasons else ""),
        f"  zeroed             : {r.zero_class}",
        f"  first after zero   : {r.first_after_zero or '-'}",
        f"  lives across steps : {r.lives_across_steps}",
    ]
    if r.read_before_zero:
        lines.append(f"  read before zero   : {', '.join(r.read_before_zero)}")
    if r.written_before_zero:
        lines.append(f"  written before zero: {', '.join(r.written_before_zero)}")
    if r.history:
        lines.append(f"  history            : {', '.join(r.history)}")
    if r.restart:
        lines.append(f"  restart            : {', '.join(r.restart)}")
    lines.append(f"  classes            : {r.classes}")
    lines.append("  between zeroing and unpack:")
    for sub, uses in r.users.items():
        lines.append(f"    {sub}")
        lines.extend(f"        {u}" for u in uses)
    if r.after_unpack:
        lines.append("  after unpack (bookkeeping copy):")
        for sub, uses in r.after_unpack.items():
            lines.append(f"    {sub}: {', '.join(uses)}")
    return "\n".join(lines)


def write_json(reports: list[FieldReport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in reports], indent=1))
