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
from spel.transforms.compact.holders import Holder, find_holder, srcroot_of
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
    holder: Optional[Holder] = None  # the type and where its instances live (see holders.py)


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
    holder = find_holder(fut, dtype_name)
    reports, tracer = build_inventory(fut, types=(dtype_name,), unpack_after=unpack_after)
    dtype = fut.type_dict[dtype_name]
    instances = holder.instances
    excluded: dict[str, str] = {}
    by_comp: dict[str, list[FieldReport]] = defaultdict(list)
    for r in reports:
        hit = holder.split(r.field)
        if hit is None:
            continue  # a field of the instance outside this holder (concrete-only, or another holder)
        _, comp = hit
        if not holder.embedded and "%" in comp:
            # a field of a holder the type embeds (its nutrient core or a role component)
            head = comp.split("%")[0]
            ctype = dtype.components[head].type if head in dtype.components else "?"
            excluded[comp] = f"lives on {ctype}: pass --type {ctype}"
            continue
        by_comp[comp].append(r)
    subgrids = {r.subgrid for rs in by_comp.values() for r in rs}
    if len(subgrids) != 1 or (subgrid := subgrids.pop()) not in MAIN_FILTER:
        raise ValueError(f"{dtype_name}: fields on subgrids {subgrids}; one of {set(MAIN_FILTER)} expected")

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
        sites, poly, drop = _sites(tracer, by_field, chosen, subgrid, holder)
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
        holder=holder,
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
            sites, poly, drop = _sites(tracer, by_field, sel.components, subgrid, holder)
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


def _sites(tracer: Tracer, by_field, chosen, subgrid, holder: Holder):
    sites: dict[tuple, Site] = {}
    drop: dict[str, str] = {}
    for t, es in by_field.items():
        hit = holder.split(t)
        if hit is None:
            continue
        _, comp = hit
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
        hit = holder.split(path)
        return hit is not None and hit[1] in chosen

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
                        drop.setdefault(holder.split(p)[1], f"call {where} mixes layouts in {sub_id}")
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
    component outside the elm_drv trace. Analyzed routines the trace never
    visited (initialization, restart, finalization, ...) are read from their
    access records: a use is relevant when its path is a selected field of one
    of the holder's instances (`veg_pf%core%x`), or `this%<path>%x` in a
    routine of the holder or of its concrete types; a same-named component
    of another type is listed for review only. Lines outside every analyzed
    routine (no record to read) are a text search.
    """
    if not sel.components:
        return []
    holder = sel.holder or find_holder(fut, sel.dtype)
    handled = set(holder.routines.values())
    for ctype in holder.concrete_types:
        handled |= {
            sid for key in ("init", "setvalues", "clean")
            if isinstance(sid := fut.type_dict[ctype].procedures.get(key), str)
        }
    chosen = set(sel.components)
    # routines whose `this` holds the selected fields: `this%x` in the holder's own
    # routines, `this%<path>%x` in the concrete types' type-bound procedures
    this_prefix: dict[str, str] = {sid: "this%" for sid in holder.routines.values()}
    for emb in holder.embeddings:
        for sid in fut.type_dict[emb.concrete].procedures.values():
            if isinstance(sid, str):
                this_prefix[sid] = f"this%{emb.path}%" if emb.path else "this%"
    srcroot = srcroot_of(fut.subroutine_dict)
    out: list[tuple[str, str, bool]] = []
    # routines the trace never walked are walked here on demand (module scopes needed);
    # one that fails to walk falls to the text search of its lines
    from spel.scripts.module_resolver import ModuleScopes
    from spel.scripts.record_access import AccessMapper

    failures: dict[str, str] = {}
    mapper = AccessMapper(fut.subroutine_dict, ModuleScopes(fut.module_dict, fut.subroutine_dict), failures)

    def where(sub, ln: int) -> str:
        path = Path(sub.filepath)
        rel = path.relative_to(srcroot) if path.is_relative_to(srcroot) else path
        text = path.read_text(errors="replace").split("\n")[ln].strip()[:100]
        return f"{rel}:{ln + 1} {sub.id}: {text}"

    analyzed_lines: dict[str, set[int]] = defaultdict(set)
    for sub in fut.subroutine_dict.values():
        if not sub.filepath:
            continue
        analyzed_lines[str(sub.filepath)].update(range(sub.startline, sub.endline + 1))
        if sub.id in handled or sub.id in tracer.visited or getattr(sub, "library", False):
            continue
        rec = sub.record
        if rec is None and mapper.maps(sub) is not None:
            rec = sub.record
        if rec is None:
            analyzed_lines[str(sub.filepath)] -= set(range(sub.startline, sub.endline + 1))
            continue  # no record: its lines fall to the text search
        seen: set[tuple[int, str]] = set()
        for a in rec.accesses():
            hit = holder.split(a.path)
            prefix = this_prefix.get(sub.id)
            if hit is not None and hit[1] in chosen:
                comp, relevant = hit[1], True
            elif prefix and a.path.startswith(prefix) and a.path[len(prefix):] in chosen:
                comp, relevant = a.path[len(prefix):], True
            elif a.path.split("%")[-1] in chosen and "%" in a.path:
                comp, relevant = a.path.split("%")[-1], False  # a same-named component of another type
            else:
                continue
            if (a.ln, comp) in seen:
                continue
            seen.add((a.ln, comp))
            out.append((comp, where(sub, a.ln), relevant))

    # lines no analyzed routine covers: a text search (no record to read)
    pattern = re.compile(
        r"%\s*(" + "|".join(sorted(map(re.escape, chosen))) + r")\b", re.IGNORECASE
    )
    insts = "|".join(
        sorted(
            (rf"{re.escape(e.instance)}\s*%\s*{re.escape(e.path)}" if e.path else re.escape(e.instance))
            for e in holder.embeddings
        )
    )
    for path in sorted(srcroot.rglob("*.F90")):
        if "external_models" in path.parts:
            continue
        covered = analyzed_lines.get(str(path), set())
        lines = path.read_text(errors="replace").split("\n")
        for ln, line in enumerate(lines):
            if ln in covered:
                continue
            code = line.split("!")[0]
            for m in pattern.finditer(code):
                comp = m.group(1).lower()
                before = code[: m.start()]
                relevant = bool(re.search(rf"\b({insts})\s*$", before, re.IGNORECASE))
                out.append((comp, f"{path.relative_to(srcroot)}:{ln + 1} (no analyzed routine): {line.strip()[:100]}", relevant))
    return out
