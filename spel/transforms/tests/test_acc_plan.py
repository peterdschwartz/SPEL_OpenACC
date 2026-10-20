"""Loop shape proposals on a snippet: elementwise, interchange, scatter, column-parallel."""
from spel.scripts.record_access import AccessMapper
from spel.scripts.tests.test_record_access import StubSub
from spel.transforms.acc_plan import propose

SRC = """
subroutine demo(num, filter, numv, filterp, colof, x, y, tot)
  implicit none
  integer, intent(in) :: num, filter(:), numv, filterp(:), colof(:)
  real(r8), intent(inout) :: x(:,:), y(:), tot(:)
  integer :: fc, c, j, fp, p
  real(r8) :: tmp
  do j = 1, 10
     do fc = 1, num
        c = filter(fc)
        tmp = x(c,j) * 2.0_r8
        x(c,j) = tmp + y(c)
     end do
  end do
  do j = 1, 10
     do fc = 1, num
        c = filter(fc)
        tot(c) = tot(c) + x(c,j)
     end do
  end do
  do fp = 1, numv
     p = filterp(fp)
     c = colof(p)
     y(c) = y(c) + x(c,1)
  end do
  do fc = 1, num
     c = filter(fc)
     tot(c) = 0.0_r8
     do j = 1, 10
        tot(c) = tot(c) + x(c,j)
        if (tot(c) < 0.0_r8) call endrun('neg')
     end do
  end do
end subroutine demo
"""


def test_shapes():
    sub = StubSub(SRC)
    sub.filepath = None
    mapper = AccessMapper({sub.id: sub})
    props = propose(sub, mapper, source=SRC.splitlines())
    kinds = [p.kind for p in props]
    assert kinds == ["elementwise", "interchange", "scatter", "column-parallel"], kinds
    e, i, s, cp = props
    assert len(e.nest) == 2 and "collapse(2)" in e.directive_lines()[0]
    assert "private(c, tmp)" in e.directive_lines()[0] or "private(c,tmp)" in e.directive_lines()[0].replace(" ", "")
    assert i.carried == {"j": ["tot"]}
    assert s.scatter == {"fp": ["y"]}
    assert cp.directive_lines()[-1].strip().startswith("!$acc loop seq")
    assert cp.unsafe and "endrun" in cp.unsafe[0][1]
