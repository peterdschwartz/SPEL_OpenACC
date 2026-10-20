"""Holders: a concrete flux type, a nutrient base type embedded as `core`, a role type."""
from types import SimpleNamespace

import pytest

from spel.transforms.compact.holders import (
    Embedding,
    base_routine,
    element_of,
    embedded_holders,
    family_base,
    find_holder,
    role_types,
)


def comp(name, type_="real", dim=1, bounds="begp:endp", nested=False, pointer=False):
    return SimpleNamespace(name=name, type=type_, dim=dim, bounds=bounds, nested=nested, pointer=pointer, ptrscalar=False)


def dtype(name, components, instances=(), procedures=None, filepath="VegetationDataType.F90"):
    return SimpleNamespace(
        type_name=name,
        components={c.name: c for c in components},
        instances={i: SimpleNamespace(declaration="vegetationdatatype") for i in instances},
        procedures=procedures or {},
        filepath=filepath,
    )


@pytest.fixture
def fut():
    base = dtype(
        "vegetation_nutrient_flux",
        [comp("species", "integer", 0, None), comp("leaf_to_litter"), comp("cbuf_dummy", "real", 0, None)],
        filepath="NutrientFluxType.F90",
    )
    role = dtype("vegetation_retrans_flux", [comp("pool")], filepath="NutrientFluxType.F90")
    carbon = dtype(
        "vegetation_carbon_flux",
        [
            comp("core", "vegetation_nutrient_flux", 0, None),
            comp("core%species", "integer", 0, None, nested=True),
            comp("core%leaf_to_litter", nested=True),
            comp("gpp"),
        ],
        instances=("veg_cf", "c13_veg_cf"),
        procedures={"init": "vegetationdatatype::veg_cf_init", "setvalues": "vegetationdatatype::veg_cf_setvalues"},
    )
    nitrogen = dtype(
        "vegetation_nitrogen_flux",
        [
            comp("core", "vegetation_nutrient_flux", 0, None),
            comp("core%leaf_to_litter", nested=True),
            comp("retrans", "vegetation_retrans_flux", 0, None),
            comp("retrans%pool", nested=True),
        ],
        instances=("veg_nf",),
        procedures={"init": "vegetationdatatype::veg_nf_init", "setvalues": "vegetationdatatype::veg_nf_setvalues"},
    )
    subs = {
        "vegetationdatatype::veg_cf_init": None,
        "vegetationdatatype::veg_cf_setvalues": None,
        "vegetationdatatype::veg_nf_init": None,
        "vegetationdatatype::veg_nf_setvalues": None,
        "nutrientfluxtype::vegetation_nutrient_flux_setvalues": None,
        "nutrientfluxtype::vegetation_nutrient_flux_init_history": None,
    }
    return SimpleNamespace(
        type_dict={t.type_name: t for t in (base, role, carbon, nitrogen)},
        subroutine_dict=subs,
    )


def test_concrete_holder(fut):
    h = find_holder(fut, "vegetation_carbon_flux")
    assert not h.embedded
    assert h.instances == ["veg_cf", "c13_veg_cf"]
    assert [e.element for e in h.embeddings] == ["c12", "c13"]
    assert h.routines["setvalues"] == "vegetationdatatype::veg_cf_setvalues"
    assert h.split("veg_cf%gpp") == (Embedding("veg_cf", "vegetation_carbon_flux", "", "c12"), "gpp")
    assert h.split("veg_cf%core%leaf_to_litter")[1] == "core%leaf_to_litter"


def test_base_holder(fut):
    h = find_holder(fut, "vegetation_nutrient_flux")
    assert h.embedded
    assert sorted(h.instances) == ["c13_veg_cf", "veg_cf", "veg_nf"]
    emb = {e.instance: e for e in h.embeddings}
    assert emb["veg_nf"] == Embedding("veg_nf", "vegetation_nitrogen_flux", "core", "n")
    assert emb["c13_veg_cf"].element == "c13"
    assert h.routines == {
        "setvalues": "nutrientfluxtype::vegetation_nutrient_flux_setvalues",
        "init_history": "nutrientfluxtype::vegetation_nutrient_flux_init_history",
    }
    assert h.split("veg_nf%core%leaf_to_litter") == (emb["veg_nf"], "leaf_to_litter")
    assert h.split("veg_nf%retrans%pool") is None
    assert h.concrete_types == ["vegetation_carbon_flux", "vegetation_nitrogen_flux"]


def test_role_holder(fut):
    h = find_holder(fut, "vegetation_retrans_flux")
    assert h.embedded and h.instances == ["veg_nf"] and h.routines == {}
    assert h.split("veg_nf%retrans%pool") == (Embedding("veg_nf", "vegetation_nitrogen_flux", "retrans", "n"), "pool")


def test_helpers(fut):
    assert base_routine(fut.subroutine_dict, "vegetation_nutrient_flux", "restart") is None
    assert element_of("c14_veg_cf", "vegetation_carbon_flux") == "c14"
    assert element_of("veg_pf", "vegetation_phosphorus_flux") == "p"
    assert element_of("veg_ws", "vegetation_water_state") == ""
    assert embedded_holders(fut.type_dict, fut.type_dict["vegetation_nitrogen_flux"]) == [
        ("core", "vegetation_nutrient_flux"),
        ("retrans", "vegetation_retrans_flux"),
    ]
    manifest = {
        "families": {"vegetation_nutrient_flux": {"component": "core", "types": {"vegetation_carbon_flux": 10}}},
        "groups": {"vegetation_retrans_flux": {"component": "retrans", "types": {"vegetation_nitrogen_flux": 3}}},
    }
    assert family_base(manifest, "vegetation_carbon_flux") == "vegetation_nutrient_flux"
    assert family_base(manifest, "vegetation_water_state") is None
    assert role_types(manifest, ["vegetation_nitrogen_flux"]) == ["vegetation_retrans_flux"]
