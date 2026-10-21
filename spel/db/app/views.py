"""
Pages and HTMX partials of the ELM explorer.

Snapshot and configuration come from the URL (`?snap=`, `?cfg=`) when given,
else from the session (pickers in the banner), else the latest snapshot and the
default preset. JSON endpoints for the d3 views live in api.py.
"""

from __future__ import annotations

import json
from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.http import require_POST

from .models import (
    ConfigProfile,
    FieldState,
    FlatIf,
    IntrinsicGlobals,
    ModuleDependency,
    Modules,
    PresetConfig,
    Registration,
    Snapshot,
    SubroutineArgs,
    SubroutineCalltree,
    SubroutineActiveGlobalVars,
    SubroutineCode,
    SubroutineIntrinsicGlobals,
    Subroutines,
    TypeDefinitions,
    TypeProcedure,
    UserTypeInstances,
    UserTypes,
)
from .utils import queries as q
from .utils.configs import active_config, active_snapshot, all_configs, config_by_key
from .utils.ifs import build_env, ensure_if_evals, inactive_ranges, is_inactive, reachable

CATEGORY_ORDER = ["prognostic", "diagnostic", "intermediate", "input", "unused"]


# ------------------------------------------------------------------ context
def ctx_for(request):
    """Snapshot + configuration of this request, with the configuration evaluated."""
    snap = active_snapshot(request, request.GET.get("snap") or request.POST.get("snap"))
    cfg = active_config(request, request.GET.get("cfg") or request.POST.get("cfg"))
    if snap is not None:
        ensure_if_evals(snap, cfg["hash"], cfg["data"])
    return snap, cfg


def base_context(request, snap, cfg) -> dict:
    return {
        "snapshot": snap,
        "snapshots": Snapshot.objects.filter(loaded_at__isnull=False).order_by("-loaded_at"),
        "cfg": cfg,
        "configs": all_configs(request),
        "qs": f"snap={snap.label}&cfg={cfg['key']}" if snap else "",
    }


def is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def no_snapshot(request):
    return render(request, "home.html", {"snapshots": [], "cfg": None, "configs": [], "no_data": True})


