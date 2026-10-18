from collections.abc import Iterable
from dataclasses import dataclass

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
    # col_pp%is_fates / veg_pp%is_fates are only set .true. by the FATES interface
    # (elmfates_interfaceMod), e.g. CH4 reads veg_pp%is_bareground (allocated only
    # with use_fates) under .not. col_pp%is_fates(c)'s else branch
    "is_fates": Dependence(
        cascade_var="is_fates",
        trigger="elm_varctl::use_fates",
        val_pairs=[
            Pairs(nml_val=".false.", cascade_val=".false."),
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


@dataclass(frozen=True)
class DerivedConstant:
    """A constant a development branch derives from a namelist variable (e.g. in controlMod)."""

    name: str
    type: str
    source: str  # module::variable it is derived from
    fortran: str  # expression of the source variable

    @property
    def source_name(self) -> str:
        return self.source.split("::")[-1]


# Written by `spel create --capture-for` into the reference case's constants, so the
# development case can read them from the reference data
DERIVED_CONSTANTS = {
    # controlMod: select case (trim(urban_hac)) -> urban_hac_on_int/urban_wasteheat_int/off
    "urban_hac_int": DerivedConstant(
        name="urban_hac_int",
        type="integer",
        source="urbanparamstype::urban_hac",
        fortran="merge(1, merge(2, 0, trim(urban_hac) == 'ON_WASTEHEAT'), trim(urban_hac) == 'ON')",
    ),
}
