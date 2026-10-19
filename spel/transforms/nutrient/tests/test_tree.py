from types import SimpleNamespace

from spel.transforms.nutrient.tree import Block, Leaf, read_routine, statement_at

SRC = """\
subroutine s(this, n)
  !$acc routine seq
  class(t) :: this
  integer :: n, i
  if (n > 0) then
     !$acc parallel loop gang &
     !$acc   present(this)
     do i = 1, n
        this%a(i) = 0. ; this%b(i) = 1.
     end do
  else if (n < 0) then
     this%c = 2.
  else
     call foo(this%a, & ! a comment
          this%b)
  endif
  associate(x => this%a)
  x(1) = 3.
  end associate
end subroutine s
"""


def test_read_routine(tmp_path):
    f = tmp_path / "s.F90"
    f.write_text(SRC)
    r = read_routine(SimpleNamespace(filepath=f, startline=0, endline=19))
    assert r.name == "s" and r.dummies == ["this", "n"] and not r.unsupported
    # the routine directive belongs to the specification part
    assert [sp.text for sp, _ in r.header] == [
        "subroutine s(this, n)", "!$acc routine seq", "class(t) :: this", "integer :: n, i",
    ]
    iff, assoc = r.body
    assert isinstance(iff, Block) and (iff.head.first, iff.tail.first, iff.tail.text) == (4, 15, "endif")
    (directive, loop), elif_, else_ = (kids for _, kids in iff.segments)
    assert directive.is_directive and directive.text == "!$acc parallel loop gang present(this)"
    assert (directive.span.first, directive.span.last) == (5, 6)
    a, b = loop.segments[0][1]
    assert (a.text, b.text, a.ln, b.ln) == ("this%a(i) = 0.", "this%b(i) = 1.", 8, 8)
    assert a.guards == ("(n>0)",)
    assert elif_[0].guards == ("not((n>0))", "(n<0)")
    (call,) = else_
    assert call.is_call and call.text == "call foo(this%a, this%b)" and (call.span.first, call.span.last) == (13, 14)
    assert assoc.tail.text == "end associate"


def test_statement_at_directive_continuation():
    lines = ["  !$acc parallel loop &", "  ! a comment", "  !$acc& present(x)", "  do i = 1, n"]
    assert statement_at(lines, 0) == (2, ["!$acc parallel loop present(x)"])


def test_one_line_if_is_a_statement(tmp_path):
    f = tmp_path / "s.F90"
    f.write_text("subroutine s(n)\n  integer :: n, i\n  do i = 1, n\n     if (i > 2) exit\n     if (i == 1) n = 0\n  end do\nend subroutine s\n")
    r = read_routine(SimpleNamespace(filepath=f, startline=0, endline=6))
    (loop,) = r.body
    assert [l.text for l in loop.leaves()] == ["if (i > 2) exit", "if (i == 1) n = 0"] and not r.unsupported
