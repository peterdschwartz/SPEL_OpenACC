"""Subroutine tables: identity, code, arguments, calls, bindings, accesses, registrations."""

from __future__ import annotations

import json

from spel.scripts.db_export.context import ExportContext, canonical_summary
from spel.scripts.db_export.resolve import var_columns

INTENT = {"r": "in", "w": "out", "rw": "inout"}


def subroutine_rows(ctx: ExportContext):
    failures = ctx.meta.get("failures", {}) or {}
    incomplete = ctx.meta.get("incomplete", {}) or {}
    for sub in ctx.subs:
        lib = bool(sub.library)
        yield {
            "module": "" if lib else sub.module,
            "subroutine": sub.name,
            "sub_id": sub.id,
            "is_function": bool(getattr(sub, "func", False)),
            "return_type": getattr(sub, "return_type", "") or "",
            "result_name": getattr(sub, "result_name", "") or "",
            "filepath": "" if lib else ctx.rel(sub.filepath),
            "startline": -1 if lib else sub.startline,
            "endline": -1 if lib else sub.endline,
            "end_stmt_ln": -1 if lib else sub.end_stmt_ln,
            "library": lib,
            "is_internal": bool(getattr(sub, "is_internal", False)),
            "host": getattr(sub, "host_id", None) or "",
            "analyzed": sub.record is not None,
            "failure": str(failures.get(sub.id, "")),
            "incomplete": ";".join(incomplete.get(sub.id, [])),
        }


def code_rows(ctx: ExportContext):
    for sub in ctx.subs:
        if sub.library:
            continue
        src = ctx.source_lines(sub.filepath)
        if src is None:
            continue
        lines = src[sub.startline : sub.end_stmt_ln + 1]
        yield {
            "sub_id": sub.id,
            "startline": sub.startline,
            "n_lines": len(lines),
            "text": "\n".join(lines),
        }


def arg_rows(ctx: ExportContext):
    for sub in ctx.subs:
        decls = sub.record.declarations if sub.record is not None else {}
        for position, name in enumerate(sub.dummy_args_list):
            var = sub.arguments.get(name)
            decl = decls.get(name)
            if decl is not None:
                intent, vtype, dim = decl.intent or "", decl.type, decl.dim
                optional = "optional" in decl.attrs
            elif var is not None:
                intent, vtype, dim = INTENT.get(var.intent, ""), var.type, var.dim
                optional = bool(var.optional)
            else:
                intent, vtype, dim, optional = "", "", 0, False
            base_type = vtype.lower().replace("class(", "").replace("type(", "").rstrip(")")
            yield {
                "sub_id": sub.id,
                "position": position,
                "arg_name": name,
                "arg_type": vtype,
                "dim": dim,
                "intent": intent,
                "optional": optional,
                "user_type": base_type if base_type in ctx.type_dict else "",
            }


def local_array_rows(ctx: ExportContext):
    for sub in ctx.subs:
        if sub.record is None:
            continue
        for name, decl in sub.record.local_variables.items():
            if decl.dim > 0:
                yield {"sub_id": sub.id, "array_name": name, "type": decl.type, "dim": decl.dim}


def calltree_rows(ctx: ExportContext):
    for sub in ctx.subs:
        for c in ctx.calls(sub):
            yield {
                "parent": sub.id,
                "ln": c.ln,
                "position": c.position,
                "callee_name": c.name,
                "kind": c.kind,
                "passed_object": c.passed_object,
                "child": c.callee.id if c.callee is not None else "",
            }


def binding_rows(ctx: ExportContext):
    for sub in ctx.subs:
        for (ln, callee_id), binds in ctx.bindings(sub).items():
            position = ctx.call_position(sub, ln, callee_id)
            for b in binds:
                yield {
                    "parent": sub.id,
                    "ln": ln,
                    "position": position,
                    "argn": b.argn,
                    "dummy_arg": b.dummy,
                    "actual": b.actual,
                    "origin": b.origin.name.lower(),
                    "keyword": "",
                }


def access_rows(ctx: ExportContext):
    """(active_dtype_vars, intrinsic_access, arg_access, propagated_access) rows."""
    dtype_rows, intr_rows, arg_rows_, prop_rows = [], [], [], []
    for sub in ctx.subs:
        maps = sub.record_access
        if maps is None:
            continue
        for path, rws in list(maps.elmtype.items()) + list(maps.globals.items()):
            info = ctx.resolver.split(sub, path)
            cols = var_columns(info, path)
            for rw in rws:
                if info is not None and info["dtype"] is not None:
                    dtype_rows.append(
                        {"sub_id": sub.id, "path": path, "inst_module": cols["inst_module"],
                         "instance": cols["instance"], "member": cols["member"],
                         "status": rw.status, "ln": rw.ln}
                    )
                else:
                    intr_rows.append(
                        {"sub_id": sub.id, "path": path, "var_module": cols["var_module"],
                         "var_name": cols["var_name"], "status": rw.status, "ln": rw.ln}
                    )
        for path, rws in maps.args.items():
            dummy, _, rest = path.partition("%")
            for rw in rws:
                arg_rows_.append(
                    {"sub_id": sub.id, "dummy_arg": dummy, "member_path": rest,
                     "status": rw.status, "ln": rw.ln}
                )
        # callee accesses at the call line (transitive), resolved in the callee's scope
        for c in ctx.calls(sub):
            callee = c.callee
            if callee is None or callee.library or callee.record is None:
                continue
            for canon, status in canonical_summary(ctx, callee).items():
                info = ctx.resolver.describe_canonical(canon)
                cols = var_columns(info, canon)
                prop_rows.append(
                    {"sub_id": sub.id, "ln": c.ln, "position": c.position,
                     "kind": "elmtype" if info["dtype"] is not None else "global",
                     "status": status} | cols
                )
    return dtype_rows, intr_rows, arg_rows_, prop_rows


def registration_rows(ctx: ExportContext):
    """One row per registration; `this`-based ones carry the type, others the variable."""
    for sub in ctx.subs:
        for r in getattr(sub, "registrations", []) or []:
            row = {
                "sub_id": sub.id, "ln": r.ln, "kind": r.kind, "base": r.base, "field": r.field,
                "user_type": "", "inst_module": "", "instance": "", "member": "",
                "var_module": "", "var_name": "", "name": r.name, "long_name": r.long_name,
                "units": r.units, "guards": json.dumps([str(g) for g in r.guards]),
                "inactive": bool(r.inactive),
            }
            var = sub.arguments.get(r.base)
            if var is not None:  # registered through a dummy (`this`)
                base_type = var.type.lower().replace("class(", "").replace("type(", "").rstrip(")")
                dtype = ctx.type_dict.get(base_type)
                if dtype is not None:
                    row["user_type"] = dtype.type_name
                    row["member"] = ctx.resolver.member(dtype, r.field.split("%")) if r.field else ""
                yield row
                continue
            info = ctx.resolver.split(sub, r.path)
            if info is None:
                yield row  # unresolved base: kept for the record, no variable link
                continue
            cols = var_columns(info, r.path)
            for k in ("inst_module", "instance", "member", "var_module", "var_name"):
                row[k] = cols[k]
            yield row
