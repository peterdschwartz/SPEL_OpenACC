"""Database export (spel/scripts/db_export): resolution, step trace, field state, CSV contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from spel.scripts.db_export import fieldstate
from spel.scripts.db_export.context import ExportContext
from spel.scripts.db_export.csv_io import read_table, write_table
from spel.scripts.db_export.schema import TABLES
from spel.scripts.db_export.snapshot import export_snapshot
from spel.scripts.db_export.trace import StaticTrace
from spel.scripts.DerivedType import DerivedType
from spel.scripts.fortran_modules import FortranModule, parse_use_stmts
from spel.scripts.fortran_parser.symbols import Origin, Symbol, SymbolKind
from spel.scripts.fortran_parser.tests.test_scope_walk import gvar, walk
from spel.scripts.types import LineTuple
from spel.scripts.utilityFunctions import Variable

MOD = "m"


def proc(name):
    return Symbol(name, SymbolKind.PROCEDURE, Origin.GLOBAL, target=f"{MOD}::{name}")


GLOBALS = [gvar("r8"), gvar("col_ws"), gvar("spval"), gvar("nstep"), proc("root"), proc("child"), proc("leaf"), proc("gchild")]


class Sub:
    """The parts of Subroutine the exporter reads, from a snippet (header on line 1)."""

    def __init__(self, txt, start=0):
        self.record = walk(txt, globals=GLOBALS)
        self.name = self.record.name
        self.module = MOD
        self.id = f"{MOD}::{self.name}"
        self.library = False
        self.is_internal = False
        self.host_id = None
        self.host = None
        self.sub_call_desc = {}
        self.sub_lines = []
        self.record_access = None
        self.startline = start
        self.end_stmt_ln = start + txt.count("\n")
        self.endline = self.end_stmt_ln
        self.active_global_vars = {}
        self.registrations = []
        self.flat_ifs = []
        self.func = False
        self.filepath = Path("/nonexistent/m.F90")
        self.dummy_args_list = [d.name for d in self.record.dummy_args]
        self.arguments = {d.name: SimpleNamespace(type=d.type, intent=None, dim=d.dim, optional=False) for d in self.record.dummy_args}

    def walk_syntax_tree(self, scopes):
        return self.record


ROOT = """
subroutine root()
  implicit none
  integer :: c
  real(r8) :: tmp
  do c = 1, 10
    tmp = col_ws%h2osno(c)
    call child(col_ws%h2osoi_liq(c, 1), tmp)
    col_ws%h2osno(c) = col_ws%h2osno(c) + spval
  end do
  nstep = nstep + 1
  call leaf(col_ws%qflx(c))
end subroutine root
"""

CHILD = """
subroutine child(a, b)
  implicit none
  real(r8), intent(inout) :: a
  real(r8), intent(in) :: b
  a = a + b
  call gchild(a)
end subroutine child
"""

GCHILD = """
subroutine gchild(x)
  implicit none
  real(r8), intent(out) :: x
  x = 0.0_r8
  call child(x, x)
end subroutine gchild
"""

LEAF = """
subroutine leaf(q)
  implicit none
  real(r8), intent(out) :: q
  q = 1.0_r8
