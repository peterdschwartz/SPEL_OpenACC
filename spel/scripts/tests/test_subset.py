import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from spel.scripts.config import spel_mods_dir
from spel.scripts.instrument_elm import CaptureNames, generate_capture_module
from spel.scripts.subset import (
    PRESETS,
    SubsetError,
    SubsetSpec,
    diff_datasets,
    level_keep,
    subset_dataset,
)


def test_parse_presets():
    spec = SubsetSpec.parse("urban")
    assert spec.terms == (PRESETS["urban"][0],)
    assert spec.max_cells == 100 and not spec.custom
    spec = SubsetSpec.parse(" Urban, lake ; max=7")
    assert spec.mask == "urban,lake" and spec.max_cells == 7 and len(spec.terms) == 2
    assert SubsetSpec.parse("crop", max_cells=3).max_cells == 3
    assert "landunit_varcon, only : istcrop" in SubsetSpec.parse("crop").uses()


def test_parse_custom():
    spec = SubsetSpec.parse("landunit: lun_pp%itype(l) == istsoil .and. lun_pp%wtgcell(l) > 0.5_r8")
    assert spec.custom and spec.terms[0].level == "l"
    assert "pftvarcon" in spec.uses()
    # a comma inside a custom expression is not a preset list
    spec = SubsetSpec.parse("patch: max(veg_pp%wtgcell(p), 0._r8) > 0.1_r8")
    assert spec.terms[0].level == "p"
    assert SubsetSpec.from_json(spec.to_json()) == spec


@pytest.mark.parametrize(
    "text",
    ["suburban", "landunit: ", "landunit: lun_pp%urbpoi(c)", "landunit: f(l; x)",
     "column: (col_pp%active(c)", "urban; max=0"],
)
def test_parse_errors(text):
    with pytest.raises(SubsetError):
        SubsetSpec.parse(text)


def test_capture_module():
    names = CaptureNames.for_case("urb_sub")
    plain = generate_capture_module(names, ["energyflux_vars"])
    assert "spel_select_subset" not in plain and "nc_subset" not in plain
    spec = SubsetSpec.parse("urban; max=5")
    text = generate_capture_module(names, ["energyflux_vars"], subset=spec)
    assert "integer, parameter :: spel_subset_max = 5" in text
    assert "if (lun_pp%urbpoi(l) .and. lun_pp%wtgcell(l) > 0._r8) match(lun_pp%gridcell(l)) = .true." in text
    assert "call write_elmtypes(io_inputs, spel_bounds_sub," in text
    assert "call write_elmtypes(io_outputs, spel_bounds_sub," in text
    assert text.count("call nc_subset_activate(spel_sub)") == 3
    assert text.count("call nc_subset_deactivate()") == 3


