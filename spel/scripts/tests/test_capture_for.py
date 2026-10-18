import logging
from types import SimpleNamespace

from spel.scripts.fortran_parser.boolen_expression import Expectation
from spel.scripts.UnitTestforELM import add_capture_for
from spel.scripts.utilityFunctions import Variable


def comp(name, active=False):
    v = Variable("real", name, "column", 0, 1, bounds="begc:endc")
    v.active = active
    return v


def case(name, fields, guards=None, globals_=None):
    """A FunctionalUnitTest-like stub: one type (column_water_state) with instance col_ws."""
    comps = {f: comp(f, active=f in fields) for f in ("h2osoi_liq", "h2osfc", "wslake_col")}
    inst = Variable("column_water_state", "col_ws", "?", 0, 0)
    inst.active = True
    dtype = SimpleNamespace(
        components=comps, instances={"col_ws": inst}, active=True, type_name="column_water_state"
    )
    guards = guards or {}
    fut = SimpleNamespace(
        case_name=name,
        type_dict={"column_water_state": dtype},
        guarded_usage_dict={cond: [comps[f] for f in fs] for cond, fs in guards.items()},
        active_global_vars=dict(globals_ or {}),
        module_dict={},
        logger=logging.getLogger("test"),
    )
    fut.instance_to_type_map = lambda: {"col_ws": "column_water_state"}
    fut.guards_for_variable = lambda v: tuple(
        c for c, vs in fut.guarded_usage_dict.items() if v in vs
    )
    return fut


def test_capture_for_adds_fields_guards_and_constants():
    lake = Expectation("use_lake_wat_storage", "True")
    tundra = Variable("logical", "use_polygonal_tundra", "?", 0, 0, declaration="elm_varctl")
    ref = case("ref_x", {"h2osoi_liq"})
    ref.module_dict = {"elm_varctl": SimpleNamespace(global_vars={"use_polygonal_tundra": tundra})}
    dev = case(
        "int_x",
        {"h2osoi_liq", "wslake_col"},
        guards={lake: ["wslake_col", "h2osoi_liq"]},
        globals_={"use_polygonal_tundra": tundra},
    )
    add_capture_for(ref, dev)
    comps = ref.type_dict["column_water_state"].components
    # new field: captured under the dev case's guard
    assert comps["wslake_col"].active
    assert ref.guards_for_variable(comps["wslake_col"]) == (lake,)
    # field the reference uses unguarded stays unguarded
    assert ref.guards_for_variable(comps["h2osoi_liq"]) == ()
    assert not comps["h2osfc"].active
    assert "use_polygonal_tundra" in ref.active_global_vars
    assert ref.captured_for == ["int_x"]


def test_guards_match_components_by_identity():
    # veg_pp%gridcell is guarded, col_pp%gridcell isn't; the components compare equal
    from spel.scripts.functional_unit_test import FunctionalUnitTest

    col_gridcell = Variable("integer", "gridcell", "column", 0, 1, bounds="begc:endc")
    veg_gridcell = Variable("integer", "gridcell", "patch", 0, 1, bounds="begp:endp")
    assert col_gridcell == veg_gridcell
    storage_off = Expectation("use_lake_wat_storage", "False")
    fut = SimpleNamespace(guarded_usage_dict={storage_off: [veg_gridcell]})
    assert FunctionalUnitTest.guards_for_variable(fut, veg_gridcell) == (storage_off,)
    assert FunctionalUnitTest.guards_for_variable(fut, col_gridcell) == ()
