"""Shared state of one export: the analysis, name resolution and call-site indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from spel.scripts.db_export.resolve import GlobalResolver
from spel.scripts.fortran_parser.scope_walk import CallEvent, FunctionRef
from spel.scripts.record_access import AccessMapper

SUBGRID_OF_BOUND = {"begp": "p", "begc": "c", "begl": "l", "begt": "t", "begg": "g"}


@dataclass
class CallInfo:
    ln: int
    position: int  # index among the call events on that line
    name: str
    kind: str  # call | function | type-bound
    passed_object: str
    callee: Optional[object]  # Subroutine or None
    event: object


@dataclass
class ExportContext:
    fut: object
    meta: dict
    srcroot: Path
    resolver: GlobalResolver = field(init=False)
    mapper: AccessMapper = field(init=False)
    _calls: dict = field(default_factory=dict)
    _bindings: dict = field(default_factory=dict)
    _sources: dict = field(default_factory=dict)
    _summary: dict = field(default_factory=dict)

    def __post_init__(self):
        self.mod_dict = self.fut.module_dict
        self.sub_dict = self.fut.subroutine_dict
        self.type_dict = self.fut.type_dict
        self.resolver = GlobalResolver(self.mod_dict, self.sub_dict, self.type_dict)
        self.mapper = AccessMapper(self.sub_dict)
        # library stubs are keyed by bare name in sub_dict: dedupe by id
        self.subs = list({s.id: s for s in self.sub_dict.values()}.values())
        self.subs.sort(key=lambda s: s.id)

    def namelist_names(self) -> set[str]:
        """Names of ELM's namelist variables (cached; empty if the sources are unavailable)."""
        if not hasattr(self, "_nml_names"):
            try:
                from spel.scripts.nml.analyze_namelist import find_all_namelist

                self._nml_names = {k.lower() for k in find_all_namelist()}
            except Exception:
                self._nml_names = set()
            for sub in self.subs:
                for f in getattr(sub, "flat_ifs", []) or []:
                    self._nml_names.update(k.lower() for k in f.nml_vars)
        return self._nml_names

    # --- paths ---
    def rel(self, path) -> str:
        p = Path(path)
        try:
            return str(p.relative_to(self.srcroot))
        except ValueError:
            return str(p)

    def source_lines(self, path) -> Optional[list[str]]:
        p = Path(path)
        if p not in self._sources:
            try:
                self._sources[p] = p.read_text(errors="replace").split("\n")
            except OSError:
                self._sources[p] = None
        return self._sources[p]

    # --- calls ---
    def calls(self, sub) -> list[CallInfo]:
        """Call events of `sub` in source order, with their resolved callees."""
        if sub.id in self._calls:
            return self._calls[sub.id]
        out: list[CallInfo] = []
        rec = sub.record
        if rec is not None:
            per_line: dict[int, int] = {}
            for e in rec.events:
                if isinstance(e, CallEvent):
                    kind = "type-bound" if (e.passed_object or "%" in e.name) else "call"
                    passed = e.object_path or e.passed_object or ""
                elif isinstance(e, FunctionRef) and not e.intrinsic:
                    kind, passed = "function", ""
                else:
                    continue
                pos = per_line.get(e.ln, 0)
                per_line[e.ln] = pos + 1
                callee = self.mapper.callee(sub, rec, e)
                out.append(CallInfo(e.ln, pos, e.name, kind, passed, callee, e))
        self._calls[sub.id] = out
        return out

    def call_for_event(self, sub, event) -> Optional[CallInfo]:
        for c in self.calls(sub):
            if c.event is event:
                return c
        return None

    def call_position(self, sub, ln: int, callee_id: str) -> int:
        """Position of the first call to `callee_id` on line `ln` (0 if unknown)."""
        for c in self.calls(sub):
            if c.ln == ln and c.callee is not None and c.callee.id == callee_id:
                return c.position
        return 0

    def calls_on_line(self, sub, ln: int) -> list[CallInfo]:
        return [c for c in self.calls(sub) if c.ln == ln]

    def bindings(self, sub) -> dict[tuple[int, str], list]:
        """`record_access.bindings` of `sub` grouped by (call line, callee id)."""
        if sub.id not in self._bindings:
            out: dict[tuple[int, str], list] = {}
            maps = sub.record_access
            for b in (maps.bindings if maps is not None else []):
                out.setdefault((b.ln, b.callee), []).append(b)
            self._bindings[sub.id] = out
        return self._bindings[sub.id]


def subgrid_of(var) -> str:
    sg = (getattr(var, "subgrid", "") or "").lower()
    if sg in SUBGRID_OF_BOUND.values():
        return sg
    bounds = (getattr(var, "bounds", "") or "").replace(" ", "").lower()
    first = bounds.split(":")[0].split("%")[-1].split(",")[0]
    return SUBGRID_OF_BOUND.get(first, "")


def to_fortran(val) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return ".true." if val else ".false."
    if isinstance(val, str):
        return val.replace("True", ".true.").replace("False", ".false.")
    return str(val)


def merge_status(a: str, b: str) -> str:
    return "".join(sorted(set(a) | set(b)))


def canonical_summary(ctx: ExportContext, sub, _chain: tuple = ()) -> dict[str, str]:
    """
    Overall status of every module variable `sub` reads or writes, directly or
    through its callees (transitively), keyed by canonical path
    (`module::name%member`). Resolution happens in the scope of the routine
    that names the variable, so callee accesses are attributed correctly.
    """
    if sub.id in ctx._summary:
        return ctx._summary[sub.id]
    out: dict[str, str] = {}
    maps = sub.record_access
    if maps is not None:
        for path, rws in list(maps.elmtype.items()) + list(maps.globals.items()):
            canon = ctx.resolver.canonical(sub, path)
            if canon is None:
                continue
            status = ""
            for rw in rws:
                status = merge_status(status, rw.status)
            for target in ctx.resolver.expand(canon):
                out[target] = merge_status(out.get(target, ""), status)
        for c in ctx.calls(sub):
            callee = c.callee
            if callee is None or callee.library or callee.record is None or callee.id in _chain:
                continue
            for canon, status in canonical_summary(ctx, callee, _chain + (sub.id,)).items():
                out[canon] = merge_status(out.get(canon, ""), status)
    ctx._summary[sub.id] = out
    return out
