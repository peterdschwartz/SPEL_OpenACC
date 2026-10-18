import logging
from types import SimpleNamespace

from spel.scripts.fortran_parser.tests.test_Parser import parse_statements
from spel.scripts.process_associate import getAssociateClauseVars
from spel.scripts.types import LineTuple

# col_cf_setvalues-like: an associate block, a second block-local one inside a
# loop over filter chunks, and one inside an if in an internal subprogram
SRC = """subroutine setvalues(this, num_column, filter_column, value_column)
  integer :: fi, blk
  associate(hr => this%hr, nee => this%nee(:))
  do fi = 1, num_column, blk
     associate (idx => filter_column(fi:min(fi+blk-1, num_column)))
     hr(idx) = value_column
     end associate
  end do
  if (value_column > 0) then
     associate(er => this%er)
     er(1) = 0
     end associate
  end if
  end associate
contains
  subroutine helper(x)
    associate(other => x%other)
    other = 1
    end associate
  end subroutine helper
end subroutine setvalues"""


def test_associate_names_come_from_the_syntax_tree():
    tree = parse_statements(SRC).statements[0]
    lines = [LineTuple(line=l, ln=i) for i, l in enumerate(SRC.split("\n"))]
    own_end = next(i for i, l in enumerate(SRC.split("\n")) if l.startswith("contains"))
    sub = SimpleNamespace(
        name="setvalues",
        syntax_tree=tree,
        sub_lines=lines[:own_end],
        logger=logging.getLogger("test"),
    )
    names, start, end = getAssociateClauseVars(sub)
    assert names == {
        "hr": "this%hr",
        "nee": "this%nee",
        "idx": "filter_column",
        "er": "this%er",
    }  # not the internal subprogram's `other`
    assert (start, end) == (2, 3)


def test_no_associate():
    src = "subroutine plain(x)\n  x = 1\nend subroutine plain"
    sub = SimpleNamespace(
        name="plain",
        syntax_tree=parse_statements(src).statements[0],
        sub_lines=[LineTuple(line=l, ln=i) for i, l in enumerate(src.split("\n"))],
        logger=logging.getLogger("test"),
    )
    assert getAssociateClauseVars(sub) == ({}, 0, 0)
