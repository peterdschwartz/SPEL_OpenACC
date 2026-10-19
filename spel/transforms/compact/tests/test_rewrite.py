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