# --------------------------------------------------------------------------
# nc_io's subset writer vs the offline subsetter
# --------------------------------------------------------------------------
# 4 gridcells with 2/1/3/2 landunits, one topounit each. The process bounds
# don't start at 1 (as on an MPI rank other than 0).
ROUNDTRIP = r"""
program subset_roundtrip
  use netcdf
  use nc_io
  implicit none
  type :: bounds_t
     integer :: beg(5), end(5)
  end type
  integer, parameter :: begg = 11, ng = 4, begt = 11, begl = 101, nl = 8
  integer, parameter :: begc = 201, nc = 10, begp = 301, np = 13
  integer, parameter :: nl_g(ng) = [2, 1, 3, 2]
  integer, parameter :: nc_l(nl) = [1, 2, 1, 1, 2, 1, 1, 1]
  integer, parameter :: np_c(nc) = [1, 2, 1, 1, 1, 2, 1, 1, 2, 1]
  integer :: top_gridcell(begt:begt+ng-1), top_downhill(begt:begt+ng-1)
  integer :: grc_coli(begg:begg+ng-1), grc_colf(begg:begg+ng-1), grc_gindex(begg:begg+ng-1)
  integer :: lun_gridcell(begl:begl+nl-1)
  logical :: lun_urbpoi(begl:begl+nl-1)
  integer :: col_landunit(begc:begc+nc-1), col_gridcell(begc:begc+nc-1)
  integer :: veg_column(begp:begp+np-1), veg_gridcell(begp:begp+np-1)
  real(8) :: veg_x(begp:begp+np-1, 3)
  type(spel_subset_type), target :: sub
  type(bounds_t) :: b_full, b_sub
  logical :: keep(begg:begg+ng-1)
  integer :: g, l, c, p, k

  l = begl; c = begc; p = begp
  do g = begg, begg + ng - 1
     top_gridcell(g) = g
     grc_gindex(g) = 1000 + g
     grc_coli(g) = c
     do k = 1, nl_g(g - begg + 1)
        lun_gridcell(l) = g
        lun_urbpoi(l) = mod(l, 3) == 0
        do c = c, c + nc_l(l - begl + 1) - 1
           col_landunit(c) = l
           col_gridcell(c) = g
           veg_column(p:p + np_c(c - begc + 1) - 1) = c
           veg_gridcell(p:p + np_c(c - begc + 1) - 1) = g
           p = p + np_c(c - begc + 1)
        end do
        l = l + 1
     end do
     grc_colf(g) = c - 1
  end do
  ! kept t12 -> kept t14, kept t14 -> dropped t13
  top_downhill = [13, 14, -9999, 13]
  do k = 1, 3
     do p = begp, begp + np - 1
        veg_x(p, k) = p + 0.25d0*k
     end do
  end do

  keep = .false.
  keep(begg + 1) = .true.
  keep(begg + 3) = .true.
  call nc_subset_set_level(sub, 1, begg, keep)
  call nc_subset_set_level(sub, 2, begt, keep(top_gridcell))
  call nc_subset_set_level(sub, 3, begl, keep(lun_gridcell))
  call nc_subset_set_level(sub, 4, begc, keep(col_gridcell))
  call nc_subset_set_level(sub, 5, begp, keep(veg_gridcell))
  sub%mask = 'test mask'
  sub%gindex = pack(grc_gindex, keep)

  b_full%beg = [begg, begt, begl, begc, begp]
  b_full%end = b_full%beg + [ng, ng, nl, nc, np] - 1
  b_sub%beg = 1
  do k = 1, 5
     b_sub%end(k) = nc_subset_count(sub, k)
  end do

  call write_file('full.nc', b_full)
  call nc_subset_activate(sub)
  call write_file('sub.nc', b_sub)
  call nc_subset_deactivate()

contains

  subroutine write_file(fn, b)
    character(len=*), intent(in) :: fn
    type(bounds_t), intent(in) :: b
    character(len=1), parameter :: lev(5) = ['g', 't', 'l', 'c', 'p']
    character(len=32) :: dn(2)
    integer :: ncid, varid, t, i
    ncid = nc_create_or_open_file(fn, create_file)
    do i = 1, 5
       call nc_define_var(ncid, 0, [0], dn, 'bounds__beg'//lev(i), nf90_int, varid, .false.)
       call nc_define_var(ncid, 0, [0], dn, 'bounds__end'//lev(i), nf90_int, varid, .false.)
    end do
    call def1(ncid, 'topo', 'top_pp__gridcell', nf90_int, lbound(top_gridcell), ubound(top_gridcell))
    call def1(ncid, 'topo', 'top_pp__downhill_ti', nf90_int, lbound(top_downhill), ubound(top_downhill))
    call def1(ncid, 'gridcell', 'grc_pp__coli', nf90_int, lbound(grc_coli), ubound(grc_coli))
    call def1(ncid, 'gridcell', 'grc_pp__colf', nf90_int, lbound(grc_colf), ubound(grc_colf))
    call def1(ncid, 'gridcell', 'grc_pp__gindex', nf90_int, lbound(grc_gindex), ubound(grc_gindex))
    call def1(ncid, 'landunit', 'lun_pp__gridcell', nf90_int, lbound(lun_gridcell), ubound(lun_gridcell))
    call def1(ncid, 'landunit', 'lun_pp__urbpoi', nf90_int, lbound(lun_urbpoi), ubound(lun_urbpoi))
    call def1(ncid, 'column', 'col_pp__landunit', nf90_int, lbound(col_landunit), ubound(col_landunit))
    call def1(ncid, 'column', 'col_pp__gridcell', nf90_int, lbound(col_gridcell), ubound(col_gridcell))
    call def1(ncid, 'patch', 'veg_pp__column', nf90_int, lbound(veg_column), ubound(veg_column))
    call def1(ncid, 'patch', 'veg_pp__gridcell', nf90_int, lbound(veg_gridcell), ubound(veg_gridcell))
    dn(1) = 'patch'; dn(2) = 'nlev'
    call nc_define_var(ncid, 2, shape(veg_x), dn, 'veg_x', nf90_double, varid, .true.)
    call nc_put_bounds_att(ncid, varid, 2, dn, lbound(veg_x), ubound(veg_x))
    call check(nf90_enddef(ncid))
    do i = 1, 5
       call nc_write_var_scalar(ncid, b%beg(i), 'bounds__beg'//lev(i))
       call nc_write_var_scalar(ncid, b%end(i), 'bounds__end'//lev(i))
    end do
    do t = 1, 2
       call w1(ncid, 'topo', top_gridcell, 'top_pp__gridcell', t)
       call w1(ncid, 'topo', top_downhill, 'top_pp__downhill_ti', t)
       call w1(ncid, 'gridcell', grc_coli, 'grc_pp__coli', t)
       call w1(ncid, 'gridcell', grc_colf, 'grc_pp__colf', t)
       call w1(ncid, 'gridcell', grc_gindex, 'grc_pp__gindex', t)
       call w1(ncid, 'landunit', lun_gridcell, 'lun_pp__gridcell', t)
       call nc_write_var_array(ncid, 1, shape(lun_urbpoi), [character(len=32) :: 'landunit'], &
                               lun_urbpoi, 'lun_pp__urbpoi', t)
       call w1(ncid, 'column', col_landunit, 'col_pp__landunit', t)
       call w1(ncid, 'column', col_gridcell, 'col_pp__gridcell', t)
       call w1(ncid, 'patch', veg_column, 'veg_pp__column', t)
       call w1(ncid, 'patch', veg_gridcell, 'veg_pp__gridcell', t)
       call nc_write_var_array(ncid, 2, shape(veg_x), [character(len=32) :: 'patch', 'nlev'], &
                               reshape(veg_x, [size(veg_x)]), 'veg_x', t)
    end do
    call check(nf90_close(ncid))
  end subroutine write_file

  subroutine def1(ncid, dim, name, xtype, lb, ub)
    integer, intent(in) :: ncid
    character(len=*), intent(in) :: dim, name
    integer, intent(in) :: xtype, lb(1), ub(1)
    character(len=32) :: dn(1)
    integer :: varid
    dn(1) = dim
    call nc_define_var(ncid, 1, ub - lb + 1, dn, name, xtype, varid, .true.)
    call nc_put_bounds_att(ncid, varid, 1, dn, lb, ub)
  end subroutine def1

  subroutine w1(ncid, dim, var, name, t)
    integer, intent(in) :: ncid
    character(len=*), intent(in) :: dim, name
    integer, intent(in) :: var(:), t
    character(len=32) :: dn(1)
    dn(1) = dim
    call nc_write_var_array(ncid, 1, shape(var), dn, var, name, t)
  end subroutine w1
end program subset_roundtrip
"""


