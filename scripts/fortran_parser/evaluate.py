from __future__ import annotations

import sys
from dataclasses import dataclass
from pprint import pprint
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine
    from scripts.utilityFunctions import Variable

from scripts.fortran_parser.environment import Environment
from scripts.fortran_parser.lexer import Lexer
from scripts.fortran_parser.spel_parser import Parser
from scripts.fortran_parser.tracing import Trace
from scripts.types import ArgDesc, ArgNode, ArgType, IdentKind

REAL = "real"
INT = "integer"
CHAR = "character"
INHERITED = "inherited"

map_py_to_f_types = {int: INT, float: REAL,  str : CHAR, }

@dataclass
class SymbolTable:
    vars: List[ArgNode]
    intrinsics: List[ArgNode]
    fns: List[ArgNode]

class ArgTree:
    """
    node: ArgNode
    children: List[ArgTree]
    parent
    """
    def __init__(self, node):
        self.node: ArgNode = node
        self.children: List[ArgTree] = []
        self.parent: Optional[ArgTree] = None

    def add_child(self, child: ArgTree):
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
        return f"ArgTree({self.node.ident}, children={len(self.children)})"

    def print_tree(self, level: int = 0):
        """Recursively prints the tree in a hierarchical format."""
        indent = "|--" * level  # Indentation based on depth level
        print(
            f"{indent}-{self.node.argn} {self.node.ident}(kind: {self.node.kind.name})"
        )

        for child in self.children:
            child.print_tree(level + 1)


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

def construct_arg_tree(
    args,
    env: Environment,
) -> List[ArgTree]:
    """
    Takes a list of expressions from subroutine call, returns
    a List with the ith element corresponding the ith argument expression.
    """
    flat_tree: List[List[ArgNode]] = [[] for i in range(0, len(args))]
    for arg_num, expr in enumerate(args):
        evaluate(arg_num, expr, env, flat_tree, nested=0)

    arg_trees : List[ArgTree] = []
    for nodes in flat_tree:
        arg_trees.append(make_tree(nodes))

    return arg_trees


def make_tree(flat_arg_nodes: List[ArgNode]) -> ArgTree:
    """
    Generates a linked tree structure for each argument node based on nested_level
    """

    root = ArgTree(flat_arg_nodes[0])
    stack = [(flat_arg_nodes[0].nested_level, root)]  # Stack to track parents

    for node in flat_arg_nodes[1:]:
        node_tree = ArgTree(node)

        # Find the correct parent by checking the stack
        while stack and stack[-1][0] >= node.nested_level:
            stack.pop()

        if stack:
            parent_tree = stack[-1][1]
            parent_tree.add_child(node_tree)

        stack.append((node.nested_level, node_tree))

    return root


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
    ast: Dict[str, Any] = stmt.to_dict()

    node_type = ast["Node"]
    if node_type != "SubCallStatement":
        print("Error -- Not a SubCallStatement!\n{input}\n")
        sys.exit(1)
    sub_node: Dict[str, Any] = ast["Sub"]
    sub_name = sub_node["Func"]
    arg_list = sub_node["Args"]

    env: Environment = create_environment(sub, sub_dict)

    arg_tree = construct_arg_tree(arg_list, env)

    arg_desc_list = create_arg_descr(arg_tree, env)

    sort_variables(sub, arg_tree, arg_desc_list)

    for desc in arg_desc_list:
        print("Desc:\n",desc)

    if sub_name in ilist:
        print("Need to resolve interface")

    return



def create_environment(
    sub: Subroutine,
    sub_dict: Dict[str, Subroutine],
) -> Environment:
    """
    Package revelant variables and functions for this subroutine
    """

    for ptr, gv in sub.associate_vars.items():
        sub.dtype_vars[ptr] = sub.dtype_vars[gv]

    variables: dict[str, Variable] = (
        sub.dtype_vars
        | sub.active_global_vars
        | sub.LocalVariables["scalars"]
        | sub.LocalVariables["arrays"]
        | sub.Arguments
    )

    return Environment(variables=variables, fns=sub_dict)


