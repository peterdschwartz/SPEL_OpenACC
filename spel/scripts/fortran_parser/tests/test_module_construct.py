from spel.scripts.fortran_parser.spel_ast import (
    AccessStatement,
    ModuleConstruct,
    SaveStatement,
    SubroutineDefinitionConstruct,
    TypeDef,
    UseStatement,
)
from spel.scripts.fortran_parser.spel_parser import Parser
from spel.scripts.types import LineTuple

SRC = """\
module m
  use k, only : r8
  implicit none
  save
  private
  public :: t, assignment(=), f
  save :: counter
  integer :: counter = 0
  type, public :: t
     real(r8) :: x
  end type t
  interface f
     module procedure f1
  end interface f
contains
  subroutine f1(a)
    integer :: a
    save = 1
  end subroutine f1
end module m
"""


def parse(src):
    lines = [LineTuple(line=l, ln=i) for i, l in enumerate(src.split("\n"))]
    return Parser(lines=lines).parse_program().statements


def test_module_construct():
    (m,) = parse(SRC)
    assert isinstance(m, ModuleConstruct) and m.name == "m"
    assert (m.lineno, m.contains_ln, m.end_ln) == (0, 14, 19)
    spec = m.spec.statements
    assert isinstance(spec[0], UseStatement)
    access = [s for s in spec if isinstance(s, AccessStatement)]
    assert [(a.access, a.names) for a in access] == [("private", []), ("public", ["t", "assignment(=)", "f"])]
    saves = [s for s in spec if isinstance(s, SaveStatement)]
    assert [s.names for s in saves] == [[], ["counter"]]
    (t,) = [s for s in spec if isinstance(s, TypeDef)]
    assert (t.lineno, t.end_ln) == (8, 10)
    (sub,) = m.subprograms
    assert isinstance(sub, SubroutineDefinitionConstruct) and sub.end_ln == 18


def test_module_procedure_is_not_a_module():
    stmts = parse("interface f\n  module procedure f1\nend interface f\n")
    assert not any(isinstance(s, ModuleConstruct) for s in stmts)
