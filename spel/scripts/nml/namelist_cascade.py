from collections.abc import Iterable

from spel.scripts.types import Dependence, Pairs
from spel.scripts.utilityFunctions import Variable

NML_CASCADES = {
    "num_pcropp": Dependence(
        cascade_var="num_pcropp",
        trigger="elm_varctl::use_crop",
        val_pairs=[
            Pairs(nml_val=".false.", cascade_val="0"),
            Pairs(nml_val=".true.", cascade_val="10"),
        ],
    ),
    "num_ppercropp": Dependence(
        cascade_var="num_ppercropp",
        trigger="elm_varctl::use_crop",
        val_pairs=[
            Pairs(nml_val=".false.", cascade_val="0"),
            Pairs(nml_val=".true.", cascade_val="10"),
        ],
    ),
    # ice wedge polygon landunits are only added with use_polygonal_tundra
    # (initGridCellsMod), and polygon-only fields (col_ws%iwp_*) are only allocated then
    "ispolygon": Dependence(
        cascade_var="ispolygon",
        trigger="elm_varctl::use_polygonal_tundra",
        val_pairs=[
            Pairs(nml_val=".false.", cascade_val=".false."),
        ],
    ),
}


def cascade_trigger_variables(names: Iterable[str]) -> dict[str, Variable]:
    """Variables for the cascade trigger namelist variables among `names`."""
    triggers = {dep.trigger_name: dep.trigger for dep in NML_CASCADES.values()}
    result: dict[str, Variable] = {}
    for name in names:
        if name in triggers:
            module = triggers[name].split("::")[0]
            result[name] = Variable("logical", name, "?", 0, 0, declaration=module)
    return result
