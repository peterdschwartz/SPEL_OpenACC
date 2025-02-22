from __future__ import annotations

from collections import namedtuple
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, NamedTuple, Optional, Tuple

from scripts.utilityFunctions import Variable


class ArgLabel(Enum):
    dummy = 1
    globals = 2
    locals = 3


class FortranTypes(Enum):
    CHAR = 1
    LOGICAL = 2
    INT = 3
    REAL = 4
    INHERITED = 5


class FileInfo(NamedTuple):
    fpath: str
    startln: int
    endln: int


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
    field = 8


@dataclass
class ArgNode:
    argn: int
    ident: int | float | str
    kind: IdentKind
    nested_level: int
    node: dict

    def to_dict(self):
        return asdict(self)


@dataclass
class ArgVar:
    node: ArgNode
    var: Variable

    def to_dict(self):
        return asdict(self)


@dataclass
class ArgDesc:
    argn: int  # argument number
    intent: str  # in/out/inout => 'r', 'w', 'rw'
    keyword: bool  # passed as a keyword argument
    key_ident: str  # identifier of keyword
    argtype: ArgType  # overall type and dimension
    locals: list[ArgVar]  # local variables passed to this argument
    globals: list[ArgVar]  # global variables passed to this argument
    dummy_args: list[ArgVar]  # track dummy arguments

    def to_dict(self):
        return asdict(self)

    def increment_arg_number(self):
        """
        Function needed for class methods that have an implicit
        first argument
        """

        def inc_list(argvar_list: list[ArgVar]):
            for v in argvar_list:
                v.node.argn += 1

        self.argn += 1
        inc_list(self.locals)
        inc_list(self.globals)
        inc_list(self.dummy_args)


@dataclass
class CallDesc:
    alias: str  # Interface name, class method alias, or actual name
    fn: str  # real Name of called subroutine
    ln: int  # line number of Subroutine Call
    args: list[ArgDesc]
    # summary of the ArgDesc fields
    globals: list[ArgVar]
    locals: list[ArgVar]
    dummy_args: list[ArgVar]

    def to_dict(self, long=False):
        if long:
            return asdict(self)
        else:
            return {k: v for k, v in asdict(self).items() if k not in ["args"]}

    def aggregate_vars(self) -> None:
        """
        Populates the globals, locals, and dummy_args field for the entire CallDesc
        """
        for arg in self.args:
            temp = [v for v in arg.globals if v not in self.globals]
            self.globals.extend(temp)

            temp = [v for v in arg.locals if v not in self.locals]
            self.locals.extend(temp)

            temp = [v for v in arg.dummy_args if v not in self.dummy_args]
            self.dummy_args.extend(temp)
        return


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


class LineTuple(NamedTuple):
    line: str
    ln: int


class ReadWrite(object):
    """
    Declare namedtuple for readwrite status of variables:
    """

    def __init__(self, status, ln):
        self.status = status
        self.ln = ln

    def __eq__(self, other):
        return self.status == other.status and self.ln == other.ln

    def __repr__(self):
        return f"{self.status}@L{self.ln}"


class SubroutineCall:
    """
    namedtuple to log the subroutines called and their arguments
    to properly match read/write status of variables.
    """

    def __init__(self, subname, args, ln):
        self.subname: str = subname
        self.args: list[Any] = args
        self.ln: int = ln

    def __eq__(self, other):
        return (
            (self.subname == other.subname)
            and (self.args == other.args)
            and (self.ln == other.ln)
        )

    def __str__(self):
        return f"{self.subname}@{self.ln} ({self.args})"

    def __repr__(self):
        return str(self)


class CallTuple(NamedTuple):
    """
    Fields:
        nested
        subname
    """

    nested: int
    subname: str


class CallTree:
    """
    Represents node for subroutine and function calls in a call Tree
    Fields:
        node (CallTuple)
        children list[CallTree]
        parent CallTree|None
    """

    def __init__(self, node):
        self.node: CallTuple = node
        self.children: list[CallTree] = []
        self.parent: Optional[CallTree] = None

    def add_child(self, child: CallTree):
        child.parent = self
        self.children.append(child)

    def traverse_preorder(self):
        """Pre-order traversal (node -> children)."""
        yield self
        for child in self.children:
            yield from child.traverse_preorder()

    def traverse_postorder(self):
        """Post-order traversal (children -> node)."""
        for child in self.children:
            yield from child.traverse_postorder()
        yield self

    def __repr__(self):
        return f"CallTree({self.node.subname}, children={len(self.children)})"

    def print_tree(self, level: int = 0):
        """Recursively prints the tree in a hierarchical format."""
        if level == 0:
            print("CallTree for ", self.node.subname)
        indent = "|--" * level
        print(f"{indent}>{self.node.subname}")

        for child in self.children:
            child.print_tree(level + 1)

    def remove(self):
        """
        Removes this node from the tree by reattaching its children to its parent.
        Raises a ValueError if attempting to remove the root node.
        -- self must be a child node!
        """
        if self.parent is None:
            raise ValueError("CallTree:::Cannot remove the root node.")

        parent = self.parent
        index = parent.children.index(self)

        # Update parent references for this node's children.
        for child in self.children:
            child.parent = parent

        # Short-hand slice syntax to replace child node with it's children
        parent.children[index : index + 1] = self.children

        self.children = []
        self.parent = None