end subroutine leaf
"""


@pytest.fixture
def analysis(tmp_path):
    from spel.scripts.record_access import AccessMapper

    subs = {s.id: s for s in (Sub(ROOT, 1), Sub(CHILD, 20), Sub(GCHILD, 30), Sub(LEAF, 40))}
    mapper = AccessMapper(subs)
    for s in subs.values():
        mapper.maps(s)
    f = tmp_path / "m.F90"
    f.write_text("module m\nend module m\n")
    dtype = DerivedType("water_state", MOD, fpath=str(f))
    for comp, dim in (("h2osno", 1), ("h2osoi_liq", 2), ("qflx", 1)):
        dtype.components[comp] = Variable("real", comp, "c", 0, dim, bounds="begc:endc", declaration=MOD)
    fm = FortranModule(MOD, str(f), 0)
    fm.end_of_head_ln = 1
    fm.subroutines = set(subs)
    fm.global_vars = {
        "col_ws": Variable("water_state", "col_ws", "", 0, 0, declaration=MOD),
        "spval": Variable("real", "spval", "", 0, 0, declaration=MOD, value="1e36"),
        "nstep": Variable("integer", "nstep", "", 0, 0, declaration=MOD),
        "r8": Variable("integer", "r8", "", 0, 0, parameter=True, declaration=MOD, value="8"),
    }
    fm.defined_types = {"water_state": dtype}
    fut = SimpleNamespace(module_dict={MOD: fm}, subroutine_dict=subs, type_dict={"water_state": dtype},
                          primary_subroutines={f"{MOD}::root": subs[f"{MOD}::root"]}, e3sm_srcroot=tmp_path)
    return fut


def test_static_trace_resolves_dummies_and_cuts_recursion(analysis):
    ctx = ExportContext(analysis, {}, Path("/"))
    trace = StaticTrace(ctx, [f"{MOD}::root"]).run()
    subs = [n["subroutine"].split("::")[1] for n in trace.nodes]
    # root -> child -> gchild -> child (cut), root -> leaf
    assert subs == ["root", "child", "gchild", "child", "leaf"]
    assert [n["depth"] for n in trace.nodes] == [0, 1, 2, 3, 1]
    assert trace.nodes[3]["cut"] and trace.nodes[0]["size"] == 5 and trace.nodes[1]["size"] == 3
    by_path = {}
    for a in trace.accesses:
        by_path.setdefault(a["path"], []).append((a["node_order"], a["status"], a["resolved_from"]))
    # the dummy `a` of child is col_ws%h2osoi_liq at this call; gchild writes it through `x`
    assert ("m::col_ws%h2osoi_liq", 1, "r") in {(p, o, s) for p, v in by_path.items() for o, s, _ in v}
    assert any(o == 2 and s == "w" and f == "dummy" for o, s, f in by_path["m::col_ws%h2osoi_liq"])
    assert by_path["m::col_ws%qflx"] == [(4, "w", "dummy")]
    first = min(trace.accesses, key=lambda a: a["order"])
    assert first["path"] == "m::col_ws%h2osno" and first["status"] == "r"
    assert all(a["instance"] == "col_ws" and a["member"] for a in trace.accesses if "%" in a["path"])
    assert {a["var_name"] for a in trace.accesses if a["var_name"]} == {"spval", "nstep"}


def test_fieldstate_categories():
    rows = [
        # carried: read first, then written
        {"inst_module": "m", "instance": "col_ws", "member": "h2osno", "var_module": "", "var_name": "", "status": "r", "order": 0, "node_order": 0, "ln": 5},
        {"inst_module": "m", "instance": "col_ws", "member": "h2osno", "var_module": "", "var_name": "", "status": "w", "order": 3, "node_order": 1, "ln": 7},
        # written first, history -> diagnostic
        {"inst_module": "m", "instance": "veg_cf", "member": "npp", "var_module": "", "var_name": "", "status": "w", "order": 1, "node_order": 0, "ln": 6},
        {"inst_module": "m", "instance": "veg_cf", "member": "npp", "var_module": "", "var_name": "", "status": "r", "order": 2, "node_order": 2, "ln": 8},
        # written first, no registration -> intermediate
        {"inst_module": "m", "instance": "veg_cf", "member": "tmp", "var_module": "", "var_name": "", "status": "w", "order": 4, "node_order": 0, "ln": 9},
        # read only -> input
        {"inst_module": "", "instance": "", "member": "", "var_module": "m", "var_name": "spval", "status": "r", "order": 5, "node_order": 0, "ln": 1},
        # whole-instance access is ignored
        {"inst_module": "m", "instance": "veg_cf", "member": "", "var_module": "", "var_name": "", "status": "r", "order": 6, "node_order": 0, "ln": 1},
    ]
    regs = [
        {"inst_module": "m", "instance": "col_ws", "member": "h2osno", "kind": "restart", "inactive": False},
        {"inst_module": "m", "instance": "veg_cf", "member": "npp", "kind": "hist", "inactive": True},
        {"inst_module": "m", "instance": "veg_cf", "member": "npp", "kind": "restart", "inactive": False},
        {"inst_module": "m", "instance": "col_ws", "member": "never", "kind": "restart", "inactive": False},
    ]
    out = {(r["instance"], r["member"], r["var_name"]): r for r in fieldstate.derive(rows, regs, {0: "a", 1: "b", 2: "c"})}
    assert out[("col_ws", "h2osno", "")]["category"] == "prognostic"
    assert out[("col_ws", "h2osno", "")]["n_routines"] == 2 and not out[("col_ws", "h2osno", "")]["restart_missing"]
    npp = out[("veg_cf", "npp", "")]
    assert npp["category"] == "diagnostic" and npp["history"] and not npp["history_active"]
    assert npp["restart"] and npp["restart_unneeded"]
    assert out[("veg_cf", "tmp", "")]["category"] == "intermediate"
    assert out[("", "", "spval")]["category"] == "input"
    # a conditional write first, then a read: the read may see last step's value -> prognostic
    cond = [
        {"inst_module": "m", "instance": "col_ws", "member": "snw_rds", "var_module": "", "var_name": "", "status": "w", "order": 0, "node_order": 0, "ln": 1, "conditional": True},
        {"inst_module": "m", "instance": "col_ws", "member": "snw_rds", "var_module": "", "var_name": "", "status": "r", "order": 1, "node_order": 1, "ln": 2, "conditional": False},
        {"inst_module": "m", "instance": "col_ws", "member": "snw_rds", "var_module": "", "var_name": "", "status": "w", "order": 2, "node_order": 1, "ln": 3, "conditional": False},
    ]
    snw = fieldstate.derive(cond, [], {})[0]
    assert snw["category"] == "prognostic" and snw["first_status"] == "w"
    assert fieldstate.categorize([("w", True), ("w", True)], False) == "prognostic"
    assert fieldstate.categorize([("w", False), ("r", False)], True) == "diagnostic"
    never = out[("col_ws", "never", "")]
    assert never["category"] == "unused" and never["restart_unneeded"]
    assert ("veg_cf", "", "") not in out


def test_apply_registrations_follows_type_extension():
    regs = [
        {"sub_id": "m::init", "ln": 1, "kind": "hist", "base": "this", "field": "x", "user_type": "base", "member": "x",
         "inst_module": "", "instance": "", "var_module": "", "var_name": "", "inactive": False},
        {"sub_id": "m::init", "ln": 2, "kind": "restart", "base": "col_ws", "field": "y", "user_type": "",
         "member": "y", "inst_module": "m", "instance": "col_ws", "var_module": "", "var_name": "", "inactive": False},
    ]
    instances = [
        {"module": "m", "user_type_name": "base", "instance_name": "b1", "public": True},
        {"module": "m", "user_type_name": "ext", "instance_name": "e1", "public": True},
        {"module": "m", "user_type_name": "other", "instance_name": "o1", "public": True},
    ]
    applied = fieldstate.apply_registrations(regs, instances, {"ext": "base"}, lambda r, inst: inst != "e1" or r["kind"] != "hist" or True)
    keys = {(a["instance"], a["member"], a["kind"]) for a in applied}
    assert keys == {("b1", "x", "hist"), ("e1", "x", "hist"), ("col_ws", "y", "restart")}
    applied = fieldstate.apply_registrations(regs, instances, {"ext": "base"}, lambda r, inst: inst != "e1")
    assert {(a["instance"], a["member"]) for a in applied} == {("b1", "x"), ("col_ws", "y")}


def test_csv_contract(tmp_path):
    n = write_table(tmp_path, "cascades", [
        {"cascade_var": "num_pcropp", "pair": 0, "trigger_module": "elm_varctl", "trigger_name": "use_crop", "nml_val": ".false.", "cascade_val": 0},
    ])
    assert n == 1
    rows = read_table(tmp_path / "cascades.csv")
    assert rows == [{"cascade_var": "num_pcropp", "pair": "0", "trigger_module": "elm_varctl", "trigger_name": "use_crop", "nml_val": ".false.", "cascade_val": "0"}]
    with pytest.raises(KeyError):
        write_table(tmp_path, "cascades", [{"bogus": 1}])
    (tmp_path / "modules.csv").write_text("module,other\n")
    with pytest.raises(ValueError):
        read_table(tmp_path / "modules.csv")


def test_pointer_components_expand_to_targets(analysis):
    """`ptrs%tend_ptr` (a module instance whose component points at col_ws%h2osno) resolves to the target."""
    fm = analysis.module_dict[MOD]
    ptype = DerivedType("ptr_type", MOD, fpath=str(fm.filepath))
    ptype.components["tend_ptr"] = Variable("real", "tend_ptr", "", 0, 1, pointer=["col_ws%h2osno", "col_ws%qflx"], ptrscalar=True)
    analysis.type_dict["ptr_type"] = ptype
    fm.global_vars["ptrs"] = Variable("ptr_type", "ptrs", "", 0, 1, declaration=MOD)
    ctx = ExportContext(analysis, {}, Path("/"))
    assert ctx.resolver.expand("m::ptrs%tend_ptr") == ("m::col_ws%h2osno", "m::col_ws%qflx")
    assert ctx.resolver.expand("m::col_ws%h2osno") == ("m::col_ws%h2osno",)
    assert ctx.resolver.expand("m::ptrs") == ("m::ptrs",)


def test_export_snapshot_small(analysis, tmp_path):
    meta = {"e3sm_srcroot": str(tmp_path), "e3sm": {"commit": "abc1234def", "branch": "x/y"}, "spel": {}}
    snap = export_snapshot(analysis, meta, tmp_path / "out", roots=[f"{MOD}::root"])
    assert snap["label"] == "y@abc1234"
    files = {p.stem for p in (tmp_path / "out").glob("*.csv")}
    assert files == set(TABLES)
    rows = snap["stats"]["rows"]
    assert rows["subroutines"] == 4 and rows["trace_nodes"] == 5 and rows["user_type_instances"] == 1
    assert rows["intrinsic_globals"] == 3 and rows["field_state"] >= 4
    with (tmp_path / "out" / "field_state.csv").open() as f:
        cats = {(r["instance"], r["member"], r["var_name"]): r["category"] for r in csv.DictReader(f)}
    assert cats[("col_ws", "h2osno", "")] == "prognostic"
    assert cats[("col_ws", "qflx", "")] == "intermediate"
    assert cats[("", "", "spval")] == "input"
    assert cats[("", "", "nstep")] == "prognostic"
    tree = json.loads((tmp_path / "out" / "snapshot.json").read_text())
    assert tree["trace_roots"] == [f"{MOD}::root"]


def test_resolver_follows_renames_and_reexports(tmp_path):
    from spel.scripts.db_export.resolve import GlobalResolver

    f = tmp_path / "x.F90"
    f.write_text("")
    varcon = FortranModule("varcon", str(f), 0)
    varcon.global_vars = {"spval": Variable("real", "spval", "", 0, 0, declaration="varcon")}
    varcon.end_of_head_ln = 5
    shim = FortranModule("shim", str(f), 0)  # re-exports spval under a new name
    shim.use_stmts = parse_use_stmts([LineTuple(line="use varcon, only: special => spval", ln=1)])
    shim.end_of_head_ln = 5
    user = FortranModule("user", str(f), 0)
    user.use_stmts = parse_use_stmts([
        LineTuple(line="use shim, only: special", ln=1),
        LineTuple(line="use varcon, only: local_spval => spval", ln=12),
    ])
    user.end_of_head_ln = 5
    sub = SimpleNamespace(id="user::s", module="user", startline=10, end_stmt_ln=20, is_internal=False, host=None, library=False, active_global_vars={})
    r = GlobalResolver({"varcon": varcon, "shim": shim, "user": user}, {}, {})
    assert r.resolve(sub, "special") == ("varcon", "spval")
    assert r.resolve(sub, "local_spval") == ("varcon", "spval")
    assert r.resolve(sub, "unknown") is None and r.unresolved["unknown"] == 1
    assert r.canonical(sub, "local_spval%x") == "varcon::spval%x"


def test_whole_elm_export(elm_drv_analysis, tmp_path):
    meta = {"e3sm_srcroot": str(elm_drv_analysis.e3sm_srcroot), "e3sm": {}, "spel": {}}
    snap = export_snapshot(elm_drv_analysis, meta, tmp_path, label="t")
    rows = snap["stats"]["rows"]
    assert rows["trace_nodes"] > 1000 and rows["trace_access"] > 10000 and rows["field_state"] > 1000
    subs = {r["sub_id"] for r in read_table(tmp_path / "subroutines.csv")}
    nodes = read_table(tmp_path / "trace_nodes.csv")
    assert all(n["subroutine"] in subs for n in nodes)
    orders = {int(n["order"]) for n in nodes}
    assert orders == set(range(len(nodes)))
    assert all(int(n["parent_order"]) in orders for n in nodes if n["parent_order"] != "")
    assert all(int(a["node_order"]) in orders for a in read_table(tmp_path / "trace_access.csv"))
    assert all(int(r["end_ln"]) >= int(r["start_ln"]) for r in read_table(tmp_path / "nml_ifs.csv"))
    stats = snap["stats"]
    assert sum(stats["unresolved_globals"].values()) < 100


def test_filter_relations_from_sites():
    from spel.scripts.db_export.filters import derive, disjoint_pairs

    active = ("top_pp%active(t)", "(col_pp%active(c).or.include_inactive)")
    pactive = ("top_pp%active(t)", "(veg_pp%active(p).or.include_inactive)")

    def site(name, ln, level, guards, parent="", sub="filtermod::setfiltersonegroup"):
        domain = f"filter:{parent}" if parent else f"range:bounds%beg{level}:bounds%end{level}"
        return {"name": name, "instance": "filtermod::filter", "subroutine": sub, "ln": ln, "level": level,
                "parent": parent, "domain": domain, "guards": guards}

    sites = [
        site("lakec", 10, "c", active + ("lun_pp%lakpoi(l)",)),
        site("nolakec", 12, "c", active + ("not(lun_pp%lakpoi(l))",)),
        site("lakep", 20, "p", pactive + ("lun_pp%lakpoi(l)",)),
        site("nolakep", 22, "p", pactive + ("not(lun_pp%lakpoi(l))",)),
        site("nolakeurbanp", 24, "p", pactive + ("not(lun_pp%lakpoi(l))", "(.not.lun_pp%urbpoi(l))")),
        site("soilc", 30, "c", active + ("(col_pp%is_soil(c).or.col_pp%is_crop(c))",)),
        site("hydrologyc", 40, "c", active + ("(col_pp%is_soil(c).or.road(c))",)),
        site("hydrononsoic", 42, "c", active + ("(col_pp%is_soil(c).or.road(c))", "(col_pp%itype(c)==icol_road_perv)")),
        site("snowc", 5, "c", ("(col_pp%snl(c)<0)",), parent="nolakec", sub="snowhydrologymod::buildsnowfilter"),
        site("nosnowc", 7, "c", ("not((col_pp%snl(c)<0))",), parent="nolakec", sub="snowhydrologymod::buildsnowfilter"),
    ]
    sites.append(dict(sites[0], instance="filtermod::filter_inactive_and_active"))  # the second setFilters call: same site
    frows, rrows = derive(sites)
    assert [f["name"] for f in frows] == sorted({s["name"] for s in sites})
    rel = {(r["filter_a"], r["filter_b"], r["relation"]): r for r in rrows}
    assert rel[("lakec", "nolakec", "disjoint")]["source"] == "if/else"
    assert rel[("lakec", "nolakep", "disjoint")]["condition"].endswith("(across levels)")
    assert rel[("nolakeurbanp", "nolakep", "subset")]["source"] == "nested"
    assert rel[("hydrononsoic", "hydrologyc", "subset")]["source"] == "nested"
    assert rel[("snowc", "nolakec", "subset")]["source"] == "parent"
    assert rel[("nosnowc", "snowc", "disjoint")]["source"] == "if/else"
    assert rel[("lakec", "snowc", "disjoint")]["source"] == "closure"
    assert rel[("lakec", "soilc", "disjoint")]["source"] == "curated"
    assert rel[("hydrononsoic", "lakec", "disjoint")]["source"] in ("curated", "closure")
    assert ("soilc", "hydrologyc", "disjoint") not in rel and ("lakec", "lakep", "disjoint") not in rel
    pairs = disjoint_pairs(rrows)
    assert ("snowc", "lakec") in pairs and ("lakec", "snowc") in pairs and ("soilc", "hydrologyc") not in pairs


def test_cascade_rows_one_row_per_pair_and_trigger():
    from spel.scripts.db_export.ifs import cascade_rows

    rows = list(cascade_rows(None))
    crop = [r for r in rows if r["cascade_var"] == "num_pcropp"]
    assert [(r["pair"], r["trigger_name"], r["nml_val"]) for r in crop] == [(0, "use_crop", ".false."), (1, "use_crop", ".true.")]
    carbon = [r for r in rows if r["cascade_var"] == "carbon_only"]
    assert len(carbon) == 4 * 3  # four mappings, three triggers each
    on = [r for r in carbon if r["cascade_val"] == ".true."]
    assert {(r["trigger_name"], r["nml_val"]) for r in on} == {("suplnitro", "all"), ("suplphos", "all"), ("spinup_state", "0")}
    assert len({r["pair"] for r in on}) == 1
