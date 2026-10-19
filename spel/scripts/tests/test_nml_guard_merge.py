from types import SimpleNamespace

import spel.scripts.nml.analyze_namelist as an
from spel.scripts.fortran_parser.boolen_expression import AnyOf, Expectation

FATES = Expectation("use_fates", "False")
RD = Expectation("nu_com", ".eq. 'rd'")


def test_guards_are_merged_over_all_roots(monkeypatch):
    # a.x: guarded in both roots -> OR'ed; a.y: unguarded in root2 -> no guard;
    # a.z: only accessed (guarded) by root1. Previously the last root overwrote the rest.
    root1 = SimpleNamespace(elmtype_access_by_ln={"a%x": [], "a%y": [], "a%z": []})
    root2 = SimpleNamespace(elmtype_access_by_ln={"a%x": [], "a%y": []})
    guards = {id(root1): {"a%x": FATES, "a%y": FATES, "a%z": RD}, id(root2): {"a%x": RD}}
    monkeypatch.setattr(an, "nml_guards", lambda sub: guards[id(sub)])
    monkeypatch.setattr(an, "get_component", lambda insts, inst, field: field)

    for roots in ([root1, root2], [root2, root1]):
        result = an.check_subs_for_nml_guarded_vars(roots, instance_dict={})
        by_var = {v: cond for cond, vs in result.items() for v in vs}
        assert set(by_var) == {"x", "z"}
        assert by_var["z"] == RD
        assert by_var["x"] in (AnyOf((FATES, RD)), AnyOf((RD, FATES)))


C13 = Expectation("use_c13", "True")
C14 = Expectation("use_c14", "True")


def test_instances_sharing_a_component_guard_it_only_if_all_are_guarded(monkeypatch):
    # col_cf%x is used unguarded, c13_col_cf%x only under use_c13: the type's
    # component x (shared by both instances) must stay unguarded. y is used only
    # by the isotope instances, each under its own flag: guarded by either.
    x, y = SimpleNamespace(name="x"), SimpleNamespace(name="y")
    dtype = SimpleNamespace(components={"x": x, "y": y})
    insts = {"col_cf": dtype, "c13_col_cf": dtype, "c14_col_cf": dtype}
    root = SimpleNamespace(
        elmtype_access_by_ln={"col_cf%x": [], "c13_col_cf%x": [], "c13_col_cf%y": [], "c14_col_cf%y": []}
    )
    monkeypatch.setattr(
        an, "nml_guards", lambda sub: {"c13_col_cf%x": C13, "c13_col_cf%y": C13, "c14_col_cf%y": C14}
    )

    result = an.check_subs_for_nml_guarded_vars([root], instance_dict=insts)
    by_var = {v.name: cond for cond, vs in result.items() for v in vs}
    assert set(by_var) == {"y"}
    assert by_var["y"] in (AnyOf((C13, C14)), AnyOf((C14, C13)))
