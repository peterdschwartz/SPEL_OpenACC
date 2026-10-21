"""JSON endpoints for the d3 views (timeline, node-link call tree, module graph, flag impact)."""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models import Count
from django.http import Http404, JsonResponse

from .models import FlatIf, FlatIfNamelistVar, IntrinsicGlobals, ModuleDependency, Modules, SubroutineActiveGlobalVars, Subroutines
from .utils import queries as q
from .utils.ifs import inactive_ranges, is_inactive, reachable
from .views import ctx_for


def timeline(request):
    """Marks and arcs of the selected variables along the step (see the plan's JSON shape)."""
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    refs = q.parse_vars(snap, request.GET.getlist("v"))
    reach = reachable(snap.pk, cfg["hash"])
    ranges = inactive_ranges(snap.pk, cfg["hash"])
    nodes = {r[1]: r for r in q.load_nodes(snap.pk)}
    tops = q.top_level(snap.pk)
    occ = q.occurrence_index(snap.pk)
    per_var = {ref.key: q.trace_rows(snap, ref, reach, ranges) for ref in refs}
    if request.GET.get("all") == "1":
        orders = sorted(o for o in nodes if o in reach.orders)
    else:
        orders = sorted({m["c"] for rows in per_var.values() for m in rows})
    col_of = {o: i for i, o in enumerate(orders)}
    columns = []
    for o in orders:
        r = nodes[o]
        k, n = occ.get(o, (1, 1))
        columns.append({"i": col_of[o], "node": o, "sub": r[6], "short": r[4] + (f" #{k}" if n > 1 else ""), "module": r[5] or "lib", "depth": r[7], "order": o, "top": nodes[tops[o]][4] if tops.get(o) in nodes else r[4], "top_order": tops.get(o, o)})
    steps = []
    for c in columns:
        if steps and steps[-1]["top_order"] == c["top_order"]:
            steps[-1]["c1"] = c["i"]
        else:
            steps.append({"c0": c["i"], "c1": c["i"], "label": c["top"], "top_order": c["top_order"]})
    rows = []
    for ref in refs:
        marks = [m | {"c": col_of[m["c"]], "node": m["c"]} for m in per_var[ref.key]]
        state = ref.state
        rows.append({
            "key": ref.key, "label": ref.label, "kind": ref.kind,
            "category": state.effective_category if state else "", "restart": bool(state and state.restart), "history": bool(state and state.history),
            "config_category": q.categorize([(m["s"], m["cond"]) for m in marks], bool(state and state.history)) if marks else "unused",
            "marks": marks, "arcs": q.arcs_for(marks),
        })
    return JsonResponse({"snapshot": snap.label, "config": {"label": cfg["label"], "key": cfg["key"], "hash": cfg["hash"]}, "columns": columns, "steps": steps, "rows": rows})


def _node_json(n: q.Node, depth_limit, marks=None, base_depth=0):
    d = {"id": n.order, "name": n.name, "sub": n.sub_id, "label": n.label, "depth": n.depth, "size": n.size, "cut": n.cut, "analyzed": n.analyzed, "active": n.active, "count": n.count}
    if marks is not None:
        merged: dict[str, str] = {}
        for o in n.orders:
            for k, v in marks.get(o, {}).items():
                merged[k] = q.merge_status([merged[k], v]) if k in merged else v
        if merged:
            d["marks"] = merged
    if n.children and (depth_limit is None or n.depth - base_depth < depth_limit):
        d["children"] = [_node_json(c, depth_limit, marks, base_depth) for c in n.children]
    elif n.children:
        d["collapsed"] = len(n.children)
        d["n_desc"] = n.size - 1
    return d


def calltree(request):
    """The step tree (or the subtree rooted at `root`) for the d3 node-link view; `inactive=1` keeps pruned routines."""
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    reach = reachable(snap.pk, cfg["hash"])
    root = request.GET.get("root", "")
    root_sub = q.find_subroutine(snap, root) if root else None
    depth = request.GET.get("depth")
    depth_limit = int(depth) if depth and depth.isdigit() else None
    keep = request.GET.get("inactive") == "1"
    tree = q.build_tree(snap.pk, reach, root_sub_pk=root_sub.pk if root_sub else None, keep_inactive=keep)
    marks = None
    refs = q.parse_vars(snap, request.GET.getlist("v"))
    if refs:
        ranges = inactive_ranges(snap.pk, cfg["hash"])
        marks = {}
        for ref in refs:
            for row in q.trace_rows(snap, ref, reach, ranges):
                marks.setdefault(row["c"], {}).setdefault(ref.key, "")
                marks[row["c"]][ref.key] = q.merge_status([marks[row["c"]][ref.key], row["s"]]) if marks[row["c"]][ref.key] else row["s"]
    return JsonResponse({"snapshot": snap.label, "config": cfg["label"], "roots": [_node_json(n, depth_limit, marks, n.depth) for n in tree], "vars": [r.key for r in refs]})


def modgraph(request):
    """Module `use` graph: nodes = modules, links = head uses (weight = only-items, 1 for a whole use)."""
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    mods = {m.pk: m for m in Modules.objects.filter(snapshot=snap).annotate(n_subs=Count("subroutine_module", distinct=True), n_globals=Count("global_var", distinct=True))}
    links = Counter()
    for mod, dep in ModuleDependency.objects.filter(module__snapshot=snap, in_head=True, dep_module__isnull=False).values_list("module_id", "dep_module_id"):
        links[(mod, dep)] += 1
    nodes = [{"id": m.module_name, "subs": m.n_subs, "globals": m.n_globals, "file": m.filepath.split("/")[-2] if "/" in m.filepath else ""} for m in mods.values()]
    return JsonResponse({"nodes": nodes, "links": [{"source": mods[a].module_name, "target": mods[b].module_name, "weight": w} for (a, b), w in links.items() if a in mods and b in mods]})


def flag_impact(request, var_name):
    """Routines and accesses gated by a namelist flag: if blocks mentioning it, and what lies inside them."""
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    gvar = IntrinsicGlobals.objects.filter(snapshot=snap, var_name=var_name.lower()).first()
    if gvar is None:
        raise Http404(var_name)
    ifs = FlatIf.objects.filter(flatifnamelistvar__namelist_var__active_var_id=gvar).select_related("subroutine").order_by("subroutine__sub_id", "start_ln")
    ranges = inactive_ranges(snap.pk, cfg["hash"])
    out = []
    gated_subs = set()
    for fi in ifs:
        inside = SubroutineActiveGlobalVars.objects.filter(subroutine=fi.subroutine, ln__gte=fi.start_ln, ln__lte=fi.end_ln).values("path").annotate(n=Count("pk"))
        calls = list(fi.subroutine.parent_subroutine.filter(lineno__gte=fi.start_ln, lineno__lte=fi.end_ln).values_list("child_subroutine__sub_id", flat=True))
        gated_subs.update(c for c in calls if c)
        out.append({"sub": fi.subroutine.sub_id, "start": fi.start_ln, "end": fi.end_ln, "kind": fi.kind, "text": fi.condition_text,
                    "active": not is_inactive(ranges, fi.subroutine_id, fi.start_ln + (1 if fi.end_ln > fi.start_ln else 0)),
                    "accesses": [{"path": a["path"], "n": a["n"]} for a in inside], "calls": [c for c in calls if c]})
    return JsonResponse({"flag": f"{gvar.gv_module.module_name}::{gvar.var_name}", "value": cfg["data"].get(gvar.var_name, gvar.value), "blocks": out, "gated_routines": sorted(gated_subs)})
