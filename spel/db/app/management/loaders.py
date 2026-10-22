"""
Load a `spel export` directory into the database as one Snapshot.

Each CSV is read, its header checked against spel.scripts.db_export.schema.TABLES,
and its rows bulk-inserted; foreign keys are resolved in memory from the
natural keys the CSVs carry (module names, `module::sub` ids, component paths,
trace order). Nothing relies on bulk_create returning primary keys.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from django.db import connection, transaction
from django.utils import timezone

from spel.scripts.db_export.csv_io import read_table
from spel.scripts.db_export.schema import SNAPSHOT_JSON, TABLES

from ..models import (
    ArgAccess,
    CallsiteBinding,
    CascadeDependence,
    CascadePair,
    FieldState,
    FlatIf,
    FlatIFCascadeVar,
    FlatIfNamelistVar,
    IntrinsicGlobals,
    ModuleDependency,
    Modules,
    NamelistVariable,
    PropagatedEffectByLn,
    Registration,
    Snapshot,
    SubroutineActiveGlobalVars,
    SubroutineArgs,
    SubroutineCalltree,
    SubroutineCode,
    SubroutineIntrinsicGlobals,
    SubroutineLocalArrays,
    Subroutines,
    TraceAccess,
    FilterSet,
    FilterRelation,
    TraceNode,
    TypeDefinitions,
    TypeProcedure,
    UserTypeInstances,
    UserTypes,
)


def _bool(v: str) -> bool:
    return v in ("1", "True", "true")


def _int(v: str, default: Optional[int] = None) -> Optional[int]:
    return int(v) if v not in ("", None) else default


def _dt(v: str):
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    return dt if dt.tzinfo else timezone.make_aware(dt)


class SnapshotLoader:
    def __init__(
        self,
        directory: Path,
        label: Optional[str] = None,
        replace: bool = False,
        batch_size: int = 2000,
        log: Callable[[str], None] = print,
    ):
        self.dir = Path(directory)
        self.meta = json.loads((self.dir / SNAPSHOT_JSON).read_text())
        self.label = label or self.meta["label"]
        self.replace = replace
        self.batch = batch_size
        self.log = log
        self.counts: dict[str, int] = {}
        self.overrides: dict[tuple, tuple[str, str]] = {}

    # --- helpers ---
    def rows(self, table: str) -> list[dict]:
        path = self.dir / f"{table}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"{path} missing (export is incomplete)")
        return read_table(path)

    def bulk(self, model, objs: list, table: str) -> None:
        model.objects.bulk_create(objs, batch_size=self.batch)
        self.counts[table] = self.counts.get(table, 0) + len(objs)
        self.log(f"  {table}: {len(objs)} rows")

    def _ids(self, qs, *fields):
        return {tuple(row[:-1]) if len(fields) > 1 else row[0]: row[-1] for row in qs.values_list(*fields, "pk")}

    # --- main ---
    def load(self) -> Snapshot:
        for table in TABLES:
            if not (self.dir / f"{table}.csv").is_file():
                raise FileNotFoundError(f"{self.dir / (table + '.csv')} missing")
        if connection.vendor == "sqlite":
            try:
                with connection.cursor() as cur:
                    cur.execute("PRAGMA synchronous=OFF")
            except Exception:  # inside an outer transaction (tests): keep the default
                pass
        with transaction.atomic():
            old = Snapshot.objects.filter(label=self.label).first()
            if old is not None:
                if not self.replace:
                    raise ValueError(f"snapshot '{self.label}' exists; use --replace to reload it")
                self._stash_overrides(old)
                self.log(f"Deleting snapshot '{self.label}' ...")
                old.delete()
            snap = self._snapshot()
            self._structure(snap)
            self._routines(snap)
            self._module_deps(snap)
            self._accesses(snap)
            self._ifs(snap)
            self._registrations(snap)
            self._trace(snap)
            snap.loaded_at = timezone.now()
            snap.stats = (self.meta.get("stats") or {}) | {"loaded_rows": self.counts}
            snap.save(update_fields=["loaded_at", "stats"])
        return snap

    def _stash_overrides(self, old: Snapshot) -> None:
        qs = FieldState.objects.filter(snapshot=old).exclude(override="").select_related(
            "instance", "instance__inst_module", "member", "global_var", "global_var__gv_module"
        )
        for fs in qs:
            if fs.instance_id:
                key = ("inst", fs.instance.inst_module.module_name, fs.instance.instance_name, fs.member.member_name)
            else:
                key = ("glob", fs.global_var.gv_module.module_name, fs.global_var.var_name)
            self.overrides[key] = (fs.override, fs.override_note)

    def _snapshot(self) -> Snapshot:
        m = self.meta
        e3sm, spel = m.get("e3sm", {}) or {}, m.get("spel", {}) or {}
        return Snapshot.objects.create(
            label=self.label,
            srcroot=m.get("e3sm_srcroot", ""),
            e3sm_commit=e3sm.get("commit") or "",
            e3sm_branch=e3sm.get("branch") or "",
            elm_diff=e3sm.get("elm_diff") or "",
            spel_commit=spel.get("commit") or "",
            spel_branch=spel.get("branch") or "",
            analysis_created_at=_dt(m.get("analysis_created_at", "")),
            exported_at=_dt(m.get("exported_at", "")),
            case=m.get("case", "") or "",
            roots=m.get("roots", []),
            trace_roots=m.get("trace_roots", []),
            failures=m.get("failures", {}) or {},
            incomplete=m.get("incomplete", {}) or {},
        )

    # --- modules, types, globals ---
    def _structure(self, snap: Snapshot) -> None:
        self.bulk(Modules, [
            Modules(snapshot=snap, module_name=r["module"], filepath=r["filepath"], ln=_int(r["ln"], 0),
                    end_of_head_ln=_int(r["end_of_head_ln"], 0), default_private=_bool(r["default_private"]))
            for r in self.rows("modules")
        ], "modules")
        self.mod = self._ids(Modules.objects.filter(snapshot=snap), "module_name")

        types = self.rows("user_types")
        self.bulk(UserTypes, [
            UserTypes(snapshot=snap, module_id=self.mod[r["module"]], user_type_name=r["user_type_name"])
            for r in types if r["module"] in self.mod
        ], "user_types")
        self.utype = self._ids(UserTypes.objects.filter(snapshot=snap), "user_type_name")
        parents = [UserTypes(pk=self.utype[r["user_type_name"]], parent_id=self.utype[r["parent"]])
                   for r in types if r["parent"] in self.utype and r["user_type_name"] in self.utype]
        if parents:
            UserTypes.objects.bulk_update(parents, ["parent"], batch_size=self.batch)
        type_module = {r["user_type_name"]: r["module"] for r in types}

        self.bulk(TypeDefinitions, [
            TypeDefinitions(
                type_module_id=self.mod[type_module[r["user_type_name"]]],
                user_type_id=self.utype[r["user_type_name"]], member_type=r["member_type"],
                member_name=r["member_name"], dim=_int(r["dim"], 0), bounds=r["bounds"],
                subgrid=r["subgrid"], pointer=_bool(r["pointer"]), allocatable=_bool(r["allocatable"]),
                nested=_bool(r["nested"]), position=_int(r["position"], 0),
                component_type_id=self.utype.get(r["component_type"]),
            )
            for r in self.rows("type_defs") if r["user_type_name"] in self.utype
        ], "type_defs")
        self.member = self._ids(TypeDefinitions.objects.filter(user_type__snapshot=snap), "user_type_id", "member_name")

        self.bulk(UserTypeInstances, [
            UserTypeInstances(inst_module_id=self.mod[r["module"]], instance_type_id=self.utype[r["user_type_name"]],
                              instance_name=r["instance_name"], public=_bool(r["public"]))
            for r in self.rows("user_type_instances") if r["module"] in self.mod and r["user_type_name"] in self.utype
        ], "user_type_instances")
        self.inst = self._ids(UserTypeInstances.objects.filter(inst_module__snapshot=snap), "inst_module__module_name", "instance_name")
        self.inst_type = dict(UserTypeInstances.objects.filter(inst_module__snapshot=snap).values_list("pk", "instance_type_id"))
        self.inst_by_name: dict[str, list[int]] = defaultdict(list)
        for (mod, name), pk in self.inst.items():
            self.inst_by_name[name].append(pk)

        globals_rows = self.rows("intrinsic_globals")
        self.bulk(IntrinsicGlobals, [
            IntrinsicGlobals(snapshot=snap, gv_module_id=self.mod[r["module"]], dim=_int(r["dim"], 0),
                             var_type=r["var_type"], var_name=r["var_name"], bounds=r["bounds"], value=r["value"],
                             parameter=_bool(r["parameter"]), pointer=_bool(r["pointer"]), public=_bool(r["public"]),
                             protected=_bool(r["protected"]), namelist_group=r["namelist_group"],
                             namelist_kind=r["namelist_kind"])
            for r in globals_rows if r["module"] in self.mod
        ], "intrinsic_globals")
        self.gvar = self._ids(IntrinsicGlobals.objects.filter(snapshot=snap), "gv_module__module_name", "var_name")
        self.bulk(NamelistVariable, [
            NamelistVariable(active_var_id_id=self.gvar[(r["module"], r["var_name"])])
            for r in globals_rows if r["namelist_group"] and (r["module"], r["var_name"]) in self.gvar
        ], "namelist_variables")
        self.nml = self._ids(NamelistVariable.objects.filter(active_var_id__snapshot=snap), "active_var_id_id")

    def _namelist_var(self, mv: tuple[str, str]) -> Optional[int]:
        """NamelistVariable pk for a (module, name), created on demand (a gate's variable may lack a group)."""
        gid = self.gvar.get(mv)
        if gid is None:
            return None
        if gid not in self.nml:
            self.nml[gid] = NamelistVariable.objects.create(active_var_id_id=gid).pk
        return self.nml[gid]

    # --- routines ---
    def _routines(self, snap: Snapshot) -> None:
        subs = self.rows("subroutines")
        self.bulk(Subroutines, [
            Subroutines(snapshot=snap, subroutine_name=r["subroutine"], sub_id=r["sub_id"],
                        module_id=self.mod.get(r["module"]), is_function=_bool(r["is_function"]),
                        return_type=r["return_type"], result_name=r["result_name"], filepath=r["filepath"],
                        startline=_int(r["startline"], -1), endline=_int(r["endline"], -1),
                        end_stmt_ln=_int(r["end_stmt_ln"], -1), library=_bool(r["library"]),
                        is_internal=_bool(r["is_internal"]), analyzed=_bool(r["analyzed"]),
                        failure=r["failure"], incomplete=r["incomplete"])
            for r in subs
        ], "subroutines")
        self.sub = self._ids(Subroutines.objects.filter(snapshot=snap), "sub_id")
        hosts = [Subroutines(pk=self.sub[r["sub_id"]], host_id=self.sub[r["host"]]) for r in subs if r["host"] in self.sub]
        if hosts:
            Subroutines.objects.bulk_update(hosts, ["host"], batch_size=self.batch)

        self.bulk(SubroutineCode, [
            SubroutineCode(subroutine_id=self.sub[r["sub_id"]], startline=_int(r["startline"], 0),
                           n_lines=_int(r["n_lines"], 0), text=r["text"])
            for r in self.rows("subroutine_code") if r["sub_id"] in self.sub
        ], "subroutine_code")

        self.bulk(TypeProcedure, [
            TypeProcedure(user_type_id=self.utype[r["user_type_name"]], binding=r["binding"],
                          subroutine_id=self.sub.get(r["subroutine"]))
            for r in self.rows("type_procedures") if r["user_type_name"] in self.utype
        ], "type_procedures")

        self.bulk(SubroutineArgs, [
            SubroutineArgs(subroutine_id=self.sub[r["sub_id"]], position=_int(r["position"], 0), arg_type=r["arg_type"],
                           arg_name=r["arg_name"], dim=_int(r["dim"], 0), intent=r["intent"],
                           optional=_bool(r["optional"]), user_type_id=self.utype.get(r["user_type"]))
            for r in self.rows("subroutine_args") if r["sub_id"] in self.sub
        ], "subroutine_args")
        self.arg = self._ids(SubroutineArgs.objects.filter(subroutine__snapshot=snap), "subroutine_id", "arg_name")

        self.bulk(SubroutineLocalArrays, [
            SubroutineLocalArrays(subroutine_id=self.sub[r["sub_id"]], array_name=r["array_name"], type=r["type"],
                                  dim=_int(r["dim"], 0))
            for r in self.rows("subroutine_local_arrays") if r["sub_id"] in self.sub
        ], "subroutine_local_arrays")
        self.local = self._ids(SubroutineLocalArrays.objects.filter(subroutine__snapshot=snap), "subroutine_id", "array_name")

        self.bulk(SubroutineCalltree, [
            SubroutineCalltree(parent_subroutine_id=self.sub[r["parent"]], child_subroutine_id=self.sub.get(r["child"]),
                               lineno=_int(r["ln"]), position=_int(r["position"], 0), callee_name=r["callee_name"],
                               kind=r["kind"], passed_object=r["passed_object"])
            for r in self.rows("subroutine_calltree") if r["parent"] in self.sub
        ], "subroutine_calltree")
        self.call = self._ids(SubroutineCalltree.objects.filter(parent_subroutine__snapshot=snap),
                              "parent_subroutine_id", "lineno", "position")
        self.call_child = dict(SubroutineCalltree.objects.filter(parent_subroutine__snapshot=snap)
                               .values_list("pk", "child_subroutine_id"))

        binds = []
        for r in self.rows("call_bindings"):
            parent = self.sub.get(r["parent"])
            call = self.call.get((parent, _int(r["ln"]), _int(r["position"], 0))) if parent else None
            if call is None:
                continue
            child = self.call_child.get(call)
            base = r["actual"].split("%")[0]
            origin = r["origin"]
            insts = self.inst_by_name.get(base, []) if origin in ("global", "external") else []
            binds.append(CallsiteBinding(
                parent_subroutine_id=parent, call_id=call, argn=_int(r["argn"], 0),
                dummy_arg_id=self.arg.get((child, r["dummy_arg"])) if child else None,
                dummy_name=r["dummy_arg"], actual=r["actual"], origin=origin, keyword=r["keyword"],
                from_elmtype_id=insts[0] if len(insts) == 1 else None,
                from_arg_id=self.arg.get((parent, base)) if origin == "dummy" else None,
                from_local_id=self.local.get((parent, base)) if origin == "local" else None,
            ))
        self.bulk(CallsiteBinding, binds, "call_bindings")

    # --- accesses ---
    def _inst_member(self, r: dict) -> tuple[Optional[int], Optional[int]]:
        inst = self.inst.get((r.get("inst_module", ""), r.get("instance", "")))
        if inst is None:
            return None, None
        member = self.member.get((self.inst_type[inst], r.get("member", ""))) if r.get("member") else None
        return inst, member

    def _module_deps(self, snap: Snapshot) -> None:
        objs = []
        for r in self.rows("module_deps"):
            mod = self.mod.get(r["module"])
            if mod is None:
                continue
            objs.append(ModuleDependency(
                module_id=mod, dep_module_id=self.mod.get(r["dep_module"]), dep_module_name=r["dep_module"],
                object_used=r["object_used"], local_name=r["local_name"], ln=_int(r["ln"], -1), whole=_bool(r["whole"]),
                in_head=_bool(r["in_head"]), subroutine_id=self.sub.get(r["subroutine"]) if r["subroutine"] else None,
            ))
        self.bulk(ModuleDependency, objs, "module_deps")

    def _accesses(self, snap: Snapshot) -> None:
        objs = []
        for r in self.rows("active_dtype_vars"):
            sub = self.sub.get(r["sub_id"])
            if sub is None:
                continue
            inst, member = self._inst_member(r)
            objs.append(SubroutineActiveGlobalVars(subroutine_id=sub, instance_id=inst, member_id=member,
                                                   path=r["path"], status=r["status"], ln=_int(r["ln"], -1)))
        self.bulk(SubroutineActiveGlobalVars, objs, "active_dtype_vars")

        self.bulk(SubroutineIntrinsicGlobals, [
            SubroutineIntrinsicGlobals(sub_id_id=self.sub[r["sub_id"]], gv_id_id=self.gvar.get((r["var_module"], r["var_name"])),
                                       path=r["path"], status=r["status"], gv_ln=_int(r["ln"], -1))
            for r in self.rows("intrinsic_access") if r["sub_id"] in self.sub
        ], "intrinsic_access")

        objs = []
        for r in self.rows("arg_access"):
            sub = self.sub.get(r["sub_id"])
            arg = self.arg.get((sub, r["dummy_arg"])) if sub else None
            if arg is None:
                continue
            objs.append(ArgAccess(subroutine_id=sub, arg_id=arg, ln=_int(r["ln"]), status=r["status"],
                                  member_path=r["member_path"]))
        self.bulk(ArgAccess, objs, "arg_access")

        objs = []
        for r in self.rows("propagated_access"):
            sub = self.sub.get(r["sub_id"])
            if sub is None:
                continue
            inst, member = self._inst_member(r)
            call = self.call.get((sub, _int(r["ln"]), _int(r["position"], 0))) if r["position"] != "" else None
            objs.append(PropagatedEffectByLn(
                subroutine_id=sub, call_site_id=call, lineno=_int(r["ln"]), kind=r["kind"], instance_id=inst,
                member_id=member, global_var_id=self.gvar.get((r["var_module"], r["var_name"])),
                path=r["path"], status=r["status"]))
        self.bulk(PropagatedEffectByLn, objs, "propagated_access")

    # --- namelist ifs ---
    def _ifs(self, snap: Snapshot) -> None:
        objs = []
        for r in self.rows("nml_ifs"):
            sub = self.sub.get(r["sub_id"])
            if sub is None:
                continue
            cond = None
            if r["condition"]:
                try:
                    cond = json.loads(r["condition"])
                except json.JSONDecodeError:
                    cond = None
            objs.append(FlatIf(subroutine_id=sub, position=_int(r["position"], 0), start_ln=_int(r["start_ln"]),
                               end_ln=_int(r["end_ln"]), kind=r["kind"], condition=cond,
                               condition_text=r["condition_text"], nml_gated=_bool(r["nml_gated"])))
        self.bulk(FlatIf, objs, "nml_ifs")
        self.flatif = self._ids(FlatIf.objects.filter(subroutine__snapshot=snap), "subroutine_id", "position")

        cascades: dict[str, int] = {}  # cascade var -> its first dependence (if links)
        dependences: dict[tuple[str, int], int] = {}  # (cascade var, trigger) -> dependence
        rows = self.rows("cascades")
        # a pair whose trigger isn't a namelist variable of this snapshot can never match: drop it whole
        missing = {(r["cascade_var"], r["pair"]) for r in rows
                   if self._namelist_var((r["trigger_module"], r["trigger_name"])) is None}
        pairs = []
        for r in rows:
            if (r["cascade_var"], r["pair"]) in missing:
                continue
            trig = self._namelist_var((r["trigger_module"], r["trigger_name"]))
            key = (r["cascade_var"], trig)
            if key not in dependences:
                dependences[key] = CascadeDependence.objects.create(
                    snapshot=snap, cascade_var=r["cascade_var"], trigger_var_id=trig).pk
                cascades.setdefault(r["cascade_var"], dependences[key])
            pairs.append(CascadePair(dependence_id=dependences[key], pair_key=_int(r["pair"], 0),
                                     nml_val=r["nml_val"], cascade_val=r["cascade_val"]))
        self.counts["cascades"] = len(cascades)
        self.bulk(CascadePair, pairs, "cascade_pairs")

        nml_links, casc_links, seen = [], [], set()
        for r in self.rows("flat_if_vars"):
            sub = self.sub.get(r["sub_id"])
            fi = self.flatif.get((sub, _int(r["position"], 0))) if sub else None
            if fi is None:
                continue
            if r["role"] == "nml":
                nv = self._namelist_var((r["var_module"], r["var_name"]))
                if nv is not None and (fi, nv) not in seen:
                    seen.add((fi, nv))
                    nml_links.append(FlatIfNamelistVar(flatif_id=fi, namelist_var_id=nv))
            elif r["var_name"] in cascades and (fi, "c", r["var_name"]) not in seen:
                seen.add((fi, "c", r["var_name"]))
                casc_links.append(FlatIFCascadeVar(flatif_cv_id=fi, cascade_id=cascades[r["var_name"]]))
        self.bulk(FlatIfNamelistVar, nml_links, "flat_if_namelist")
        self.bulk(FlatIFCascadeVar, casc_links, "flat_if_cascade")

    # --- registrations ---
    def _registrations(self, snap: Snapshot) -> None:
        objs = []
        for r in self.rows("registrations"):
            sub = self.sub.get(r["sub_id"])
            if sub is None:
                continue
            utype = self.utype.get(r["user_type"])
            member = None
            inst = None
            if utype is not None:
                member = self.member.get((utype, r["member"])) if r["member"] else None
            else:
                inst, member = self._inst_member(r)
            objs.append(Registration(
                snapshot=snap, kind=r["kind"], subroutine_id=sub, ln=_int(r["ln"]), base=r["base"], field=r["field"],
                user_type_id=utype, member_id=member, instance_id=inst,
                global_var_id=self.gvar.get((r["var_module"], r["var_name"])), name=r["name"][:255],
                long_name=r["long_name"][:255], units=r["units"][:128], guards=json.loads(r["guards"] or "[]"),
                inactive=_bool(r["inactive"])))
        self.bulk(Registration, objs, "registrations")

    # --- trace and field state ---
    def _trace(self, snap: Snapshot) -> None:
        rows = self.rows("trace_nodes")
        objs = []
        for r in rows:
            sub = self.sub.get(r["subroutine"])
            caller = self.sub.get(r["caller"]) if r["caller"] else None
            call = self.call.get((caller, _int(r["call_ln"]), _int(r["call_position"], 0))) if caller and r["call_ln"] != "" else None
            objs.append(TraceNode(snapshot=snap, order=_int(r["order"]), call_site_id=call, subroutine_id=sub,
                                  depth=_int(r["depth"], 0), size=_int(r["size"], 1), cut=_bool(r["cut"]),
                                  analyzed=_bool(r["analyzed"])))
        objs = [o for o in objs if o.subroutine_id is not None]
        self.bulk(TraceNode, objs, "trace_nodes")
        self.node = self._ids(TraceNode.objects.filter(snapshot=snap), "order")
        parents = [TraceNode(pk=self.node[_int(r["order"])], parent_id=self.node[_int(r["parent_order"])])
                   for r in rows if r["parent_order"] != "" and _int(r["order"]) in self.node and _int(r["parent_order"]) in self.node]
        if parents:
            TraceNode.objects.bulk_update(parents, ["parent"], batch_size=self.batch)

        objs = []
        for r in self.rows("trace_access"):
            node = self.node.get(_int(r["node_order"]))
            if node is None:
                continue
            inst, member = self._inst_member(r)
            objs.append(TraceAccess(snapshot=snap, trace_node_id=node, instance_id=inst, member_id=member,
                                    global_var_id=self.gvar.get((r["var_module"], r["var_name"])), path=r["path"],
                                    status=r["status"], ln=_int(r["ln"]), order=_int(r["order"]),
                                    resolved_from=r["resolved_from"], conditional=_bool(r["conditional"]),
                                    index_kind=r.get("index_kind", ""), filter=r.get("filter", "")))
        self.bulk(TraceAccess, objs, "trace_access")

        objs = [FilterSet(snapshot=snap, name=r["name"], subroutine_id=self.sub.get(r["subroutine"]), ln=_int(r["ln"], 0),
                          level=r["level"], parent=r["parent"], guards=r["guards"]) for r in self.rows("filters")]
        self.bulk(FilterSet, objs, "filters")
        objs = [FilterRelation(snapshot=snap, filter_a=r["filter_a"], filter_b=r["filter_b"], relation=r["relation"],
                               source=r["source"], subroutine_id=self.sub.get(r["subroutine"]) if r["subroutine"] else None,
                               condition=r["condition"]) for r in self.rows("filter_relations")]
        self.bulk(FilterRelation, objs, "filter_relations")

        objs = []
        for r in self.rows("field_state"):
            inst, member = self._inst_member(r)
            gvar = self.gvar.get((r["var_module"], r["var_name"])) if r["var_name"] else None
            if inst is not None and member is None:
                continue
            if inst is None and gvar is None:
                continue
            key = (("inst", r["inst_module"], r["instance"], r["member"]) if inst is not None
                   else ("glob", r["var_module"], r["var_name"]))
            override, note = self.overrides.get(key, ("", ""))
            objs.append(FieldState(
                snapshot=snap, instance_id=inst, member_id=member, global_var_id=gvar,
                restart=_bool(r["restart"]), history=_bool(r["history"]), history_active=_bool(r["history_active"]),
                first_status=r["first_status"], first_trace_node_id=self.node.get(_int(r["first_node_order"], -1)),
                first_ln=_int(r["first_ln"]), read_in_step=_bool(r["read_in_step"]),
                written_in_step=_bool(r["written_in_step"]), n_reads=_int(r["n_reads"], 0),
                n_writes=_int(r["n_writes"], 0), n_routines=_int(r["n_routines"], 0), category=r["category"],
                restart_unneeded=_bool(r["restart_unneeded"]), restart_missing=_bool(r["restart_missing"]),
                override=override, override_note=note))
        self.bulk(FieldState, objs, "field_state")