def _netcdf_fortran_flags() -> list[str] | None:
    if shutil.which("gfortran") is None or shutil.which("pkg-config") is None:
        return None
    res = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "netcdf-fortran"], capture_output=True, text=True
    )
    if res.returncode != 0:
        return None
    libdir = subprocess.run(
        ["pkg-config", "--variable=libdir", "netcdf-fortran"], capture_output=True, text=True
    ).stdout.strip()
    return res.stdout.split() + ([f"-Wl,-rpath,{libdir}"] if libdir else [])


@pytest.fixture(scope="module")
def roundtrip(tmp_path_factory) -> Path:
    flags = _netcdf_fortran_flags()
    if flags is None:
        pytest.skip("needs gfortran and netcdf-fortran (pkg-config)")
    d = tmp_path_factory.mktemp("subset")
    (d / "prog.F90").write_text(ROUNDTRIP)
    cmd = ["gfortran", "-ffree-line-length-none", str(Path(spel_mods_dir) / "nc_io.F90"),
           "prog.F90", "-o", "prog", *flags]
    res = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    res = subprocess.run(["./prog"], cwd=d, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    return d


def test_fortran_subset_matches_offline(roundtrip):
    full, sub = roundtrip / "full.nc", roundtrip / "sub.nc"
    keep = level_keep(full, [2, 4])
    assert [int(k.sum()) for k in keep.values()] == [2, 2, 3, 3, 4]
    offline = roundtrip / "offline.nc"
    subset_dataset(full, offline, keep, mask="test mask", gindex=[1012, 1014])
    assert diff_datasets(sub, offline) == []


def test_fortran_subset_renumbers(roundtrip):
    import netCDF4

    with netCDF4.Dataset(roundtrip / "sub.nc") as ds:
        ds.set_auto_mask(False)
        val = lambda n: ds[n][1].tolist()  # second time step
        assert {n: int(ds[f"bounds__{n}"][...]) for n in ("begg", "endg", "endl", "endc", "endp")} == \
            {"begg": 1, "endg": 2, "endl": 3, "endc": 3, "endp": 4}
        # kept: g12, g14; l103, l107, l108; c204, c209, c210; p305, p311-313
        assert val("lun_pp__gridcell") == [1, 2, 2]
        assert val("lun_pp__urbpoi") == [0, 0, 1]
        assert val("col_pp__landunit") == [1, 2, 3]
        assert val("col_pp__gridcell") == [1, 2, 2]
        assert val("veg_pp__column") == [1, 2, 2, 3]
        assert val("grc_pp__coli") == [1, 2] and val("grc_pp__colf") == [1, 3]
        assert val("grc_pp__gindex") == [1, 2]
        assert val("top_pp__downhill_ti") == [2, -9999]
        x = ds["veg_x"][1]  # netCDF order (nlev, patch)
        np.testing.assert_array_equal(x[0], [305.25, 311.25, 312.25, 313.25])
        np.testing.assert_array_equal(x[2], [305.75, 311.75, 312.75, 313.75])
        assert ds["veg_x"].lbounds.tolist() == [1, 1] and ds["veg_x"].ubounds.tolist() == [4, 3]
        assert ds.spel_subset_mask == "test mask"
        assert ds.spel_subset_gindex.tolist() == [1012, 1014]
