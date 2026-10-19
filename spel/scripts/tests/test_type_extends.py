"""
`type, extends(parent) :: child`: the child gets the parent's components (copies)
and type-bound procedures, its own bindings overriding the parent's.
"""

from spel.scripts.DerivedType import parse_derived_type_definition, resolve_inheritance
from spel.scripts.types import LineTuple

SRC = """\
module m
  type, public :: base_t
     real(r8), pointer :: leaf(:) => null()
   contains
     procedure, public :: SetValues => base_setvalues
     procedure, public :: Clean => base_clean
  end type base_t
  type, public, extends(base_t) :: child_t
     real(r8), pointer :: gpp(:) => null()
   contains
     procedure, public :: SetValues => child_setvalues
  end type child_t
  type, extends(child_t) :: grandchild_t
     integer :: n
  end type grandchild_t
end module m
"""


def test_extends(tmp_path):
    f = tmp_path / "m.F90"
    f.write_text(SRC)
    lines = [LineTuple(line=l, ln=i) for i, l in enumerate(SRC.split("\n"))]
    td = parse_derived_type_definition(lines, "m", str(f))
    assert td["child_t"].parent == "base_t" and td["base_t"].parent is None
    resolve_inheritance(td)
    child, grand = td["child_t"], td["grandchild_t"]
    assert list(child.components) == ["leaf", "gpp"]
    assert list(grand.components) == ["leaf", "gpp", "n"]
    assert child.procedures == {"setvalues": "m::child_setvalues", "clean": "m::base_clean"}
    assert grand.procedures == child.procedures
    # each type has its own copy (allocation bounds are found per type)
    assert child.components["leaf"] is not td["base_t"].components["leaf"]
    assert grand.components["leaf"] is not child.components["leaf"]


NESTED = """\
module m
  type, public :: core_t
     real(r8), pointer :: leaf(:) => null()
  end type core_t
  type, public :: dribbler_t
     real(r8), pointer :: amount(:) => null()
   contains
     procedure, public :: get => dribbler_get
  end type dribbler_t
  type, public :: veg_t
     type(core_t) :: core
     type(dribbler_t) :: dribbler
     real(r8), pointer :: gpp(:) => null()
  end type veg_t
end module m
"""


def test_nested_components(tmp_path):
    from spel.scripts.DerivedType import component_path, resolve_nested

    f = tmp_path / "m.F90"
    f.write_text(NESTED)
    lines = [LineTuple(line=l, ln=i) for i, l in enumerate(NESTED.split("\n"))]
    td = parse_derived_type_definition(lines, "m", str(f))
    resolve_nested(td)
    comps = td["veg_t"].components
    # data-only components are flattened; types with bindings are reached through them
    assert list(comps) == ["core", "dribbler", "gpp", "core%leaf"]
    assert comps["core%leaf"] is not td["core_t"].components["leaf"]
    assert component_path(comps, ["core", "leaf"]) == "core%leaf"
    assert component_path(comps, ["dribbler", "get"]) == "dribbler"
    assert component_path(comps, ["nope"]) is None
