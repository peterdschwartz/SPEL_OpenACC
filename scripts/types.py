from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from scripts.utilityFunctions import Variable


class FortranTypes(Enum):
    CHAR = 1
    LOGICAL = 2
    INT = 3
    REAL = 4
    INHERITED = 5


@dataclass(frozen=True)
class ArgType:
    datatype: str
    dim: int


class IdentKind(Enum):
    intrinsic = 1
    variable = 2
    function = 3
    infix = 4
    prefix = 5
    slice = 6
    literal = 7


@dataclass
class ArgNode:
    argn: int
    ident: int | float | str
    kind: IdentKind
    nested_level: int
    node: dict


@dataclass
class ArgDesc:
    argn: int  # argument number
    intent: str  # in/out/inout => 'r', 'w', 'rw'
    keyword: bool  # passed as a keyword argument
    argtype: ArgType  # overall type and dimension
    locals: list[Variable]  # local variables passed to this argument
    globals: list[Variable]  # global variables passed to this argument
    dummy_args: list[Variable]  # track dummy arguments


@dataclass
class CallDesc:
    fn: str  # Name of called subroutine
    ln: int  # line number of Subroutine Call
    args: list[ArgDesc]


class PointerAlias:
    """
    Create Class for used objects that are aliased
     i.e.,    `ptr` => 'long_object_name'
    """

    def __init__(self, ptr, obj):
        self.ptr: str = ptr
        self.obj: str = obj

    def __eq__(self, other):
        return (self.ptr == other.ptr) and (self.obj == other.obj)

    def __str__(self):
        if self.ptr:
            return f"{ self.ptr } => { self.obj }"
        else:
            return f"{ self.obj }"

    def __repr__(self):
        return f"{self.ptr} => {self.obj}"


@dataclass
class FunctionReturn:
    """
    Dataclass to package fortran function metadata
    """

    return_type: str
    name: str
    result: str
    start_ln: int
    cpp_start: int


# Named tuple used to store line numbers
# for preprocessed and original files
PreProcTuple = namedtuple("PreProcTuple", ["cpp_ln", "ln"])
