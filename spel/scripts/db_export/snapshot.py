"""Write every table of one analysis snapshot as CSV plus snapshot.json."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spel.scripts.db_export import fieldstate, filters, ifs, modules, routines
from spel.scripts.db_export.context import ExportContext
from spel.scripts.db_export.csv_io import write_table
from spel.scripts.db_export.schema import SNAPSHOT_JSON, TABLES
from spel.scripts.db_export.trace import StaticTrace

DRIVER_ID = "elm_driver::elm_drv"


def default_label(meta: dict) -> str:
    e3sm = meta.get("e3sm", {}) or {}
    branch = (e3sm.get("branch") or "e3sm").split("/")[-1]
    commit = (e3sm.get("commit") or "")[:7]
    return f"{branch}@{commit}" if commit else branch


def export_snapshot(
    fut,
    meta: dict,
    out_dir: Path,
    label: Optional[str] = None,
    case: Optional[str] = None,
    roots: Optional[list[str]] = None,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """
    fut:   the analysis (FunctionalUnitTest) with source paths anchored at meta["e3sm_srcroot"]
    meta:  the cache's meta.json content (analysis_cache.current_meta() plus created_at, ...)
    roots: trace roots (default elm_drv; a case export uses its primary subroutines)
    Returns the snapshot.json content.
    """
    log = logger or logging.getLogger("spel.export")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = label or default_label(meta)
    ctx = ExportContext(fut, meta, Path(meta.get("e3sm_srcroot") or fut.e3sm_srcroot))
    counts: dict[str, int] = {}

    def write(name, rows):
        counts[name] = write_table(out_dir, name, rows)
        log.info(f"  {name}: {counts[name]} rows")

    write("modules", modules.modules_rows(ctx))
    write("module_deps", modules.module_dep_rows(ctx))
    write("user_types", modules.user_type_rows(ctx))
    write("type_defs", modules.type_def_rows(ctx))
    write("type_procedures", modules.type_procedure_rows(ctx))
    instances, globals_ = modules.global_rows(ctx)
    write("user_type_instances", instances)
    write("intrinsic_globals", globals_)
    write("subroutines", routines.subroutine_rows(ctx))
    write("subroutine_code", routines.code_rows(ctx))
    write("subroutine_args", routines.arg_rows(ctx))
    write("subroutine_local_arrays", routines.local_array_rows(ctx))
    write("subroutine_calltree", routines.calltree_rows(ctx))
    write("call_bindings", routines.binding_rows(ctx))
    dtype_rows, intr_rows, arg_rows, prop_rows = routines.access_rows(ctx)
    write("active_dtype_vars", dtype_rows)
    write("intrinsic_access", intr_rows)
    write("arg_access", arg_rows)
    write("propagated_access", prop_rows)
    if_rows, if_var_rows = ifs.flat_if_rows(ctx)
    write("nml_ifs", if_rows)
    write("flat_if_vars", if_var_rows)
    write("cascades", ifs.cascade_rows(ctx))
    reg_rows = list(routines.registration_rows(ctx))
    write("registrations", reg_rows)

    roots = roots or ([DRIVER_ID] if DRIVER_ID in ctx.sub_dict else list(fut.primary_subroutines))
    trace = StaticTrace(ctx, roots).run()
    write("trace_nodes", [{k: v for k, v in n.items() if k != "guarded"} for n in trace.nodes])
    write("trace_access", trace.accesses)
    filter_rows, relation_rows = filters.derive(trace.filter_sites)
    write("filters", filter_rows)
    write("filter_relations", relation_rows)

    type_parents = {t.type_name: (getattr(t, "parent", None) or "") for t in ctx.type_dict.values()}
    reg_objs = {(s.id, r.ln, r.kind, r.path): r for s in ctx.subs for r in getattr(s, "registrations", []) or []}

    def applies(row, instance) -> bool:
        path = f"{row['base']}%{row['field']}" if row["field"] else row["base"]
        reg = reg_objs.get((row["sub_id"], row["ln"], row["kind"], path))
        return reg.applies_to(instance) if reg is not None else True

    applied = fieldstate.apply_registrations(reg_rows, instances, type_parents, applies)
    node_subs = {n["order"]: n["subroutine"] for n in trace.nodes}
    write("field_state", fieldstate.derive(trace.accesses, applied, node_subs))

    missing = [t for t in TABLES if t not in counts]
    assert not missing, f"tables not written: {missing}"
    snapshot = {
        "label": label,
        "case": case or "",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "e3sm_srcroot": meta.get("e3sm_srcroot", ""),
        "e3sm": meta.get("e3sm", {}),
        "spel": meta.get("spel", {}),
        "analysis_created_at": meta.get("created_at", ""),
        "roots": meta.get("roots", roots),
        "trace_roots": roots,
        "failures": meta.get("failures", {}),
        "incomplete": meta.get("incomplete", {}),
        "stats": {
            "rows": counts,
            "unresolved_calls": trace.unresolved_calls,
            "unresolved_actuals": trace.unresolved_actuals,
            "unresolved_globals": dict(ctx.resolver.unresolved.most_common(50)),
        },
    }
    (out_dir / SNAPSHOT_JSON).write_text(json.dumps(snapshot, indent=2) + "\n")
    log.info(f"Exported snapshot '{label}' to {out_dir}")
    return snapshot
