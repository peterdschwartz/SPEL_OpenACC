"""
Compact views of state fields inside a window of the time step.

States carry over between steps and are used everywhere (dynSubgrid, history,
restart, ...), so their components keep the full layout. A selected field
gets a second pointer component `<field>_k` bound to compact storage; the
window's routines use it, x(p) -> x_k(k0p+fp), and elm_drv packs each clump's
filter elements before the window and unpacks them after it.

A component of the type is selected when, for every instance:

  * it is rank 1 on the patch subgrid and used in the window,
  * every access in the window is x(p) with p = filter_soilp(fp) in
    `do fp = 1, num_soilp` (or a dummy bound to such an element),
  * it is not passed as a whole array in the window, and no access site of
    it is also reached outside the window (that code needs the full layout),
  * an associate name it is reached through is used only at such sites
    (its selector is renamed to the compact view),
  * no use the trace doesn't see names the type's instance (select.untraced_uses),
  * every site that touches it touches only selected fields.
"""

from __future__ import annotations

from collections import defaultdict

from spel.scripts.fortran_parser.scope_walk import Access
from spel.transforms.compact.inventory import DRIVER_ID, Entry, Tracer, unpack_line
from spel.transforms.compact.select import (
    MAIN_FILTER,
    Selection,
    Site,
    rewritable,
    untraced_uses,
)

WINDOW_START = "ecosystemdynnoleaching1"
WINDOW_END = "ecosystemdynleaching"
SUFFIX = "_k"


def window_lines(sub_dict, start: str = WINDOW_START, end: str = WINDOW_END) -> tuple[int, int]:
    drv = sub_dict[DRIVER_ID]
    starts = [c.ln for c in drv.record.calls if c.name.lower() == start.lower()]
    if not starts:
        raise ValueError(f"elm_drv has no call to {start}")
    return min(starts), unpack_line(sub_dict, end)


def select_states(fut, dtype_name: str, start: str = WINDOW_START, end: str = WINDOW_END) -> Selection:
    subs, td = fut.subroutine_dict, fut.type_dict
    dtype = td[dtype_name]
    instances = list(dtype.instances)
    tracer = Tracer(subs, td, {i: dtype_name for i in instances}, set())
    tracer.run()
    lo, hi = window_lines(subs, start, end)
    tracer.unpack_ln = hi

    by_field: dict[str, list[Entry]] = defaultdict(list)
    for e in tracer.entries:
        by_field[e.field].append(e)
    by_comp: dict[str, list[Entry]] = defaultdict(list)
    for t, es in by_field.items():
        by_comp[t.split("%")[1]].extend(es)

    excluded: dict[str, str] = {}
    chosen: dict[str, str] = {}
    for comp, es in sorted(by_comp.items()):
        sg, rank, _ = tracer.component(f"{es[0].field}")
        inside = [e for e in es if lo <= e.top_ln <= hi]
        if not inside:
            continue
        outside_sites = {e.site for e in es if not lo <= e.top_ln <= hi}
        if sg != "p" or rank != 1:
            excluded[comp] = f"subgrid {sg}, rank {rank}"
        elif any(e.status == "arg?" for e in inside):
            excluded[comp] = "passed to a routine SPEL can't follow"
        elif bad := [e for e in inside if e.status == "pass" and not e.sub0]:
            excluded[comp] = f"passed as a whole array at {bad[0].loc}"
        elif bad := [e for e in inside if e.status != "pass" and rewritable(e, sg)]:
            excluded[comp] = rewritable(bad[0], sg)
        elif bad := [e for e in inside if e.site in outside_sites]:
            excluded[comp] = f"site {bad[0].loc} is also reached outside the window"
        else:
            chosen[comp] = "state"

    sel = Selection(
        dtype=dtype_name,
        subgrid="p",
        instances=instances,
        components=chosen,
        unpack={c: True for c in chosen},
        sites=[],
        excluded=excluded,
        untraced=[],
    )
    sel.mode = "state"
    while True:
        sites, aliases, drop = _state_sites(fut, tracer, by_field, sel.components, instances, lo, hi)
        uses = untraced_uses(fut, tracer, sel, by_field)
        for comp, where, relevant in uses:
            if relevant:
                drop.setdefault(comp, f"used outside the trace: {where}")
        if not drop:
            break
        for comp, reason in drop.items():
            sel.components.pop(comp, None)
            sel.unpack.pop(comp, None)
            sel.excluded[comp] = reason
    sel.sites = sorted(sites.values(), key=lambda s: (s.sub, s.ln, s.path))
    sel.aliases = aliases
    sel.untraced = [f"{where}{'' if relevant else '  (another type)'}" for _, where, relevant in uses]
    return sel


def _state_sites(fut, tracer: Tracer, by_field, chosen, instances, lo, hi):
    sites: dict[tuple, Site] = {}
    drop: dict[str, str] = {}
    for t, es in by_field.items():
        comp = t.split("%")[1]
        if comp not in chosen:
            continue
        for e in es:
            if not (lo <= e.top_ln <= hi) or not e.sub0:
                continue
            site = sites.get(e.site)
            fp = e.index.inner.var
            if site is None:
                site = sites[e.site] = Site(e.sub, e.ln, e.path, e.written, e.sub0, fp)
                site.rename = e.written == e.path or "%" in e.written
            elif (site.sub0, site.fp) != (e.sub0, fp):
                drop.setdefault(comp, f"site {e.loc} indexed differently in different visits")
            site.components.add(comp)

    def selected(path: str) -> bool:
        parts = path.split("%")
        return parts[0] in instances and len(parts) > 1 and parts[1] in chosen

    for key, site in sites.items():
        targets = tracer.site_targets.get(key)
        if targets and not all(selected(p) for p in targets):
            for comp in site.components:
                drop.setdefault(comp, f"site {site.sub}@{site.ln + 1} is also bound to {sorted(targets)[0]}")

    # associate names: every use in the routine must be a compact site
    aliases: dict[tuple[str, str], tuple[int, str]] = {}
    site_keys = set(sites)
    for site in sites.values():
        if site.rename:
            continue
        name = site.written.split("%")[0]
        rec = fut.subroutine_dict[site.sub].record
        frame = next((f for f in rec.frames if f.start_ln <= site.ln <= f.end_ln and name in f.names), None)
        if frame is None:
            drop.update({c: f"associate name {name} at {site.sub}@{site.ln + 1} not found" for c in site.components})
            continue
        uses = [
            e for e in rec.events
            if isinstance(e, Access) and e.via == name and frame.start_ln <= e.ln <= frame.end_ln
        ]
        if any((site.sub, e.ln, e.path) not in site_keys for e in uses):
            for comp in site.components:
                drop.setdefault(comp, f"associate name {name} in {site.sub} also used outside compact sites")
            continue
        aliases[(site.sub, name)] = (frame.start_ln, frame.names[name])
    return sites, aliases, drop
