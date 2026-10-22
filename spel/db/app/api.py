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
    """
    The direct callees of `root` (default: the step's root) as a dependency
    graph for the box diagram: nodes in call order, an edge from an earlier
    callee to a later one when something the first writes (anywhere in its
    subtree) is read by the second before the second writes it. Pruned calls
    and accesses are left out under the configuration (`inactive=1` keeps the
    pruned calls as grey boxes, still without edges).
    """
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    reach = reachable(snap.pk, cfg["hash"])
    ranges = inactive_ranges(snap.pk, cfg["hash"])
    root = request.GET.get("root", "")
    root_sub = q.find_subroutine(snap, root) if root else None
    if root and root_sub is None:  # not an exact name: the best fuzzy match, analyzed routines first
        qs = Subroutines.objects.filter(snapshot=snap).order_by("-analyzed", "subroutine_name")
        hits = q.fuzzy_filter(root, qs, lambda r: r.sub_id if "::" in root else r.subroutine_name, limit=1)
        if not hits:
            raise Http404(root)
        root_sub = hits[0]
    keep = request.GET.get("inactive") == "1"
    g = q.dependency_graph(snap.pk, reach, ranges, root_sub.pk if root_sub else None, keep_inactive=keep)
    if g is None:
        raise Http404(root or "root")
    return JsonResponse({"snapshot": snap.label, "config": cfg["label"], **g})


def modgraph(request):
    """
    The modules `root` uses at module scope (`dir=usedby`: the modules that use
    it) as a layered diagram: edges among them are their own head `use`s, from
    the user to the used module (`n` names imported, `whole` for a plain use).
    """
    snap, cfg = ctx_for(request)
    if snap is None:
        raise Http404("no snapshot")
    direction = "usedby" if request.GET.get("dir") == "usedby" else "uses"
    mods = {m.pk: m for m in Modules.objects.filter(snapshot=snap).annotate(n_subs=Count("subroutine_module", distinct=True), n_globals=Count("global_var", distinct=True))}
    heads = list(ModuleDependency.objects.filter(module__snapshot=snap, in_head=True, dep_module__isnull=False)
                 .values_list("module_id", "dep_module_id", "ln", "whole", "object_used"))
    uses: dict[int, set] = defaultdict(set)
    used_by: dict[int, set] = defaultdict(set)
    first_ln: dict[tuple, int] = {}
    for a, b, ln, whole, name in heads:
        uses[a].add(b)
        used_by[b].add(a)
        first_ln[(a, b)] = min(first_ln.get((a, b), ln), ln)
    root_name = (request.GET.get("root") or "").strip().lower()
    by_name = {m.module_name: m for m in mods.values()}
    if not root_name:
        root_name = "elm_driver" if "elm_driver" in by_name else max(by_name, key=lambda n: len(uses[by_name[n].pk]), default="")
    root = by_name.get(root_name)
    if root is None:  # not an exact name: the best fuzzy match
        hits = q.fuzzy_filter(root_name, sorted(by_name), lambda n: n, limit=1)
        if not hits:
            raise Http404(root_name)
        root = by_name[hits[0]]
    members = uses[root.pk] if direction == "uses" else used_by[root.pk]
    order = {m: (first_ln.get((root.pk, m), 0) if direction == "uses" else first_ln.get((m, root.pk), 0)) for m in members}

    def node(pk):
        m = mods[pk]
        return {"id": m.module_name, "order": order.get(pk, 0), "subs": m.n_subs, "globals": m.n_globals,
                "file": m.filepath.split("/")[-2] if "/" in m.filepath else "", "n_uses": len(uses[pk]), "n_used_by": len(used_by[pk])}

    nodes = sorted((node(pk) for pk in members), key=lambda n: (n["order"], n["id"]))
    names: dict[tuple, list] = defaultdict(list)
    whole_use: set[tuple] = set()
    for a, b, ln, whole, name in heads:
        if a in members and b in members:
            if whole:
                whole_use.add((a, b))
            elif name:
                names[(a, b)].append(name)
    edges = []
    for (a, b) in sorted(set(names) | whole_use, key=lambda ab: (order.get(ab[0], 0), order.get(ab[1], 0))):
        items = sorted(set(names.get((a, b), [])))
        edges.append({"s": mods[a].module_name, "t": mods[b].module_name, "n": max(1, len(items)), "whole": (a, b) in whole_use, "vars": items[:q.MAX_EDGE_VARS]})
    return JsonResponse({"snapshot": snap.label, "dir": direction, "root": node(root.pk), "nodes": nodes, "edges": edges})


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
