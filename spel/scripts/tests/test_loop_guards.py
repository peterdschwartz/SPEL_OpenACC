"""Guard-dominated loops: invariant, range, element and mixed conditions on a snippet."""
from spel.scripts.loop_guards import _and_terms, classify_term, guarded_loops

SRC = """
subroutine demo(num, filter, lake, jwt, x, y, flag)
  integer, intent(in) :: num, filter(:), jwt(:)
  logical, intent(in) :: lake, flag(:)
  real(8), intent(inout) :: x(:,:), y(:)
  integer :: fc, c, j
  do fc = 1, num
     c = filter(fc)
     if (.not. lake .and. .not. flag(c)) then
        y(c) = y(c) + 1.0d0
        y(c) = y(c) * 2.0d0
        y(c) = y(c) - 1.0d0
     end if
  end do
  do j = 1, 10
     do fc = 1, num
        c = filter(fc)
        if (j > jwt(c)) then
           x(c,j) = x(c,j) + 1.0d0
           x(c,j) = x(c,j) * 2.0d0
        end if
     end do
  end do
end subroutine demo
"""


def test_and_terms_and_classification():
    assert _and_terms("((.not.lake).and.(.not.flag(c)))") == ["(.not.lake)", "(.not.flag(c))"]
    body = ["     y(c) = y(c) + 1.0d0"]
    assert classify_term("(.not.lake)", {"fc"}, body) == "invariant"
    assert classify_term("(.not.flag(c))", {"fc"}, body) == "element"
    assert classify_term("(j>jwt(c))", {"j", "fc"}, body) == "range"
    assert classify_term("lake", {"fc"}, ["   lake = .false."]) == "element"  # written in the loop: not hoistable


def test_guarded_loops_on_snippet():
    from types import SimpleNamespace

    from spel.scripts.fortran_parser.tests.test_scope_walk import walk

    lines = SRC.splitlines()
    rec = walk(SRC)
    def ln(text):  # 0-based line of the first line containing `text`
        return next(i for i, l in enumerate(lines) if text in l)
    flat_ifs = [
        SimpleNamespace(start_ln=ln("if (.not. lake"), end_ln=ln("end if"), condition="((.not.lake).and.(.not.flag(c)))"),
        SimpleNamespace(start_ln=ln("if (j > jwt(c))"), end_ln=ln("end if", ) + 0, condition="(j>jwt(c))"),
    ]
    # the second `end if` belongs to the j loop
    second_end = [i for i, l in enumerate(lines) if "end if" in l][1]
    flat_ifs[1].end_ln = second_end
    sub = SimpleNamespace(name="demo", filepath="demo.F90", record=rec, flat_ifs=flat_ifs)
    found = guarded_loops(sub, 0.5, source=lines)
    kinds = {(g.loop_index, g.kind): g for g in found}
    mixed = kinds[("fc", "mixed")]
    assert mixed.hoistable == "(.not.lake)" and mixed.fraction >= 0.5 and mixed.range_terms == ""
    rng = kinds[("j", "range")]
    assert rng.if_lines[0] == ln("if (j > jwt(c))") + 1
