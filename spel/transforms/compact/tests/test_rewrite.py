from pathlib import Path

from spel.transforms.compact.rewrite import FileEdits, Rewriter
from spel.transforms.compact.select import Site, statement_end, statement_start

LINES = """\
    associate( a => veg_cf%a, &

               b => veg_cf%b , & ! comment
               c => veg_cf%c )
    do fp = 1, num_soilp
       p = filter_soilp(fp)
       a(p) = b(p) + veg_cf%c(p, 1) + &
              veg_cf % c( p ,2) + other%a(p)
    end do""".split("\n")


def test_statement_lines_skip_blank_continuations():
    assert statement_end(LINES, 0) == 3
    assert statement_start(LINES, 3) == 0
    assert statement_end(LINES, 6) == 7
    assert statement_start(LINES, 7) == 6


def test_site_rewrite_keeps_other_subscripts_and_designators():
    fe = FileEdits(Path("x.F90"), LINES)
    rw = Rewriter.__new__(Rewriter)
    rw.rewrite_site(fe, Site("m::s", 6, "veg_cf%a", "a", "p", "fp"))
    rw.rewrite_site(fe, Site("m::s", 6, "veg_cf%c", "veg_cf%c", "p", "fp"))
    out = fe.result()
    assert out[6] == "       a(k0p+fp) = b(p) + veg_cf%c(k0p+fp, 1) + &"
    assert out[7] == "              veg_cf % c(k0p+fp,2) + other%a(p)"


# --- nutrient-transformed sources: fields on an embedded holder (`veg_cf%core%x`) ---
import shutil
import subprocess
from types import SimpleNamespace

from spel.transforms.compact.holders import Embedding, Holder
from spel.transforms.compact.rewrite import TEMPLATE

NESTED = """\
    associate( agnpp => veg_cf%core%agnpp )
    do fp = 1, num_soilp
       p = filter_soilp(fp)
       agnpp(p) = veg_nf % core % agnpp(p) + veg_cf%core%gpp(p)
    end do""".split("\n")


def test_site_rewrite_three_level_paths():
    fe = FileEdits(Path("x.F90"), NESTED)
    rw = Rewriter.__new__(Rewriter)
    rw.rewrite_site(fe, Site("m::s", 3, "veg_cf%core%agnpp", "agnpp", "p", "fp"))
    rw.rewrite_site(fe, Site("m::s", 3, "veg_nf%core%agnpp", "veg_nf%core%agnpp", "p", "fp"))
    assert fe.result()[3] == "       agnpp(k0p+fp) = veg_nf % core % agnpp(k0p+fp) + veg_cf%core%gpp(p)"


def _rewriter(components, unpack):
    rw = Rewriter.__new__(Rewriter)
    rw.sel = SimpleNamespace(
        components=components, unpack=unpack, dtype="vegetation_nutrient_flux", subgrid="p", holder=None
    )
    return rw


def test_zero_block_on_a_role_component():
    rw = _rewriter({"pool": "always", "x": "use_cn"}, {"pool": True, "x": False})
    classes = rw.classes()
    out = rw.zero_block(classes, "num_patch", "filter_patch", "value_patch", "retrans")
    assert out[1] == "    if (this%retrans%cbuf%bound) then"
    assert "          this%retrans%pool(k0p+fi) = value_patch" in out
    assert "          this%retrans%pool(filter_patch(fi)) = value_patch" in out
    assert any("if (use_cn) then" in l for l in out)


def test_generated_plain_procedures_compile(tmp_path):
    rw = _rewriter({"leaf_to_litter": "always", "pool_to_leaf": "always"}, {"leaf_to_litter": True, "pool_to_leaf": False})
    gen = rw.generated_procedures(
        "vegetation_nutrient_flux", "type(vegetation_nutrient_flux), intent(inout) :: this", rw.classes()
    )
    text = "\n".join(gen)
    assert "subroutine vegetation_nutrient_flux_compact_init(this, beg, end)" in text
    assert "type(vegetation_nutrient_flux), intent(inout) :: this" in text and "class(" not in text
    flat = " ".join(text.split())
    assert "call this%cbuf%add(compact_field('leaf_to_litter',  unpack=.true. ), this%leaf_to_litter)" in flat
    if shutil.which("gfortran") is None:
        return
    module = f"""module NutrientFluxType
  use shr_kind_mod, only : r8 => shr_kind_r8
  use CompactLayoutMod, only : compact_buffer_type, compact_field
  implicit none
  private
  type, public :: vegetation_nutrient_flux
    integer :: species
    real(r8), pointer :: leaf_to_litter(:) => null()
    real(r8), pointer :: pool_to_leaf(:) => null()
    type(compact_buffer_type) :: cbuf
  end type vegetation_nutrient_flux
  public :: vegetation_nutrient_flux_compact_init, vegetation_nutrient_flux_compact_view, vegetation_nutrient_flux_full_view
contains
{text}
end module NutrientFluxType
"""
    (tmp_path / "shr_kind_mod.F90").write_text(
        "module shr_kind_mod\n  integer, parameter :: shr_kind_r8 = selected_real_kind(12)\nend module shr_kind_mod\n"
    )
    (tmp_path / "shr_sys_mod.F90").write_text(
        "module shr_sys_mod\ncontains\n  subroutine shr_sys_abort(msg)\n    character(len=*), optional :: msg\n"
        "    stop 1\n  end subroutine shr_sys_abort\nend module shr_sys_mod\n"
    )
    shutil.copy(TEMPLATE, tmp_path / TEMPLATE.name)
    (tmp_path / "NutrientFluxType.F90").write_text(module)
    for f in ("shr_kind_mod.F90", "shr_sys_mod.F90", TEMPLATE.name, "NutrientFluxType.F90"):
        r = subprocess.run(["gfortran", "-c", "-ffree-line-length-none", f], cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == 0, f"{f}: {r.stderr}"
