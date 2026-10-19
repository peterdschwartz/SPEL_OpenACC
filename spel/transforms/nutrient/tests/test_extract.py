import re

from spel.transforms.nutrient.extract import entity_count, rename_in_lines

DECL = re.compile(r"^\s*(?:type|class)\s*\(\s*(\w+)\s*\)[^:]*::(.*)$", re.I)
BY_TYPE = {"veg_ns_t": {"leafn": "core%leaf", "npool": "core%pool"}}
INSTANCES = {"veg_ns": "veg_ns_t"}

SRC = """\
module m
contains
  subroutine s(this, other, bounds)
    class(veg_ns_t) :: this
    type(other_t)   :: other
    associate(leafn => veg_ns%leafn, & ! veg_ns%leafn in a comment
              ns => veg_ns )
    this%leafn(p) = other%leafn(p) + ns%npool(p) + veg_ns % npool(p)
    call hist(fname='veg_ns%leafn', ptr=this%leafn_storage)
    !$acc update device(veg_ns%npool) ! veg_ns%npool
    end associate
  end subroutine s
  subroutine t(x)
    type(other_t) :: this
    this%leafn = 1
  end subroutine t
end module m"""


def test_rename_resolves_objects():
    lines = SRC.split("\n")
    n = rename_in_lines(lines, INSTANCES, BY_TYPE, DECL)
    assert lines[5] == "    associate(leafn => veg_ns%core%leaf, & ! veg_ns%leafn in a comment"
    assert lines[7] == "    this%core%leaf(p) = other%leafn(p) + ns%core%pool(p) + veg_ns % core%pool(p)"
    # strings and longer names untouched
    assert lines[8] == "    call hist(fname='veg_ns%leafn', ptr=this%leafn_storage)"
    # directives are renamed like code (not their comments)
    assert lines[9] == "    !$acc update device(veg_ns%core%pool) ! veg_ns%npool"
    # `this` of another type in another routine
    assert lines[14] == "    this%leafn = 1"
    assert n == 5


def test_entity_count():
    assert entity_count("real(r8), pointer :: a(:,:) => null()") == 1
    assert entity_count("real(r8), pointer :: a(:), b(:)") == 2


def test_generic_description():
    from spel.transforms.nutrient.extract import generic_description as g

    olds = {"leafc": "leaf", "totvegc": "totveg"}
    cnp = ("c", "n", "p")
    assert g("allocation to dead stem C storage (gC/m2/s)", cnp, olds) == "allocation to dead stem nutrient storage (g/m2/s)"
    assert g("carbon mass, beginning of time step (gC/m**2)", cnp, olds) == "nutrient mass, beginning of time step (g/m**2)"
    assert g("change in decomposing c pools", cnp, olds) == "change in decomposing nutrient pools"
    assert g("crop leafc harvested", cnp, olds) == "crop leaf harvested"
    assert g("(gC/m2) column-level totvegc (fire)", cnp, olds) == "(g/m2) column-level totveg (fire)"
    assert g("Carbon loss to fire", cnp, olds) == "Nutrient loss to fire"
    # N/P-only fields (groups): their letters only
    assert g("soil mineral N (gN/m3)", ("n", "p"), {}) == "soil mineral nutrient (g/m3)"
    assert g("patch2col (p2c)", cnp, olds) == "patch2col (p2c)"