def evaluate(
    argn: int,
    expr,
    env: Environment,
    arg_tree_flat: List[List[ArgNode]],
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
            arg_tree_flat[argn].append(
                ArgNode(argn=argn, ident=var, kind=IdentKind.variable, nested_level=nested, node=expr)
            )

        case "FuncExpression":
            func_name = expr["Func"]

            if func_name in intrinsic_fns:
                arg_node = ArgNode(argn=argn, ident=func_name, kind=IdentKind.intrinsic, nested_level=nested, node=expr,)
            elif func_name in env.fns:
                arg_node = ArgNode(argn=argn, ident=func_name, kind=IdentKind.function, nested_level=nested, node=expr,)
            else:
                arg_node = ArgNode(argn=argn, ident=func_name, kind=IdentKind.variable, nested_level=nested, node=expr,)

            arg_list = expr["Args"]
            arg_tree_flat[argn].append(arg_node)
            for argexpr in arg_list:
                evaluate(argn, argexpr, env, arg_tree_flat, nested + 1)

        case "InfixExpression":
            arg_tree_flat[argn].append(
                ArgNode(
                    argn=argn,
                    ident="InfixExpression",
                    kind=IdentKind.infix,
                    nested_level=nested,
                    node=expr,
                )
            )
            if expr["Op"] != "=":
                expr_list = [
                    expr["Left"],
                    expr["Right"],
                ]
            else:
                expr_list = [expr["Right"]]
            for argexpr in expr_list:
                evaluate(argn, argexpr, env, arg_tree_flat, nested + 1)

        case "PrefixExpression":
            arg_tree_flat[argn].append(
                ArgNode(
                    argn=argn,
                    ident="PrefixExpression",
                    kind=IdentKind.prefix,
                    nested_level=nested,
                    node=expr,
                )
            )
            evaluate(argn, expr["Right"], env, arg_tree_flat, nested + 1)

        case "BoundsExpression":
            arg_tree_flat[argn].append(
                ArgNode(
                    argn=argn,
                    ident=expr["Val"],
                    kind=IdentKind.slice,
                    nested_level=nested,
                    node=expr,
                )
            )
        case "IntegerLiteral":
            arg_tree_flat[argn].append(
                ArgNode(
                    argn=argn,
                    ident=expr["Val"],
                    kind=IdentKind.literal,
                    nested_level=nested,
                    node=expr,
                )
            )
        case "FloatLiteral":
            arg_tree_flat[argn].append(
                ArgNode(
                    argn=argn,
                    ident=expr["Val"],
                    kind=IdentKind.literal,
                    nested_level=nested,
                    node=expr,
                )
            )
        case _:
            print("Didn't account for Node type", node)
            sys.exit(1)
    return


def create_arg_descr(
    arg_tree: List[ArgTree],
    env: Environment,
) -> List[ArgDesc]:
    """
    Function that assigns an Variable type to each function argument and 
    returns an overall description of each argument expression.
    """
    args: List[ArgDesc] = []
    for argn, tree in enumerate(arg_tree):
        arg_type = check_arg_branch(tree, env)
        keyword = check_keyword(tree)
        desc = ArgDesc(argn=argn,
                       intent='',
                       keyword=keyword,
                       argtype=arg_type,
                       locals=[],
                       globals=[],
                       dummy_args=[],
                       )
        args.append(desc)


    return args

def sort_variables(sub: Subroutine, arg_tree: List[ArgTree], args: List[ArgDesc]) -> None:
    """
    Function to fill out the locals and globals field in ArgDesc
    """
    globals = sub.dtype_vars | sub.active_global_vars
    locals = sub.LocalVariables['arrays'] | sub.LocalVariables['scalars']
    for argn, branch in enumerate(arg_tree):
        for node in branch.traverse_preorder():
            if node.node.kind == IdentKind.variable:
                varname = node.node.ident
                if varname in globals:
                    args[argn].globals.append(globals[varname])
                elif varname in locals:
                    args[argn].locals.append(locals[varname])
                elif varname in sub.Arguments:
                    args[argn].dummy_args.append(sub.Arguments[varname])
    return


def check_arg_branch(
    branch: ArgTree,
    env: Environment,
) -> ArgType:
    """
    Function that takes a list of ArgNodes representing the expression
    passed as an argument to a subroutine call.
    """
    return evaluate_arg_node(branch, env)


def evaluate_arg_node(branch: ArgTree, env: Environment) -> ArgType:
    node = branch.node
    match node.kind:
        case IdentKind.variable:
            var = env.variables[node.ident]
            dim = adjust_dim(var.dim, branch) if branch.children else var.dim
            return ArgType(datatype=var.type, dim=dim)
        case IdentKind.intrinsic:
            return intrinsic_fns[node.ident]
        case IdentKind.function:
            fn = env.fns[node.ident]
            res_var: Variable = fn.result
            return ArgType(datatype=res_var.type, dim=res_var.dim)
        case IdentKind.infix:
            return evaluate_infix_arg(branch, env)
        case IdentKind.literal:
            datatype = map_py_to_f_types[type(node.ident)]
            return ArgType(datatype=datatype, dim=0)
        case _:
            return ArgType(datatype="default", dim=0)


def evaluate_infix_arg(branch: ArgTree, env: Environment) -> ArgType:
    """
    Evaluate infix argument type by looking at the Left and Right
    expressions and taking the higher precision of the two.
    """
    child_types = [evaluate_arg_node(child,env) for child in branch.children]
    unique_types = set(child_types)
    if(len(unique_types) == 1):
        return next(iter(unique_types))
    else:
        # There is a mixed datatype expression.
        if(not arg_dim_equals(unique_types) or not valid_mixed_types(unique_types)):
            print("Error -- Infix Operation on non-equal dimension or compatible types")
            branch.print_tree()
            sys.exit(1)
        return next(filter(lambda arg: arg.datatype == REAL, unique_types))

def arg_dim_equals(arg_set: set[ArgType]) -> bool:
    return len({arg.dim for arg in arg_set}) <= 1

def valid_mixed_types(arg_set: set[ArgType]) -> bool:
    return {arg.datatype for arg in arg_set} <= {INT, REAL}

def adjust_dim(dim: int, branch: ArgTree) -> int:
    """
    Take into account indices and slices to get accurate number of dimensions
    """
    assert branch.children != [], "Adjusting dims but children empty"

    for child in branch.children:
        if child.node.kind != IdentKind.slice:
            dim -=1

    assert dim > 0, f"can't have negative dimension:\n {branch.node}"
    return dim

def check_keyword(tree: ArgTree)->bool:
    node = tree.node
    if(node.kind != IdentKind.infix):
        return False
    else:
        return bool(node.node['Op'] == '=')
