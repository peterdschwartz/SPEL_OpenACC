"""The inventory tracer on nutrient-transformed types: 3-level targets and registrations of embedded holders."""
from types import SimpleNamespace

from spel.transforms.compact.inventory import Tracer


def comp(name, type_="real", dim=1, bounds="begp:endp", nested=False):
    return SimpleNamespace(name=name, type=type_, dim=dim, bounds=bounds, nested=nested, pointer=False, ptrscalar=False)


def test_target_resolves_component_paths():
    base = SimpleNamespace(type_name="vegetation_nutrient_flux", components={"agnpp": comp("agnpp")}, procedures={}, instances={})
    carbon = SimpleNamespace(
        type_name="vegetation_carbon_flux",
        components={
            "core": comp("core", "vegetation_nutrient_flux", 0, None),
            "core%agnpp": comp("core%agnpp", nested=True),
            "gpp": comp("gpp"),
        },
        procedures={"init": "m::veg_cf_init"},
        instances={"veg_cf": None},
    )
    type_dict = {base.type_name: base, carbon.type_name: carbon}
    tr = Tracer.__new__(Tracer)
    tr.type_dict = type_dict
    tr.instances = {"veg_cf": "vegetation_carbon_flux"}
    tr.components = {}
    assert tr.target("veg_cf%core%agnpp") == "veg_cf%core%agnpp"
    assert tr.target("veg_cf%gpp") == "veg_cf%gpp"
    assert tr.target("veg_cf%core") is None  # the whole holder passed to a base routine
    assert tr.target("veg_cf%unknown") == "veg_cf%unknown"  # as before: reported with '?' subgrid
    assert tr.target("other%x") is None
    assert tr.component("veg_cf%core%agnpp") == ("p", 1, "begp:endp")
