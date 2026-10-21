"""Module, derived-type and module-variable tables."""

from __future__ import annotations

from pathlib import Path

from spel.scripts.db_export.context import ExportContext, subgrid_of, to_fortran
from spel.scripts.fortran_modules import use_items
from spel.scripts.nml.analyze_namelist import find_all_namelist

NAMELIST_KINDS = ("logical", "integer", "real", "character")


def modules_rows(ctx: ExportContext):
    for name in sorted(ctx.mod_dict):
        fm = ctx.mod_dict[name]
        yield {
            "module": fm.name,
            "filepath": ctx.rel(fm.filepath),
            "ln": fm.ln,
            "end_of_head_ln": fm.end_of_head_ln,
            "default_private": ctx.resolver.scopes.head(fm.name).default_private,
        }


def _routine_at(ctx: ExportContext, fm, ln: int) -> str:
    """sub_id of the innermost routine of module `fm` containing line `ln`."""
    best = None
    for sub_id in fm.subroutines:
        sub = ctx.sub_dict.get(sub_id)
        if sub is None or sub.library:
            continue
        if sub.startline <= ln <= sub.end_stmt_ln:
            if best is None or sub.end_stmt_ln - sub.startline < best.end_stmt_ln - best.startline:
                best = sub
    return best.id if best is not None else ""


def module_dep_rows(ctx: ExportContext):
    for name in sorted(ctx.mod_dict):
        fm = ctx.mod_dict[name]
        for stmt in fm.use_stmts:
            in_head = stmt.lineno < fm.end_of_head_ln
            owner = "" if in_head else _routine_at(ctx, fm, stmt.lineno)
            base = {
                "module": fm.name,
                "dep_module": stmt.module.lower(),
                "ln": stmt.lineno,
                "in_head": in_head,
                "subroutine": owner,
            }
            if stmt.has_only:
                for local, remote in use_items(stmt):
                    yield base | {"whole": False, "local_name": local, "object_used": remote}
            else:
                yield base | {"whole": True, "local_name": "", "object_used": ""}


def user_type_rows(ctx: ExportContext):
    for name in sorted(ctx.type_dict):
        dtype = ctx.type_dict[name]
        yield {
            "module": dtype.declaration,
            "user_type_name": dtype.type_name,
            "parent": getattr(dtype, "parent", None) or "",
        }


def type_def_rows(ctx: ExportContext):
    for name in sorted(ctx.type_dict):
        dtype = ctx.type_dict[name]
        for position, (path, v) in enumerate(dtype.components.items()):
            yield {
                "user_type_name": dtype.type_name,
                "member_name": path,
                "member_type": v.type,
                "dim": v.dim,
                "bounds": v.bounds or "",
                "subgrid": subgrid_of(v),
                "pointer": bool(v.pointer) or bool(getattr(v, "ptrscalar", False)),
                "allocatable": bool(v.allocatable),
                "nested": bool(getattr(v, "nested", False)),
                "position": position,
                "component_type": v.type if v.type in ctx.type_dict else "",
            }


def type_procedure_rows(ctx: ExportContext):
    for name in sorted(ctx.type_dict):
        dtype = ctx.type_dict[name]
        for binding, proc in sorted(getattr(dtype, "procedures", {}).items()):
            if not isinstance(proc, str):
                continue
            sub = ctx.sub_dict.get(proc)
            yield {
                "user_type_name": dtype.type_name,
                "binding": binding,
                "subroutine": sub.id if sub is not None else proc,
            }


def namelist_map(ctx: ExportContext) -> dict[tuple[str, str], str]:
    """(module, variable) -> namelist group, for every namelist variable ELM declares."""
    by_file = {}
    for fm in ctx.mod_dict.values():
        try:
            by_file[Path(fm.filepath).resolve()] = fm.name
        except OSError:
            continue
    out: dict[tuple[str, str], str] = {}
    try:
        nml_dict = find_all_namelist()
    except Exception:  # grep/parse failure: no namelist info rather than no export
        nml_dict = {}
    for name, nml in nml_dict.items():
        mv = None
        mod = by_file.get(Path(nml.filepath).resolve()) if nml.filepath else None
        if mod is not None:
            mv = ctx.resolver.resolve_in_module(mod, name, set())
        if mv is None:
            owners = [m for m, fm in ctx.mod_dict.items() if name in fm.global_vars]
            if len(owners) == 1:
                mv = (owners[0], name)
        if mv is not None:
            out[mv] = nml.group
    return out


def global_rows(ctx: ExportContext):
    """(instance rows, intrinsic global rows) from every module's variables."""
    namelists = namelist_map(ctx)
    instances, globals_ = [], []
    for name in sorted(ctx.mod_dict):
        fm = ctx.mod_dict[name]
        head = ctx.resolver.scopes.head(fm.name)
        for vname, var in fm.global_vars.items():
            if var.type in ctx.type_dict:
                instances.append(
                    {
                        "module": fm.name,
                        "user_type_name": var.type,
                        "instance_name": vname,
                        "public": head.is_public(vname),
                    }
                )
                continue
            group = namelists.get((fm.name, vname), "")
            kind = next((k for k in NAMELIST_KINDS if var.type.lower().startswith(k)), "")
            globals_.append(
                {
                    "module": fm.name,
                    "var_name": vname,
                    "var_type": var.type,
                    "dim": var.dim,
                    "bounds": var.bounds or "",
                    "value": to_fortran(getattr(var, "default_value", None)),
                    "parameter": bool(var.parameter),
                    "pointer": bool(var.pointer) or bool(getattr(var, "ptrscalar", False)),
                    "public": head.is_public(vname),
                    "protected": head.is_protected(vname),
                    "namelist_group": group,
                    "namelist_kind": kind if group else "",
                }
            )
    return instances, globals_
