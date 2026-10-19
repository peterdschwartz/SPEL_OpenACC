import shutil
import subprocess
from types import SimpleNamespace

import pytest

from spel.transforms.nutrient.common import Family
from spel.transforms.nutrient.history import HELPERS, HistoryMerger, render, template_for

gfortran = pytest.mark.skipif(not shutil.which("gfortran"), reason="needs gfortran")

SPECIES_MOD = """\
module SpeciesMod
  implicit none
  private
  integer, parameter, public :: CN_SPECIES_C12 = 1
  integer, parameter, public :: CN_SPECIES_C13 = 2
  integer, parameter, public :: CN_SPECIES_C14 = 3
  integer, parameter, public :: CN_SPECIES_N   = 4
  integer, parameter, public :: CN_SPECIES_P   = 5
  public :: nutrient_name, nutrient_units, nutrient_text, by_species, hist_default
contains
{helpers}
end module SpeciesMod
"""

CASES = [("fname", "LEAF#_STORAGE"), ("fname", "PFT_FIRE_#LOSS"), ("units", "g#/m^2/s"), ("long_name", "leaf # storage")]
VARIANTS = ["c12", "c13", "c14", "n", "p"]


@gfortran
def test_fortran_helpers_match_render(tmp_path):
    fn = {"fname": "nutrient_name", "units": "nutrient_units", "long_name": "nutrient_text"}
    prints = "\n".join(
        f"  print '(a)', {fn[k]}({i}, '{t}')" for k, t in CASES for i in range(1, 6)
    )
    prog = (
        SPECIES_MOD.format(helpers=HELPERS)
        + "program t\n  use SpeciesMod\n  implicit none\n"
        + prints
        + "\n  print '(a)', by_species(CN_SPECIES_N, 'a', 'b', 'c', 'd', 'e')"
        + "\n  print '(a)', hist_default(.false.)\nend program t\n"
    )
    (tmp_path / "t.F90").write_text(prog)
    subprocess.run(["gfortran", "-o", "t", "t.F90"], cwd=tmp_path, check=True, capture_output=True)
    out = subprocess.run(["./t"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.split("\n")
    expected = [render(k, v, t) for k, t in CASES for v in VARIANTS] + ["d", "inactive"]
    assert out[: len(expected)] == expected
    assert out[1] == "C13_LEAFC_STORAGE" and out[12] == "gC14/m^2/s" and out[16] == "C13 leaf C storage"


def test_template_for_finds_the_element_letter():
    names = {"c12": "CROPSEEDC_DEFICIT", "c13": "C13_CROPSEEDC_DEFICIT", "n": "CROPSEEDN_DEFICIT"}
    assert template_for("fname", names) == "CROPSEED#_DEFICIT"
    assert template_for("fname", {"c12": "PFT_FIRE_CLOSS", "n": "PFT_FIRE_NLOSS"}) == "PFT_FIRE_#LOSS"
    assert template_for("long_name", {"c12": "carbon", "n": "nitrogen"}) is None


INIT = """\
module m
  implicit none
  integer, parameter :: r8 = selected_real_kind(12)
  real(r8), parameter :: spval = 1.e36_r8
  logical :: use_fates = .false.
  type, public :: veg_nutrient_state
     integer :: species
     real(r8), pointer :: leaf(:) => null()
     real(r8), pointer :: froot(:) => null()
  end type veg_nutrient_state
  type, public :: veg_carbon_state
     type(veg_nutrient_state) :: core
  end type veg_carbon_state
  type, public :: veg_nitrogen_state
     type(veg_nutrient_state) :: core
  end type veg_nitrogen_state
contains
  subroutine c_init(this, begp, endp, carbon_type)
    class(veg_carbon_state) :: this
    integer, intent(in) :: begp, endp
    character(len=3), intent(in) :: carbon_type
    this%core%species = 1
    if (use_fates) then
       ! nothing
    else if (carbon_type == 'c12') then
       this%core%leaf(begp:endp) = spval
       call hist_addfld1d (fname='LEAFC', units='gC/m^2', &
            avgflag='A', long_name='leaf C', ptr_patch=this%core%leaf)
       call hist_addfld1d (fname='FROOTC', units='gC/m^2', &
            avgflag='A', long_name='fine root C', ptr_patch=this%core%froot)
    else if (carbon_type == 'c13') then
       this%core%leaf(begp:endp) = spval
       call hist_addfld1d (fname='C13_LEAFC', units='gC13/m^2', &
            avgflag='A', long_name='C13 leaf C', ptr_patch=this%core%leaf)
    end if
  end subroutine c_init
  subroutine n_init(this, begp, endp)
    class(veg_nitrogen_state) :: this
    integer, intent(in) :: begp, endp
    this%core%species = 4
    this%core%leaf(begp:endp) = spval
    call hist_addfld1d (fname='LEAFN', units='gN/m^2', &
         avgflag='A', long_name='leaf N', ptr_patch=this%core%leaf, default='inactive')
    call hist_addfld1d (fname='FROOTN', units='gN/m^2', &
         avgflag='A', long_name='fine root N', ptr_patch=this%core%froot)
  end subroutine n_init
  subroutine hist_addfld1d(fname, units, avgflag, long_name, ptr_patch, default)
    character(len=*), intent(in) :: fname, units, avgflag, long_name
    real(r8), pointer :: ptr_patch(:)
    character(len=*), optional, intent(in) :: default
  end subroutine hist_addfld1d
  pure logical function is_carbon(species)
    integer, intent(in) :: species
    is_carbon = species <= 3
  end function is_carbon
end module m
"""


def setup(tmp_path):
    f = tmp_path / "m.F90"
    f.write_text(INIT)
    lines = INIT.split("\n")

    def sub(n):
        s = next(i for i, l in enumerate(lines) if l.strip().startswith(f"subroutine {n}"))
        e = next(i for i, l in enumerate(lines) if l.strip().startswith(f"end subroutine {n}"))
        return SimpleNamespace(filepath=f, startline=s, endline=e)

    fam = Family("veg_nutrient_state", {"c": "veg_carbon_state", "n": "veg_nitrogen_state"})
    td = {
        "veg_nutrient_state": SimpleNamespace(components={"species": None, "leaf": None, "froot": None}),
        "veg_carbon_state": SimpleNamespace(procedures={"init": "m::c_init"}),
        "veg_nitrogen_state": SimpleNamespace(procedures={"init": "m::n_init"}),
    }
    sd = {"m::c_init": sub("c_init"), "m::n_init": sub("n_init")}
    return f, fam, SimpleNamespace(type_dict=td, subroutine_dict=sd)


def test_history_merge(tmp_path):
    f, fam, fut = setup(tmp_path)
    hm = HistoryMerger([fam], fut)
    hm.build()
    assert not hm.refused, hm.refused
    out = "\n".join(hm.edits[f].apply(hm.lines(f)))
    base = out[out.index("subroutine veg_nutrient_state_init_history") : out.index("end subroutine veg_nutrient_state_init_history")]
    # leaf: c12, c13 (not c14) and N; carbon only when not FATES; N's default differs
    assert "if (.not. (is_carbon(this%species) .and. use_fates)) then" in base
    assert "this%species == CN_SPECIES_C12 .or. this%species == CN_SPECIES_C13 .or. this%species == CN_SPECIES_N" in base
    assert "fname=nutrient_name(this%species, 'LEAF#')" in base
    assert "units=nutrient_units(this%species, 'g#/m^2')" in base
    assert "long_name=nutrient_text(this%species, 'leaf #')" in base
    assert "default=hist_default(this%species == CN_SPECIES_C12 .or. this%species == CN_SPECIES_C13)" in base
    assert "this%leaf(begp:endp) = spval" in base
    # froot: c12 and N
    assert "fname=nutrient_name(this%species, 'FROOT#')" in base
    for name in ("c_init", "n_init"):
        body = out[out.index(f"subroutine {name}") : out.index(f"end subroutine {name}")]
        assert "hist_addfld1d" not in body and "spval" not in body
        assert body.index("species = ") < body.index("call veg_nutrient_state_init_history(this%core, begp, endp)")
