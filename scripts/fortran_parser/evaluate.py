from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pprint import pprint
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

from scripts.fortran_parser.lexer import Lexer
from scripts.fortran_parser.spel_parser import Parser
from scripts.fortran_parser.tracing import Trace

REAL = "real"
INT = "integer"
CHAR = "character"
INHERITED = "inherited"


@dataclass
class ArgType:
    datatype: str
    dim: int


# Dictionary to hold intrinsic Fortran functions.
intrinsic_fns = {
    "min": ArgType(datatype=REAL, dim=0),
    "max": ArgType(datatype=REAL, dim=0),
    "sin": ArgType(datatype=REAL, dim=0),
    "cos": ArgType(datatype=REAL, dim=0),
    "tan": ArgType(datatype=REAL, dim=0),
    "acos": ArgType(datatype=REAL, dim=0),
    "asin": ArgType(datatype=REAL, dim=0),
    "atan": ArgType(datatype=REAL, dim=0),
    "abs": ArgType(datatype=REAL, dim=0),
    "exp": ArgType(datatype=REAL, dim=0),
    "sqrt": ArgType(datatype=REAL, dim=0),
    "dim": ArgType(datatype=INT, dim=0),
    "mod": ArgType(datatype=INT, dim=0),
    "modulo": ArgType(datatype=INT, dim=0),
    # string
    "trim": ArgType(datatype=CHAR, dim=0),
    "len": ArgType(datatype=INT, dim=0),
    # array
    "size": ArgType(datatype=INT, dim=0),
    "shape": ArgType(datatype=INT, dim=1),
    # "any",
    # "all",
    # math
    "sum": ArgType(datatype=REAL, dim=0),
    "product": ArgType(datatype=REAL, dim=0),
    # "matmul",
    "maxval": ArgType(datatype=REAL, dim=0),
    "minval": ArgType(datatype=REAL, dim=0),
    "maxloc": ArgType(datatype=INT, dim=0),
    "minloc": ArgType(datatype=INT, dim=0),
    # conversion functions
    "int": ArgType(datatype=INT, dim=0),
    "real": ArgType(datatype=REAL, dim=0),
    "dble": ArgType(datatype=REAL, dim=0),
    "epsilon": ArgType(datatype=REAL, dim=0),
}


class IdentKind(Enum):
    intrinsic = 1
    variable = 2
    function = 3


@dataclass
class ArgNode:
    argn: int
    ident: str
    kind: IdentKind
    nested_level: int
    node: str


@Trace.trace_decorator("parse_subroutine_call")
def parse_subroutine_call(
    sub: Subroutine,
    sub_dict: Dict[str, Subroutine],
    input: str,
    ilist: List[str],
):
    """
    Function to generate an AST for a subroutine call string
    """
    lex = Lexer(input=input)
    parser = Parser(lex=lex)
    program = parser.parse_program()
    if len(program.statements) > 1:
        print("Error -- multiple calls in input")
        sys.exit(1)

    stmt = program.statements[0]
    ast = stmt.to_dict()
    pprint(ast, sort_dicts=False)

    node_type = ast["Node"]
    if node_type != "SubCallStatement":
        print("Error -- Not a SubCallStatement!\n{input}\n")
        sys.exit(1)
    sub_node = ast["Sub"]
    sub_name = sub_node["Func"]
    arg_list = sub_node["Args"]

    # The result returned by this function which is a dictionary
    #  <type> => [<identifiers>]
    identifiers = {"vars": [], "fns": [], "intrinsic": []}
    evaluate_args(arg_list, sub_dict, sub, identifiers)

    # Check if subname is an interface
    if sub_name in ilist:
        print("Need to resolve interface")


def evaluate_args(
    args,
    sub_dict: Dict[str, Subroutine],
    sub: Subroutine,
    identifiers,
):
    """
    Takes a list of expressions from subroutine call, returns
    dictionary of each identifier along with it's type (ie, variable, function, intrinsic, etc...)
    """
    for arg_num, expr in enumerate(args):
        evaluate(arg_num, expr, sub_dict, identifiers, nested=0)

    return


def evaluate(
    argn: int,
    expr,
    sub_dict: Dict[str, Subroutine],
    identifiers: Dict[str, List[ArgNode]],
    nested: int,
):
    """
    Function that is called recursively on an ast.expression to categorize
    all the identifiers.
    """
    node = expr["Node"]
    match node:
        case "Ident":
            var = expr["val"]
            identifiers["vars"].append(
                ArgNode(argn, var, IdentKind.variable, nested, node)
            )

        case "FuncExpression":
            func_name = expr["Func"]
            kind = ""

            if func_name in intrinsic_fns:
                kind = "intrinsic"
                arg_node = ArgNode(argn, func_name, IdentKind.intrinsic, nested, node)
            elif func_name in sub_dict:
                kind = "fns"
                arg_node = ArgNode(argn, func_name, IdentKind.function, nested, node)
            else:
                kind = "vars"
                arg_node = ArgNode(argn, func_name, IdentKind.variable, nested, node)

            arg_list = expr["Args"]
            identifiers[kind].append(arg_node)
            for argexpr in arg_list:
                evaluate(argn, argexpr, sub_dict, identifiers, nested + 1)

        case "InfixExpression":
            if expr["Op"] != "=":
                expr_list = [
                    expr["Left"],
                    expr["Right"],
                ]
            else:
                expr_list = [expr["Right"]]
            for argexpr in expr_list:
                evaluate(argn, argexpr, sub_dict, identifiers, nested + 1)

        case "PrefixExpression":
            evaluate(argn, expr["Right"], sub_dict, identifiers, nested + 1)

        case _:
            print("Didn't account for Node type", node)
            sys.exit(1)

    return
