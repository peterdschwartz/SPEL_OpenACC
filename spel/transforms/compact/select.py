"""
The fields of a derived type to compact, and the access sites to rewrite.

A component is selected when, for every instance of the type it is zeroed in:

  * its inventory verdict is `compact` (every access between the zeroing and
    the unpack point gathers from the main filter),
  * it is not a restart variable and nothing accesses it after the unpack
    point (those would need the full layout),
  * every access site can be rewritten: the subscript is the variable `p` of
    ``p = filter_soilp(fp)`` inside a loop ``do fp = 1, num_soilp`` (then
    ``x(p)`` becomes ``x(k0p+fp)``), or the access has no subscripts (a whole
    array passed on, or a dummy bound to an element: the caller's subscript
    is rewritten),
  * every site that touches it touches only selected fields. A routine that
    takes arrays as dummies (CarbonIsoFluxCalc) indexes every array bound to
    a dummy the same way, so all of them must have the compact layout.

Dropping a component can make sites inconsistent for others, so the rules
are applied until nothing changes.

Uses of the selected components in routines the elm_drv trace never visits
(initialization, restart, finalization) are listed for review (`untraced`):
a text search, so it also lists same-named components of other types.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from spel.transforms.compact.inventory import (
    UNPACK_AFTER,
    Entry,
    FieldReport,
    Tracer,
    build_inventory,
    split_window,
)
from spel.transforms.compact.index_forms import MAIN_FILTER


@dataclass
class Site:
    """An access to rewrite: `written(sub0, ...)` -> `written(<k0>+fp, ...)` on line `ln`."""

    sub: str
    ln: int  # 0-based first line of the statement
    path: str
    written: str
    sub0: str
    fp: str
    components: set[str] = field(default_factory=set)


@dataclass
class Polymorphic:
    """
    A routine whose array dummies are bound to selected fields in some calls
    and to full layout arrays in others (CarbonIsoFluxCalc). It gets an
    optional `compact_off` dummy, which the calls with selected fields pass;
    its sites index with ``compact_off + fp`` when it is present.
    """

    sub: str
    dummies: set[str]
    compact_calls: set[tuple[str, int]]  # (caller, 0-based call line)


@dataclass
class Selection:
    dtype: str
    subgrid: str
    instances: list[str]
    components: dict[str, str]  # component -> zeroing class (guard text)
    unpack: dict[str, bool]  # component -> copied to the full layout at the unpack point
    sites: list[Site]
    excluded: dict[str, str]  # component -> reason
    untraced: list[str]
    polymorphic: dict[str, Polymorphic] = field(default_factory=dict)


def rewritable(e: Entry, subgrid: str) -> Optional[str]:
    """None if `e` needs no edit or can be rewritten, else why not."""
    form = e.index
    if not e.sub0:
        return None  # whole array passed on, or a dummy bound to an element
    if form is None or form.kind != "filter" or form.foreign:
        return f"index form {form} at {e.loc}"
    inner = form.inner
    main = MAIN_FILTER[subgrid]
    count = f"filter%num_{main.split('%')[1]}"
    if (
        form.var != e.sub0
        or main not in form.filter
        or inner is None
        or inner.kind != "count"
        or inner.var is None
        or count not in inner.filter
    ):
        return f"subscript {e.sub0} = {form} at {e.loc}"
    return None


def select_fields(fut, dtype_name: str, unpack_after: str = UNPACK_AFTER) -> Selection:
    reports, tracer = build_inventory(fut, types=(dtype_name,), unpack_after=unpack_after)
    dtype = fut.type_dict[dtype_name]
    instances = list(dtype.instances)
    by_comp: dict[str, list[FieldReport]] = defaultdict(list)
    for r in reports:
        by_comp[r.field.split("%")[1]].append(r)
    subgrids = {r.subgrid for r in reports}
    if len(subgrids) != 1 or (subgrid := subgrids.pop()) not in MAIN_FILTER:
        raise ValueError(f"{dtype_name}: fields on subgrids {subgrids}; one of {set(MAIN_FILTER)} expected")

    excluded: dict[str, str] = {}
    chosen: dict[str, str] = {}
    unpack: dict[str, bool] = {}
    for comp, rs in sorted(by_comp.items()):
        if instances[0] not in {r.field.split("%")[0] for r in rs}:
            excluded[comp] = f"not zeroed for {instances[0]}"
        elif bad := [r for r in rs if r.verdict not in ("compact", "unused")]:
            excluded[comp] = f"verdict {bad[0].verdict} for {bad[0].field.split('%')[0]}"
        elif any(r.restart for r in rs):
            excluded[comp] = "restart variable"
        elif any(r.after_unpack for r in rs):
            excluded[comp] = "accessed after the unpack point"
        elif rs[0].rank != 1:
            excluded[comp] = f"rank {rs[0].rank}"
        elif len({r.zero_class for r in rs}) != 1 or '"' in rs[0].zero_class or "'" in rs[0].zero_class:
            excluded[comp] = f"zeroing classes {sorted({r.zero_class for r in rs})}"
        else:
            chosen[comp] = rs[0].zero_class
            unpack[comp] = any(r.history for r in rs)

    by_field: dict[str, list[Entry]] = defaultdict(list)
    for e in tracer.entries:
        by_field[e.field].append(e)

    while True:
        sites, poly, drop = _sites(tracer, by_field, chosen, subgrid, instances)
        if not drop:
            break
        for comp, reason in drop.items():
            chosen.pop(comp, None)
            unpack.pop(comp, None)
            excluded[comp] = reason

    sel = Selection(
        dtype=dtype_name,
        subgrid=subgrid,
        instances=instances,
        components=dict(sorted(chosen.items(), key=lambda kv: (kv[1], kv[0]))),
        unpack=unpack,
        sites=sorted(sites.values(), key=lambda s: (s.sub, s.ln, s.path)),
        excluded=excluded,
        untraced=[],
        polymorphic=poly,
    )
    # a use the trace doesn't see (an unanalyzed routine, a line SPEL comments
    # out) would index the field with the subgrid index: keep it out
    while True:
        uses = untraced_uses(fut, tracer, sel, by_field)
        drop = {comp: f"used outside the trace: {where}" for comp, where, relevant in uses if relevant}
        if not drop:
            break
        for comp, reason in drop.items():
            sel.components.pop(comp, None)
            sel.unpack.pop(comp, None)
            sel.excluded[comp] = reason
        while True:
            sites, poly, drop = _sites(tracer, by_field, sel.components, subgrid, instances)
            if not drop:
                break
            for comp, reason in drop.items():
                sel.components.pop(comp, None)
                sel.unpack.pop(comp, None)
                sel.excluded[comp] = reason
        sel.sites = sorted(sites.values(), key=lambda s: (s.sub, s.ln, s.path))
        sel.polymorphic = poly
    sel.untraced = [f"{where}{'' if relevant else '  (another type)'}" for _, where, relevant in uses]
    return sel


def _sites(tracer: Tracer, by_field, chosen, subgrid, instances):
    sites: dict[tuple, Site] = {}
    drop: dict[str, str] = {}
    for t, es in by_field.items():
        inst, comp = t.split("%")
        if comp not in chosen or not any(e.zero for e in es):
            continue
        window, _ = split_window(es, tracer.unpack_ln, passes=True)
        for e in window:
            if e.cls == "zero":
                continue
            if (why := rewritable(e, subgrid)) is not None:
                drop.setdefault(comp, why)
                continue
            if not e.sub0:
                continue
            fp = e.index.inner.var
            site = sites.get(e.site)
            if site is None:
                site = sites[e.site] = Site(e.sub, e.ln, e.path, e.written, e.sub0, fp)
            elif (site.sub0, site.fp) != (e.sub0, fp):
                drop.setdefault(comp, f"site {e.loc} indexed differently in different visits")
            site.components.add(comp)
    def selected(path: str) -> bool:
        parts = path.split("%")
        return parts[0] in instances and len(parts) > 1 and parts[1] in chosen

    # a site bound to anything but selected fields keeps the full layout,
    # unless its routine can take both layouts (Polymorphic)
    mixed: dict[str, list[Site]] = defaultdict(list)
    for key, site in sites.items():
        targets = tracer.site_targets.get(key)
        if targets and not all(selected(p) for p in targets):
            mixed[site.sub].append(site)
    poly: dict[str, Polymorphic] = {}
    for sub_id, msites in mixed.items():
        rsites = [s for s in sites.values() if s.sub == sub_id]
        dummies = {s.path.split("%")[0] for s in rsites}
        why = None
        if any(tracer.site_targets.get((s.sub, s.ln, s.path)) is None for s in rsites):
            why = "also indexes global fields"
        compact_calls: set[tuple[str, int]] = set()
        for caller, ln, env in tracer.calls.get(sub_id, []) if why is None else []:
            targets = [p for d in dummies for p in env.get(d, ())]
            flags = {selected(p) for p in targets}
            if flags == {True}:
                compact_calls.add((caller, ln))
            elif flags == {True, False}:
                where = f"{caller}@{ln + 1}"
                for p in targets:
                    if selected(p):
                        drop.setdefault(p.split("%")[1], f"call {where} mixes layouts in {sub_id}")
        if why is not None:
            for s in msites:
                for comp in s.components:
                    drop.setdefault(comp, f"site {s.sub}@{s.ln + 1} {why}")
        else:
            poly[sub_id] = Polymorphic(sub_id, dummies, compact_calls)
    return sites, poly, drop


def _code(line: str) -> str:
    return line.split("!")[0].rstrip()


def statement_start(lines: list[str], ln: int) -> int:
    """
    First line of the statement that line `ln` belongs to. Blank and comment
    lines may sit between continuation lines.
    """
    start = ln
    i = ln - 1
    while i >= 0:
        code = _code(lines[i])
        if not code.strip():
            i -= 1
            continue
        if not code.endswith("&"):
            break
        start = i
        i -= 1
    return start


def statement_end(lines: list[str], ln: int) -> int:
    """Last line of the statement starting on line `ln`."""
    end = ln
    while _code(lines[end]).endswith("&"):
        i = end + 1
        while i < len(lines) and not _code(lines[i]).strip():
            i += 1
        if i >= len(lines):
            break
        end = i
    return end


def untraced_uses(fut, tracer: Tracer, sel: Selection, by_field) -> list[tuple[str, str, bool]]:
    """
    (component, file:line routine: text, relevant) for every use of a selected
    component outside the trace. Relevant: it names an instance of the type
    (`veg_pf%x`), or `this%x` in the type's module; else it is likely a
    same-named component of another type (a text search).
    """
    if not sel.components:
        return []
    handled = {
        sid for key in ("init", "setvalues", "clean")
        if isinstance(sid := fut.type_dict[sel.dtype].procedures.get(key), str)
    }
    traced_lines: dict[str, set[int]] = defaultdict(set)
    for es in by_field.values():
        for e in es:
            traced_lines[e.sub].add(e.ln)
    # associate statements of traced routines (selectors are not accesses)
    for sub_id in tracer.visited:
        rec = fut.subroutine_dict[sub_id].record
        traced_lines[sub_id].update(f.start_ln for f in rec.frames)
    by_file: dict[str, list] = defaultdict(list)
    for sub in fut.subroutine_dict.values():
        if sub.filepath:
            by_file[str(sub.filepath)].append(sub)
    pattern = re.compile(
        r"%\s*(" + "|".join(sorted(map(re.escape, sel.components))) + r")\b", re.IGNORECASE
    )
    srcroot = Path(fut.subroutine_dict[next(iter(handled))].filepath).parents[1]
    type_file = Path(fut.subroutine_dict[next(iter(handled))].filepath)
    insts = "|".join(sorted(map(re.escape, sel.instances)))
    out = []
    for path in sorted(srcroot.rglob("*.F90")):
        if "external_models" in path.parts:
            continue
        lines = path.read_text(errors="replace").split("\n")
        subs = by_file.get(str(path), [])
        for ln, line in enumerate(lines):
            code = line.split("!")[0]
            m = pattern.search(code)
            if m is None:
                continue
            owner = min(
                (s for s in subs if s.startline <= ln <= s.endline),
                key=lambda s: s.endline - s.startline,
                default=None,
            )
            start = statement_start(lines, ln)
            if owner is not None and (owner.id in handled or start in traced_lines.get(owner.id, ())):
                continue
            where = owner.id if owner is not None else "(no analyzed routine)"
            text = f"{path.relative_to(srcroot)}:{ln + 1} {where}: {line.strip()[:100]}"
            for m in pattern.finditer(code):
                comp = m.group(1).lower()
                before = code[: m.start()]
                relevant = bool(re.search(rf"\b({insts})\s*$", before, re.IGNORECASE)) or (
                    path == type_file and bool(re.search(r"\bthis\s*$", before, re.IGNORECASE))
                )
                out.append((comp, text, relevant))
    return out