# -------------------------------------------------------------------- home
def home(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    context = base_context(request, snap, cfg)
    cards = []
    for s in context["snapshots"]:
        cats = Counter(FieldState.objects.filter(snapshot=s).values_list("category", flat=True))
        cards.append({
            "snapshot": s,
            "n_subs": Subroutines.objects.filter(snapshot=s, analyzed=True).count(),
            "n_modules": Modules.objects.filter(snapshot=s).count(),
            "n_types": UserTypes.objects.filter(snapshot=s).count(),
            "n_fields": sum(cats.values()),
            "categories": [(c, cats.get(c, 0)) for c in CATEGORY_ORDER],
            "findings": FieldState.objects.filter(snapshot=s).filter(Q(restart_unneeded=True) | Q(restart_missing=True)).count(),
        })
    context["cards"] = cards
    drv = q.find_subroutine(snap, "elm_driver::elm_drv")
    context["driver"] = drv
    return render(request, "home.html", context)


# ----------------------------------------------------------------- pickers
def snapshot_picker(request):
    snap, cfg = ctx_for(request)
    return render(request, "configs/snapshot_selector.html", base_context(request, snap, cfg))


@require_POST
def select_snapshot(request):
    label = request.POST.get("snapshot", "")
    snap = Snapshot.objects.filter(label=label).first()
    if snap is not None:
        request.session["active_snapshot"] = snap.label
    snap, cfg = ctx_for(request)
    resp = render(request, "configs/snapshot_selector.html", base_context(request, snap, cfg))
    resp["HX-Trigger"] = json.dumps({"snapshotChanged": {"label": snap.label if snap else ""}})
    return resp


def config_picker(request):
    snap, cfg = ctx_for(request)
    return render(request, "configs/selector.html", base_context(request, snap, cfg))


@require_POST
def select_config_htmx(request):
    key = request.POST.get("config", "")
    if config_by_key(key) is not None:
        request.session["active_config_key"] = key
    snap, cfg = ctx_for(request)
    resp = render(request, "configs/selector.html", base_context(request, snap, cfg))
    resp["HX-Trigger"] = json.dumps({"configChanged": {"key": cfg["key"], "hash": cfg["hash"], "label": cfg["label"]}})
    return resp


def nml_values(request):
    snap, cfg = ctx_for(request)
    rows = []
    if snap is not None:
        defaults = IntrinsicGlobals.objects.filter(snapshot=snap).exclude(namelist_group="").select_related("gv_module").order_by("var_name")
        for g in defaults:
            if g.var_name in cfg["data"]:
                rows.append({"module": g.gv_module.module_name, "name": g.var_name, "value": cfg["data"][g.var_name], "source": "config", "group": g.namelist_group})
            else:
                rows.append({"module": g.gv_module.module_name, "name": g.var_name, "value": g.value, "source": "default", "group": g.namelist_group})
        known = {r["name"] for r in rows}
        for name, value in sorted(cfg["data"].items()):
            if name not in known:
                rows.append({"module": "", "name": name, "value": value, "source": "config (not analyzed)", "group": ""})
    rows.sort(key=lambda r: (r["source"] != "config", r["name"]))
    return render(request, "configs/values_modal.html", {"rows": rows, "cfg": cfg, "snapshot": snap})


# ------------------------------------------------------------------ search
def _startswith(qs, field_name, needle):
    return qs.annotate(startswith=Case(When(**{f"{field_name}__istartswith": needle}, then=Value(0)), default=Value(1), output_field=IntegerField()))


def sub_active_search(request):
    snap, cfg = ctx_for(request)
    needle = (request.POST.get("search") or request.GET.get("search") or "").strip()
    results = []
    if snap is not None and needle:
        qs = Subroutines.objects.filter(snapshot=snap, subroutine_name__icontains=needle).select_related("module")
        results = _startswith(qs, "subroutine_name", needle).order_by("startswith", "-analyzed", "subroutine_name")[:12]
    return render(request, "partials/search/sub_active_search.html", {"results": results, "query": needle, "snapshot": snap, "cfg": cfg})


def var_active_search(request):
    """Instances, `inst%member` fields and module variables matching the query (fuzzy), for the banner."""
    snap, cfg = ctx_for(request)
    needle = (request.POST.get("search") or request.GET.get("search") or "").strip().lower()
    items = []
    if snap is not None and needle:
        limit = 14
        if "%" in needle:
            inst_part, member_part = needle.split("%", 1)
            insts = UserTypeInstances.objects.filter(inst_module__snapshot=snap).select_related("instance_type")
            for inst in q.fuzzy_filter(inst_part, insts, lambda i: i.instance_name, limit=4):
                members = TypeDefinitions.objects.filter(user_type=inst.instance_type)
                for m in q.fuzzy_filter(member_part, members, lambda m: m.member_name, limit=limit):
                    items.append({"kind": "field", "key": f"{inst.instance_name}%{m.member_name}", "label": f"{inst.instance_name}%{m.member_name}", "detail": m.member_type, "type": inst.instance_type.user_type_name})
        else:
            insts = UserTypeInstances.objects.filter(inst_module__snapshot=snap).select_related("instance_type")
            for inst in q.fuzzy_filter(needle, insts, lambda i: i.instance_name, limit=5):
                items.append({"kind": "instance", "key": inst.instance_name, "label": f"{inst.instance_name}%", "detail": inst.instance_type.user_type_name, "type": inst.instance_type.user_type_name})
            gl = IntrinsicGlobals.objects.filter(snapshot=snap, parameter=False).select_related("gv_module")
            for g in q.fuzzy_filter(needle, gl, lambda g: g.var_name, limit=limit):
                items.append({"kind": "global", "key": f"{g.gv_module.module_name}::{g.var_name}", "label": f"{g.gv_module.module_name}::{g.var_name}", "detail": g.var_type})
            inst_of = {}
            for t_id, iname in UserTypeInstances.objects.filter(inst_module__snapshot=snap).values_list("instance_type_id", "instance_name"):
                inst_of.setdefault(t_id, []).append(iname)
            members = TypeDefinitions.objects.filter(user_type__snapshot=snap, user_type_id__in=inst_of)
            for m in q.fuzzy_filter(needle, members, lambda m: m.member_name, limit=limit):
                for iname in inst_of.get(m.user_type_id, [])[:3]:
                    items.append({"kind": "field", "key": f"{iname}%{m.member_name}", "label": f"{iname}%{m.member_name}", "detail": m.member_type})
        items = items[:limit]
    return render(request, "partials/search/var_active_search.html", {"items": items, "query": needle, "snapshot": snap, "cfg": cfg})


# ---------------------------------------------------------------- routines
def sub_view(request, sub_name):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    sub = q.find_subroutine(snap, sub_name)
    if sub is None:
        raise Http404(f"no routine {sub_name} in snapshot {snap.label}")
    context = base_context(request, snap, cfg) | {"sub": sub, "sub_name": sub.sub_id}
    return render(request, "sub_view.html", context)


def render_calltree(request, sub_name):
    """Textual step tree below the routine's first call in the step (config-pruned)."""
    snap, cfg = ctx_for(request)
    if snap is None:
        return HttpResponse("")
    sub = q.find_subroutine(snap, sub_name)
    if sub is None:
        raise Http404(sub_name)
    reach = reachable(snap.pk, cfg["hash"])
    keep_inactive = request.GET.get("inactive") == "1"
    tree = q.build_tree(snap.pk, reach, root_sub_pk=sub.pk, keep_inactive=keep_inactive)
    in_step = q.first_occurrence(snap.pk, sub.pk) is not None
    context = base_context(request, snap, cfg) | {"tree": tree, "sub": sub, "in_step": in_step, "expand_to": 2, "var_keys": [], "keep_inactive": keep_inactive}
    return render(request, "partials/calltree.html", context)


def subroutine_details(request, sub_name):
    snap, cfg = ctx_for(request)
    if snap is None:
        return HttpResponse("")
    sub = q.find_subroutine(snap, sub_name)
    if sub is None:
        raise Http404(sub_name)
    ranges = inactive_ranges(snap.pk, cfg["hash"])
    dtype_groups, globals_ = q.routine_accesses(sub, ranges)
    callees = q.routine_callees(sub, ranges)
    callers = (SubroutineCalltree.objects.filter(child_subroutine=sub).select_related("parent_subroutine", "parent_subroutine__module").order_by("parent_subroutine__subroutine_name", "lineno"))
    gates = []
    for fi in FlatIf.objects.filter(subroutine=sub, nml_gated=True).order_by("start_ln"):
        gates.append({"start": fi.start_ln, "end": fi.end_ln, "kind": fi.kind, "text": fi.condition_text, "active": not is_inactive(ranges, sub.pk, fi.start_ln + 1 if fi.end_ln > fi.start_ln else fi.start_ln) if fi.end_ln >= fi.start_ln else True})
    args = list(SubroutineArgs.objects.filter(subroutine=sub).select_related("user_type").order_by("position"))
    code = SubroutineCode.objects.filter(subroutine=sub).first()
    lines = []
    if code is not None:
        for i, text in enumerate(code.text.split("\n")):
            ln = code.startline + i
            lines.append({"ln": ln, "text": text, "inactive": is_inactive(ranges, sub.pk, ln)})
    regs = Registration.objects.filter(subroutine=sub).select_related("member", "instance", "global_var", "user_type").order_by("ln")
    context = base_context(request, snap, cfg) | {
        "sub": sub, "args": args, "callees": callees, "callers": callers, "dtype_groups": dtype_groups,
        "globals": [g for g in globals_ if not g["namelist"]], "nml_vars": [g for g in globals_ if g["namelist"]],
        "gates": gates, "lines": lines, "registrations": regs, "focus_ln": request.GET.get("ln"),
        "in_step": q.first_occurrence(snap.pk, sub.pk) is not None,
    }
    return render(request, "partials/subroutine_details.html", context)


# ------------------------------------------------------------- types/modules
def types_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    types = []
    cat_counts = {}
    for t, cat, n in FieldState.objects.filter(snapshot=snap, instance__isnull=False).values_list("instance__instance_type_id", "category").annotate(n=Count("pk")).values_list("instance__instance_type_id", "category", "n"):
        cat_counts.setdefault(t, Counter())[cat] += n
    for t in UserTypes.objects.filter(snapshot=snap).select_related("module", "parent").annotate(n_members=Count("user_type_def", distinct=True), n_instances=Count("instance_type", distinct=True)).order_by("user_type_name"):
        counts = cat_counts.get(t.pk, Counter())
        types.append({"type": t, "categories": [(c, counts.get(c, 0)) for c in CATEGORY_ORDER], "total": sum(counts.values())})
    return render(request, "types.html", base_context(request, snap, cfg) | {"types": types})


def type_detail(request, type_name):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    t = get_object_or_404(UserTypes, snapshot=snap, user_type_name=type_name.lower())
    instances = list(UserTypeInstances.objects.filter(instance_type=t).select_related("inst_module").order_by("instance_name"))
    inst = request.GET.get("instance")
    focus = next((i for i in instances if i.instance_name == inst), instances[0] if instances else None)
    needle = (request.GET.get("q") or "").strip()
    members = q.member_rows(snap, focus, t, needle)
    procs = TypeProcedure.objects.filter(user_type=t).select_related("subroutine").order_by("binding")
    cat_counts = Counter(fs.effective_category for fs in FieldState.objects.filter(snapshot=snap, instance=focus)) if focus else Counter()
    context = base_context(request, snap, cfg) | {
        "type": t, "instances": instances, "focus": focus, "members": members, "procs": procs, "needle": needle,
        "categories": [(c, cat_counts.get(c, 0)) for c in CATEGORY_ORDER],
        "extensions": UserTypes.objects.filter(parent=t).order_by("user_type_name"),
    }
    return render(request, "type_detail.html", context)


def modules_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    mods = Modules.objects.filter(snapshot=snap).annotate(
        n_subs=Count("subroutine_module", distinct=True), n_globals=Count("global_var", distinct=True),
        n_types=Count("user_type_module", distinct=True), n_uses=Count("moduledependency", distinct=True),
    ).order_by("module_name")
    return render(request, "modules.html", base_context(request, snap, cfg) | {"modules": mods})


def module_detail(request, module_name):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    mod = get_object_or_404(Modules, snapshot=snap, module_name=module_name.lower())
    subs = Subroutines.objects.filter(module=mod).order_by("startline")
    globals_ = IntrinsicGlobals.objects.filter(gv_module=mod).order_by("var_name")
    instances = UserTypeInstances.objects.filter(inst_module=mod).select_related("instance_type").order_by("instance_name")
    types = UserTypes.objects.filter(module=mod).order_by("user_type_name")
    uses = (ModuleDependency.objects.filter(module=mod, in_head=True).values("dep_module_name", "dep_module__module_name").annotate(n=Count("pk")).order_by("dep_module_name"))
    used_by = (ModuleDependency.objects.filter(dep_module=mod).values("module__module_name").annotate(n=Count("pk")).order_by("module__module_name"))
    context = base_context(request, snap, cfg) | {"mod": mod, "subs": subs, "globals": globals_, "instances": instances, "types": types, "uses": uses, "used_by": used_by}
    return render(request, "module_detail.html", context)


# ----------------------------------------------------------- variable catalog
def variables_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    g = request.GET
    qs = FieldState.objects.filter(snapshot=snap).select_related("instance", "instance__instance_type", "member", "global_var", "global_var__gv_module", "first_trace_node__subroutine")
    if g.get("q"):
        needle = g["q"].lower()
        qs = qs.filter(Q(member__member_name__icontains=needle) | Q(global_var__var_name__icontains=needle) | Q(instance__instance_name__icontains=needle))
    per_config = g.get("per_config") == "1"
    cats = config_categories(snap, cfg["hash"]) if per_config else None
    if g.get("category") and not per_config:
        qs = qs.filter(Q(category=g["category"]) | Q(override=g["category"]))
    if g.get("subgrid"):
        qs = qs.filter(member__subgrid=g["subgrid"])
    if g.get("instance"):
        qs = qs.filter(instance__instance_name=g["instance"])
    if g.get("kind") == "inst":
        qs = qs.filter(instance__isnull=False)
    elif g.get("kind") == "global":
        qs = qs.filter(global_var__isnull=False)
    for flag in ("restart", "history"):
        if g.get(flag) in ("0", "1"):
            qs = qs.filter(**{flag: g[flag] == "1"})
    if g.get("finding") == "restart_unneeded":
        qs = qs.filter(restart_unneeded=True)
    elif g.get("finding") == "restart_missing":
        qs = qs.filter(restart_missing=True)
    elif g.get("finding") == "overridden":
        qs = qs.exclude(override="")
    order = g.get("order") or "name"
    order_map = {"name": ("instance__instance_name", "member__member_name", "global_var__var_name"), "routines": ("-n_routines",), "writes": ("-n_writes",), "reads": ("-n_reads",), "first": ("first_trace_node__order",)}
    qs = qs.order_by(*order_map.get(order, order_map["name"]))
    rows = []
    if per_config:
        wanted = g.get("category")
        for fs in qs:
            cat = cats.get(q.state_key(fs), "unused")
            if wanted and cat != wanted:
                continue
            rows.append((fs, cat))
        paginator = Paginator(rows, 100)
    else:
        paginator = Paginator(qs, 100)
    page = paginator.get_page(g.get("page"))
    items = [(r[0], r[1]) if per_config else (r, r.effective_category) for r in page.object_list]
    instances = UserTypeInstances.objects.filter(inst_module__snapshot=snap).order_by("instance_name").values_list("instance_name", flat=True)
    context = base_context(request, snap, cfg) | {
        "page": page, "items": items, "filters": g, "instances": instances, "categories": CATEGORY_ORDER, "per_config": per_config,
        "subgrid_levels": [("p", "patch"), ("c", "column"), ("l", "landunit"), ("t", "topounit"), ("g", "gridcell")],
    }
    template = "partials/variables_table.html" if is_htmx(request) else "variables.html"
    return render(request, template, context)


def config_categories(snap, cfg_hash):
    return q.config_categories(snap, cfg_hash)


@login_required
@require_POST
def set_override(request, state_id):
    fs = get_object_or_404(FieldState, pk=state_id)
    value = request.POST.get("override", "")
    if value not in ("", *CATEGORY_ORDER):
        return HttpResponseBadRequest("bad category")
    fs.override = value
    fs.override_note = request.POST.get("note", "")[:500]
    fs.save(update_fields=["override", "override_note"])
    return render(request, "partials/variable_row.html", {"fs": fs, "category": fs.effective_category, "snapshot": fs.snapshot, "cfg": active_config(request)})


# ----------------------------------------------------------------- tracing
def trace_view(request):
    """The trace workspace: a picker builds the list, `?v=col_ws%25h2osoi_liq&v=veg_cf%25npp` is what is traced."""
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    keys = request.GET.getlist("v")
    refs = q.parse_vars(snap, keys)
    unknown = [k for k in keys if k and not any(r.key == k or r.label == k for r in refs)]
    instances = UserTypeInstances.objects.filter(inst_module__snapshot=snap).select_related("instance_type").order_by("instance_name")
    context = base_context(request, snap, cfg) | {"refs": refs, "keys": [r.key for r in refs], "unknown": unknown, "instances": instances}
    return render(request, "trace_view.html", context)


def _instance(snap, name: str):
    name = (name or "").strip().lower().split()[0].rstrip("%") if (name or "").strip() else ""
    if not name:
        return None
    return UserTypeInstances.objects.filter(inst_module__snapshot=snap, instance_name=name).select_related("instance_type", "inst_module").first()


def picker(request):
    """Picker results: all components of an instance (fuzzy-narrowed), or matches across instances/variables."""
    snap, cfg = ctx_for(request)
    if snap is None:
        return HttpResponse("")
    needle = (request.GET.get("q") or "").strip()
    inst = _instance(snap, request.GET.get("instance"))
    context = base_context(request, snap, cfg) | {"needle": needle, "instance": inst}
    if inst is not None:
        context["rows"] = q.member_rows(snap, inst, inst.instance_type, needle)
        context["mode"] = "members"
    else:
        items = []
        if needle:
            insts = UserTypeInstances.objects.filter(inst_module__snapshot=snap).select_related("instance_type")
            for i in q.fuzzy_filter(needle, insts, lambda i: i.instance_name, limit=8):
                items.append({"kind": "instance", "key": i.instance_name, "label": f"{i.instance_name}%", "detail": i.instance_type.user_type_name})
            gl = IntrinsicGlobals.objects.filter(snapshot=snap, parameter=False).select_related("gv_module")
            for g in q.fuzzy_filter(needle, gl, lambda g: g.var_name, limit=10):
                items.append({"kind": "global", "key": f"{g.gv_module.module_name}::{g.var_name}", "label": f"{g.gv_module.module_name}::{g.var_name}", "detail": g.var_type + (" · namelist" if g.namelist_group else "")})
            inst_of: dict[int, list[str]] = {}
            for t_id, iname in UserTypeInstances.objects.filter(inst_module__snapshot=snap).values_list("instance_type_id", "instance_name"):
                inst_of.setdefault(t_id, []).append(iname)
            members = TypeDefinitions.objects.filter(user_type__snapshot=snap, user_type_id__in=inst_of)
            for m in q.fuzzy_filter(needle, members, lambda m: m.member_name, limit=12):
                for iname in inst_of.get(m.user_type_id, [])[:4]:
                    items.append({"kind": "field", "key": f"{iname}%{m.member_name}", "label": f"{iname}%{m.member_name}", "detail": m.member_type})
        context["items"] = items[:40]
        context["mode"] = "search"
    return render(request, "partials/picker_results.html", context)


def type_members(request, type_name):
    """Member rows of a type for one instance, fuzzy-filtered (the type page's filter box)."""
    snap, cfg = ctx_for(request)
    if snap is None:
        return HttpResponse("")
    t = get_object_or_404(UserTypes, snapshot=snap, user_type_name=type_name.lower())
    inst = _instance(snap, request.GET.get("instance"))
    if inst is None:
        inst = UserTypeInstances.objects.filter(instance_type=t).order_by("instance_name").first()
    rows = q.member_rows(snap, inst, t, (request.GET.get("q") or "").strip())
    return render(request, "partials/member_rows.html", {"rows": rows, "snapshot": snap, "cfg": cfg})


def trace_vars(request):
    """Textual tree with one marker column per traced variable (routines not touching any are pruned)."""
    snap, cfg = ctx_for(request)
    if snap is None:
        return HttpResponse("")
    keys = request.GET.getlist("v")
    refs = q.parse_vars(snap, keys)
    reach = reachable(snap.pk, cfg["hash"])
    ranges = inactive_ranges(snap.pk, cfg["hash"])
    marks: dict[int, dict[str, set]] = {}
    for ref in refs:
        for row in q.trace_rows(snap, ref, reach, ranges):
            marks.setdefault(row["c"], {}).setdefault(ref.key, set()).add(row["s"])
    tree = q.build_tree(snap.pk, reach)

    def prune(node) -> bool:
        node.children = [c for c in node.children if prune(c)]
        merged: dict[str, set] = {}
        for o in node.orders:
            for k, v in marks.get(o, {}).items():
                merged.setdefault(k, set()).update(v)
        if merged:
            node.marks = {k: q.merge_status(v) for k, v in merged.items()}
        return bool(merged) or bool(node.children)

    tree = [n for n in tree if prune(n)] if refs else tree
    context = base_context(request, snap, cfg) | {"tree": tree, "refs": refs, "var_keys": [r.key for r in refs], "expand_to": 3, "in_step": True}
    return render(request, "partials/trace_tree.html", context)


# ------------------------------------------------------------------ graphs
def calltree_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    root = request.GET.get("root", "")
    return render(request, "calltree_view.html", base_context(request, snap, cfg) | {"root": root})


def modgraph_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    return render(request, "modgraph.html", base_context(request, snap, cfg))


# -------------------------------------------------------------------- diff
def parse_side(request, name):
    """`snap-label:cfg-key` (either part optional) -> (Snapshot, cfg dict)."""
    raw = request.GET.get(name, "")
    if not raw and (request.GET.get(f"{name}_snap") or request.GET.get(f"{name}_cfg")):
        raw = f"{request.GET.get(f'{name}_snap', '')}:{request.GET.get(f'{name}_cfg', '')}"
    label, _, key = raw.partition(":") if ":" in raw else ("", "", raw)
    if raw and ":" not in raw and Snapshot.objects.filter(label=raw).exists():
        label, key = raw, ""
    snap = Snapshot.objects.filter(label=label).first() if label else active_snapshot(request)
    cfg = config_by_key(key) if key else active_config(request)
    if cfg is None:
        cfg = active_config(request)
    if snap is not None:
        ensure_if_evals(snap, cfg["hash"], cfg["data"])
    return snap, cfg


def diff_view(request):
    snap, cfg = ctx_for(request)
    if snap is None:
        return no_snapshot(request)
    a_snap, a_cfg = parse_side(request, "a")
    b_snap, b_cfg = parse_side(request, "b")
    context = base_context(request, snap, cfg) | {
        "a": {"snap": a_snap, "cfg": a_cfg, "raw": request.GET.get("a", "")},
        "b": {"snap": b_snap, "cfg": b_cfg, "raw": request.GET.get("b", "")},
        "tabs": [("routines", "Reached routines"), ("namelist", "Namelist values"), ("ifs", "Flipped if blocks"), ("fields", "Variable categories"), ("access", "Routine accesses")],
    }
    return render(request, "diff.html", context)


def diff_tab(request, tab):
    a_snap, a_cfg = parse_side(request, "a")
    b_snap, b_cfg = parse_side(request, "b")
    if a_snap is None or b_snap is None:
        return HttpResponse("<p>Pick two sides.</p>")
    same_snapshot = a_snap.pk == b_snap.pk
    context = {"a_snap": a_snap, "a_cfg": a_cfg, "b_snap": b_snap, "b_cfg": b_cfg, "same_snapshot": same_snapshot, "tab": tab}
    if tab == "routines":
        ra, rb = reachable(a_snap.pk, a_cfg["hash"]), reachable(b_snap.pk, b_cfg["hash"])
        ids_a = set(Subroutines.objects.filter(pk__in=ra.sub_ids).values_list("sub_id", flat=True))
        ids_b = set(Subroutines.objects.filter(pk__in=rb.sub_ids).values_list("sub_id", flat=True))
        context |= {"only_a": sorted(ids_a - ids_b), "only_b": sorted(ids_b - ids_a), "both": len(ids_a & ids_b)}
    elif tab == "namelist":
        env_a, env_b = build_env(a_snap, a_cfg["data"]), build_env(b_snap, b_cfg["data"])
        names = sorted(set(env_a) | set(env_b))
        context["rows"] = [(n, env_a.get(n, "—"), env_b.get(n, "—")) for n in names if env_a.get(n) != env_b.get(n)]
        context["n_same"] = sum(1 for n in names if env_a.get(n) == env_b.get(n))
    elif tab == "ifs":
        if same_snapshot:
            ia = inactive_ranges(a_snap.pk, a_cfg["hash"])
            ib = inactive_ranges(b_snap.pk, b_cfg["hash"])
            flips = []
            subs = {s.pk: s for s in Subroutines.objects.filter(pk__in=set(ia) | set(ib))}
            for sub_pk in set(ia) | set(ib):
                sa, sb = set(ia.get(sub_pk, [])), set(ib.get(sub_pk, []))
                for start, end in sorted(sa ^ sb):
                    fi = FlatIf.objects.filter(subroutine_id=sub_pk, start_ln=start, end_ln=end).first()
                    flips.append({"sub": subs[sub_pk], "start": start, "end": end, "text": fi.condition_text if fi else "", "active_a": (start, end) not in sa, "active_b": (start, end) not in sb})
            flips.sort(key=lambda f: (f["sub"].sub_id, f["start"]))
            context["flips"] = flips
    elif tab == "fields":
        ca = q.config_categories(a_snap, a_cfg["hash"])
        cb = q.config_categories(b_snap, b_cfg["hash"])
        label_a = _state_labels(a_snap)
        label_b = _state_labels(b_snap) if not same_snapshot else label_a
        by_label_a = {label_a.get(k): v for k, v in ca.items() if k in label_a}
        by_label_b = {label_b.get(k): v for k, v in cb.items() if k in label_b}
        changes = []
        for label in sorted(set(by_label_a) | set(by_label_b)):
            va, vb = by_label_a.get(label, "—"), by_label_b.get(label, "—")
            if va != vb:
                changes.append((label, va, vb))
        context["changes"] = changes
        context["n_same"] = len(set(by_label_a) & set(by_label_b)) - len([c for c in changes if c[1] != "—" and c[2] != "—"])
    elif tab == "access":
        context["rows"] = _access_diff(a_snap, a_cfg, b_snap, b_cfg)
    return render(request, f"partials/diff_{tab}.html", context)


def _state_labels(snap) -> dict[tuple, str]:
    out = {}
    for inst, member, gvar, iname, mname, gname, gmod in FieldState.objects.filter(snapshot=snap).values_list(
        "instance_id", "member_id", "global_var_id", "instance__instance_name", "member__member_name", "global_var__var_name", "global_var__gv_module__module_name"
    ):
        out[("i", inst, member) if inst else ("g", gvar)] = f"{iname}%{mname}" if inst else f"{gmod}::{gname}"
    return out


def _access_diff(a_snap, a_cfg, b_snap, b_cfg, limit=400):
    """Per routine (present on both sides): module-variable accesses (path, status) only on one side."""
    def summary(snap, cfg):
        reach = reachable(snap.pk, cfg["hash"])
        ranges = inactive_ranges(snap.pk, cfg["hash"])
        subs = {pk: sid for pk, sid in Subroutines.objects.filter(pk__in=reach.sub_ids).values_list("pk", "sub_id")}
        acc: dict[str, dict[str, set]] = {}
        for sub_pk, path, status, ln in SubroutineActiveGlobalVars.objects.filter(subroutine_id__in=subs).values_list("subroutine_id", "path", "status", "ln"):
            if not is_inactive(ranges, sub_pk, ln):
                acc.setdefault(subs[sub_pk], {}).setdefault(path, set()).update(status)
        for sub_pk, path, status, ln in SubroutineIntrinsicGlobals.objects.filter(sub_id_id__in=subs).values_list("sub_id_id", "path", "status", "gv_ln"):
            if not is_inactive(ranges, sub_pk, ln):
                acc.setdefault(subs[sub_pk], {}).setdefault(path, set()).update(status)
        return {s: {p: "".join(sorted(st)) for p, st in d.items()} for s, d in acc.items()}
    sa, sb = summary(a_snap, a_cfg), summary(b_snap, b_cfg)
    rows = []
    for sub_id in sorted(set(sa) & set(sb)):
        da, db = sa[sub_id], sb[sub_id]
        diff = [(p, da.get(p, "—"), db.get(p, "—")) for p in sorted(set(da) | set(db)) if da.get(p) != db.get(p)]
        if diff:
            rows.append({"sub_id": sub_id, "diff": diff[:50], "n": len(diff)})
        if len(rows) >= limit:
            break
    return rows


# ----------------------------------------------------------------- configs
def config_start(request):
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to edit namelist configurations.")
        return redirect(f"{settings.LOGIN_URL}?next=/configs/")
    cfg, _ = ConfigProfile.objects.get_or_create(owner=request.user, name="Default", defaults={"data": {}})
    return redirect("config_editor", config_id=cfg.id)


def _editor_rows(snap, config):
    rows = []
    for g in IntrinsicGlobals.objects.filter(snapshot=snap).exclude(namelist_group="").select_related("gv_module").order_by("namelist_group", "var_name"):
        rows.append({"ig": g, "current": config.data.get(g.var_name, g.value), "overridden": g.var_name in config.data})
    return rows


@login_required
def config_editor(request, config_id):
    snap, cfg = ctx_for(request)
    config = get_object_or_404(ConfigProfile, id=config_id, owner=request.user)
    if snap is None:
        return no_snapshot(request)
    context = base_context(request, snap, cfg) | {"config": config, "rows": _editor_rows(snap, config), "my_configs": ConfigProfile.objects.filter(owner=request.user).order_by("name")}
    return render(request, "configs/editor.html", context)


@login_required
@require_POST
def set_config_value(request, config_id, var_name):
    snap, cfg = ctx_for(request)
    config = get_object_or_404(ConfigProfile, id=config_id, owner=request.user)
    ig = get_object_or_404(IntrinsicGlobals, snapshot=snap, var_name=var_name.lower())
    value = (request.POST.get("value") or "").strip()
    if request.POST.get("reset") or value == "" or value == ig.value:
        config.data.pop(ig.var_name, None)
    else:
        config.data[ig.var_name] = value
    config.save(update_fields=["data"])
    return render(request, "configs/row.html", {"config": config, "ig": ig, "current": config.data.get(ig.var_name, ig.value), "overridden": ig.var_name in config.data})


@login_required
@require_POST
def new_config(request):
    name = (request.POST.get("name") or "").strip()[:128]
    if not name:
        return HttpResponseBadRequest("name required")
    base = config_by_key(request.POST.get("base", "")) or {"data": {}}
    config, _ = ConfigProfile.objects.get_or_create(owner=request.user, name=name, defaults={"data": dict(base["data"])})
    request.session["active_config_key"] = f"user:{config.id}"
    return redirect("config_editor", config_id=config.id)


# ------------------------------------------------------------------- auth
class SignupView(View):
    template_name = "registration/signup.html"

    def get(self, request):
        if not settings.REGISTRATION_OPEN:
            return HttpResponse("Registration is closed", status=403)
        return render(request, self.template_name, {"form": UserCreationForm()})

    def post(self, request):
        if not settings.REGISTRATION_OPEN:
            return HttpResponse("Registration is closed", status=403)
        form = UserCreationForm(request.POST)
        invite = request.POST.get("invite_code", "")
        if settings.INVITE_CODE and invite != settings.INVITE_CODE:
            form.add_error(None, "Invalid invite code")
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
        return render(request, self.template_name, {"form": form})
