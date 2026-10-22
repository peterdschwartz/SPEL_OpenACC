"""Namelist-conditional tables: flat if blocks, their namelist/cascade variables, cascades."""

from __future__ import annotations

import json

from spel.scripts.db_export.context import ExportContext
from spel.scripts.nml.namelist_cascade import NML_CASCADES


def _condition_json(cond) -> str:
    try:
        return json.dumps(cond.to_dict())
    except Exception:
        return ""


def flat_if_rows(ctx: ExportContext):
    """(nml_ifs rows, flat_if_vars rows)."""
    if_rows, var_rows = [], []
    for sub in ctx.subs:
        for position, f in enumerate(getattr(sub, "flat_ifs", []) or []):
            end_ln = f.end_ln if f.end_ln >= 0 else f.start_ln
            gated = bool(f.nml_vars or f.nml_cascades)
            if_rows.append(
                {
                    "sub_id": sub.id,
                    "position": position,
                    "start_ln": f.start_ln,
                    "end_ln": end_ln,
                    "kind": f.kind.name,
                    "condition": _condition_json(f.condition),
                    "condition_text": str(f.condition),
                    "nml_gated": gated,
                }
            )
            if not gated:
                continue
            for name, nml in f.nml_vars.items():
                var = getattr(nml, "variable", None)
                if var is not None and var.declaration:
                    mv = (var.declaration, name)
                else:
                    mv = ctx.resolver.resolve(sub, name)
                if mv is None:
                    continue
                var_rows.append(
                    {"sub_id": sub.id, "position": position, "role": "nml",
                     "var_module": mv[0], "var_name": mv[1]}
                )
            for name, dep in f.nml_cascades.items():
                var_rows.append(
                    {"sub_id": sub.id, "position": position, "role": "cascade",
                     "var_module": "", "var_name": dep.var}
                )
    return if_rows, var_rows


def cascade_rows(ctx: ExportContext):
    """
    One row per (pair, trigger): a pair applies when every row with its `pair`
    number matches, so a cascade on several namelist variables is several rows.
    """
    for name, dep in NML_CASCADES.items():
        for n, pair in enumerate(dep.pairs):
            for trigger, value in zip(dep.all_triggers(), dep.pair_values(pair)):
                module, _, trigger_name = trigger.partition("::")
                yield {
                    "cascade_var": dep.var,
                    "pair": n,
                    "trigger_module": module,
                    "trigger_name": trigger_name,
                    "nml_val": value,
                    "cascade_val": pair.cascade_val,
                }
