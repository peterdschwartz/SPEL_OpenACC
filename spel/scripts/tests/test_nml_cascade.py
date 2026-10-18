from spel.scripts.fortran_parser.boolen_expression import (
    NO_EXPECTATION,
    AllOf,
    Expectation,
    infer_condition_expectations,
    simplify,
)
from spel.scripts.fortran_parser.spel_ast import FuncExpression, Identifier, InfixExpression, PrefixExpression
from spel.scripts.fortran_parser.tokens import Token, TokenTypes
from spel.scripts.nml.analyze_namelist import cascade_to_triggers
from spel.scripts.nml.namelist_cascade import NML_CASCADES, cascade_trigger_variables

tok = Token(token=TokenTypes.EOF, literal="temp")

# h2osfc(c) > min_h2osfc .and. lun_pp%ispolygon(l)  (CanopyHydrologyMod::FracH2OSfc)
ISPOLYGON = FuncExpression(
    tok=tok, fn=Identifier(tok=tok, value="lun_pp%ispolygon"), args=[Identifier(tok=tok, value="l")]
)
COND = InfixExpression(
    tok=tok,
    op=".and.",
    left=InfixExpression(
        tok=tok,
        op=">",
        left=Identifier(tok=tok, value="h2osfc"),
        right=Identifier(tok=tok, value="min_h2osfc"),
    ),
    right=ISPOLYGON,
)


def test_cascade_array_element_is_matched():
    assert infer_condition_expectations(COND, {"ispolygon"}) == Expectation("ispolygon", "True")


def test_ispolygon_implies_use_polygonal_tundra():
    expectation = cascade_to_triggers(infer_condition_expectations(COND, {"ispolygon"}))
    assert expectation == Expectation("use_polygonal_tundra", "True")
    # non-polygon landunits exist with either setting
    negated = PrefixExpression(tok=tok, op=".not.", right=ISPOLYGON)
    assert simplify(
        cascade_to_triggers(infer_condition_expectations(negated, {"ispolygon"}))
    ) == NO_EXPECTATION


def test_integer_cascades_keep_their_guard():
    guard = AllOf((Expectation("num_pcropp", "> 0"),))
    assert cascade_to_triggers(guard) == guard


def test_trigger_constraint_both_pairs():
    use_crop = NML_CASCADES["num_pcropp"]
    assert use_crop.trigger_name == "use_crop"
    assert use_crop.trigger_constraint("True") is None


def test_cascade_trigger_variables():
    found = cascade_trigger_variables(["use_polygonal_tundra", "irrigate"])
    assert list(found) == ["use_polygonal_tundra"]
    var = found["use_polygonal_tundra"]
    assert (var.type, var.dim, var.declaration) == ("logical", 0, "elm_varctl")


def test_callee_guard_propagates_through_call_site():
    # CanopyHydrology calls FracH2OSfc (line 10), which reads iwp only under ispolygon
    from types import SimpleNamespace

    from spel.scripts.nml.analyze_namelist import nml_guards

    polygon = Expectation("use_polygonal_tundra", "True")
    irrigate = Expectation("irrigate", "True")
    if_at = lambda guards: lambda ln: (  # noqa: E731
        SimpleNamespace(condtional_expectation=guards[ln]) if ln in guards else None
    )
    rw = lambda ln: SimpleNamespace(ln=ln)  # noqa: E731
    child = SimpleNamespace(
        id="frach2osfc",
        sub_call_desc={},
        child_subroutines={},
        elmtype_access_by_ln={"col_ws%iwp_microrel": [rw(3)], "col_ws%h2osfc": [rw(1)]},
        namelist_if_at=if_at({3: polygon}),
    )
    root = SimpleNamespace(
        id="canopyhydrology",
        sub_call_desc={10: SimpleNamespace(fn="frach2osfc")},
        child_subroutines={"frach2osfc": child},
        elmtype_access_by_ln={
            "col_ws%iwp_microrel": [rw(10)],
            "col_ws%h2osfc": [rw(10)],
            "veg_wf%qflx_supply_patch": [rw(5)],
        },
        namelist_if_at=if_at({5: irrigate}),
    )
    assert nml_guards(root) == {
        "col_ws%iwp_microrel": polygon,
        "veg_wf%qflx_supply_patch": irrigate,
    }


def test_if_condition_line_is_not_guarded_by_the_if():
    from types import SimpleNamespace

    from spel.scripts.analyze_subroutines import Subroutine

    polygon_if = SimpleNamespace(
        start_ln=10, end_ln=20, nml_vars={}, nml_cascades={"ispolygon": None}, copy=lambda: "if"
    )
    sub = SimpleNamespace(flat_ifs=[polygon_if])
    assert Subroutine.namelist_if_at(sub, 10) is None  # the condition reads lun_pp%ispolygon
    assert Subroutine.namelist_if_at(sub, 11) == "if"


def test_ifs_inside_loops_are_flattened():
    # CH4Mod: if (.not. lake) > do fp > if (.not. col_pp%is_fates(c)) ... else
    from spel.scripts.fortran_parser.spel_ast import BlockStatement, DoLoop, IfConstruct
    from spel.scripts.nml.analyze_ifs import nested_ifs

    inner = IfConstruct.__new__(IfConstruct)
    body = BlockStatement(tok)
    body.statements = [inner]
    loop = DoLoop.__new__(DoLoop)
    loop.body = body
    assert nested_ifs([loop]) == [inner]


def test_guarded_vars_are_the_types_own_components():
    # guards are looked up by identity, so they must hold dtype.components[...] itself
    from types import SimpleNamespace

    from spel.scripts.nml.analyze_namelist import check_subs_for_nml_guarded_vars
    from spel.scripts.utilityFunctions import Variable

    fates = Expectation("use_fates", "True")
    comp = Variable("logical", "is_bareground", "patch", 0, 1, bounds="begp:endp")
    dtype = SimpleNamespace(components={"is_bareground": comp}, procedures={})
    root = SimpleNamespace(
        id="ch4mod::ch4",
        sub_call_desc={},
        child_subroutines={},
        elmtype_access_by_ln={"veg_pp%is_bareground": [SimpleNamespace(ln=5)]},
        namelist_if_at=lambda ln: SimpleNamespace(condtional_expectation=fates),
    )
    guards = check_subs_for_nml_guarded_vars([root], {"veg_pp": dtype})
    assert guards[fates][0] is comp
