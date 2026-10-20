"""Registrations of a nutrient base type: component paths, templated names, species guards."""
from spel.transforms.compact.registrations import parse_routine, registrations

SRC = """
subroutine vegetation_nutrient_flux_init_history(this, begp, endp)
  type(vegetation_nutrient_flux), intent(inout) :: this
  integer, intent(in) :: begp, endp
  real(r8), pointer :: data1dptr(:)
  this%leaf_to_litter(begp:endp) = spval
  call hist_addfld1d (fname=nutrient_name(this%species, 'LEAF#_TO_LITTER'), units=nutrient_units(this%species, 'g#/m^2/s'), &
       avgflag='A', long_name=nutrient_text(this%species, 'leaf # litterfall'), &
       ptr_patch=this%leaf_to_litter, default=hist_default(this%species == CN_SPECIES_C12))
  if (this%species == CN_SPECIES_N .or. this%species == CN_SPECIES_P) then
     call hist_addfld1d (fname=nutrient_name(this%species, 'POOL_TO_LEAF'), units='g/m^2/s', &
          avgflag='A', long_name='x', ptr_patch=this%pool_to_leaf, default='inactive')
  end if
  if (.not. is_carbon(this%species)) then
     data1dptr => this%core%deep
     call hist_addfld1d (fname='DEEP', units='g', avgflag='A', long_name='y', ptr_patch=data1dptr)
  end if
end subroutine vegetation_nutrient_flux_init_history
"""


def test_species_guards_and_paths(tmp_path):
    f = tmp_path / "x.F90"
    f.write_text(SRC)
    n = SRC.count("\n")
    regs = registrations(parse_routine(f, 1, n - 1))
    by_field = {r.field: r for r in regs}
    assert set(by_field) == {"leaf_to_litter", "pool_to_leaf", "core%deep"}
    leaf = by_field["leaf_to_litter"]
    assert leaf.kind == "hist" and not leaf.inactive  # hist_default(...) is not a literal 'inactive'
    assert leaf.applies_to("veg_cf", "c12") and leaf.applies_to("veg_nf", "n")
    pool = by_field["pool_to_leaf"]
    assert pool.inactive
    assert pool.applies_to("veg_nf", "n") and pool.applies_to("veg_pf", "p")
    assert not pool.applies_to("veg_cf", "c12")
    deep = by_field["core%deep"]
    assert deep.applies_to("veg_nf", "n") and not deep.applies_to("c13_veg_cf", "c13")
    # no element: species guards admit (conservative)
    assert pool.applies_to("veg_cf")


ISO = """
subroutine veg_cf_restart(this, ncid, flag)
  class(vegetation_carbon_flux) :: this
  if (carbon_type == 'c13') then
     call restartvar(ncid=ncid, flag=flag, varname='x13', data=this%x)
  else if (carbon_type /= 'c14') then
     call restartvar(ncid=ncid, flag=flag, varname='x', data=this%y)
  end if
  if (.not. (is_carbon(this%species) .and. use_fates)) then
     call restartvar(ncid=ncid, flag=flag, varname='z', data=this%z)
  end if
end subroutine veg_cf_restart
"""


def test_carbon_type_and_mixed_guards(tmp_path):
    f = tmp_path / "y.F90"
    f.write_text(ISO)
    regs = {r.field: r for r in registrations(parse_routine(f, 1, ISO.count("\n") - 1))}
    assert regs["x"].applies_to("c13_veg_cf", "c13") and not regs["x"].applies_to("veg_cf", "c12")
    assert regs["y"].applies_to("veg_cf", "c12") and not regs["y"].applies_to("c13_veg_cf", "c13")
    assert not regs["y"].applies_to("c14_veg_cf", "c14")
    # use_fates is unknown: the guard cannot be decided, so it admits every element
    assert regs["z"].applies_to("veg_cf", "c12") and regs["z"].applies_to("veg_nf", "n")
