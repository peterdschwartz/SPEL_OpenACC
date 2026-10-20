"""
History and restart registrations of derived-type components.

`hist_addfld*` and `restartvar` are commented out of the analyzed sources, so
the type's init and restart routines are parsed again from the original
files. A registration through a temporary pointer (``data2dptr => this%x(:,1:n)``
then ``ptr_col=data2dptr``) is attributed to the pointer's target.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from spel.scripts.fortran_parser.scope_walk import flatten_designator
from spel.scripts.fortran_parser.spel_ast import (
    AssociateConstruct,
    BlockStatement,
    DoLoop,
    DoWhile,
    ExpressionStatement,
    IfConstruct,
    InfixExpression,
    FuncExpression,
    MacroIf,
    PrefixExpression,
    SelectCaseConstruct,
    Statement,
    StringLiteral,
    SubCallStatement,
    WhereConstruct,
)
from spel.scripts.fortran_parser.spel_parser import Parser
from spel.scripts.types import LineTuple

HIST_CALLS = ("hist_addfld1d", "hist_addfld2d", "hist_addfld_decomp")
HIST_POINTERS = ("ptr_patch", "ptr_col", "ptr_lunit", "ptr_gcell", "ptr_lnd", "ptr_atm")
RESTART_CALL = "restartvar"


@dataclass(frozen=True)
class Registration:
    kind: str  # "hist" | "restart"
    field: str  # component path of `this` (x, core%x)
    name: str  # history field / restart variable name
    ln: int
    guards: tuple  # Guard (normalized text with its parsed condition) per enclosing if
    inactive: bool = False  # history field with default='inactive'

    def applies_to(self, instance: str, element: str = "") -> bool:
        """
        Whether the registration's guards admit `instance`: `carbon_type` guards
        (c12/c13/c14 from the instance prefix) and, for a registration of a
        nutrient base type, species guards (`this%species == CN_SPECIES_N`,
        `is_carbon(this%species)`) for `element` (c12, c13, c14, n, p).
        Evaluated on the parsed conditions; a guard that cannot be evaluated
        admits (conservative: the field counts as registered).
        """
        iso = next((t for t in ("c13", "c14") if instance.startswith(f"{t}_")), "c12")
        for g in self.guards:
            value = g.evaluate(iso, element) if isinstance(g, Guard) else None
            if value is False:
                return False
        return True


class Guard(str):
    """
    A normalized `if` condition (the text, for grouping and reports) with its
    parsed expression; `negated` for the `not(...)` of an else branch.
    """

    node: object
    negated: bool

    def __new__(cls, text: str, node=None, negated: bool = False):
        obj = super().__new__(cls, text)
        obj.node = node
        obj.negated = negated
        return obj

    def evaluate(self, iso: str, element: str):
        """True/False if the condition is decided by `iso`/`element`, else None."""
        value = _eval(self.node, iso, element) if self.node is not None else None
        if value is None or not self.negated:
            return value
        return not value


def _designator(expr) -> str | None:
    """`this%species` -> 'this%species', `carbon_type` -> 'carbon_type'; None if not a designator."""
    try:
        return "%".join(n.lower() for n, _ in flatten_designator(expr))
    except Exception:
        return None


def _eval(node, iso: str, element: str):
    """Three-valued evaluation of a guard's carbon_type and species terms."""
    match node:
        case PrefixExpression() if node.operator.strip().lower() == ".not.":
            v = _eval(node.right_expr, iso, element)
            return None if v is None else not v
        case InfixExpression():
            op = node.operator.strip().lower()
            if op in (".and.", ".or."):
                a, b = _eval(node.left_expr, iso, element), _eval(node.right_expr, iso, element)
                values = {a, b}
                if op == ".and.":
                    return False if False in values else (True if values == {True} else None)
                return True if True in values else (False if values == {False} else None)
            if op in ("==", ".eq.", "/=", ".ne."):
                equal = op in ("==", ".eq.")
                for left, right in ((node.left_expr, node.right_expr), (node.right_expr, node.left_expr)):
                    name = _designator(left)
                    if name == "carbon_type" and isinstance(right, StringLiteral):
                        hit = str(right.value).strip("'\"").lower() == iso
                        return hit if equal else not hit
                    if name == "this%species":
                        other = _designator(right) or ""
                        if other.startswith("cn_species_") and element:
                            hit = other[len("cn_species_"):] == element
                            return hit if equal else not hit
                        return None
            return None
        case FuncExpression():
            if _designator(node.function) == "is_carbon" and element:
                return element in ("c12", "c13", "c14")
            return None
    return None


def iter_statements(
    block: BlockStatement, guards: tuple[str, ...] = ()
) -> Iterator[tuple[Statement, tuple[str, ...]]]:
    """Every statement in `block` with the conditions of its enclosing ifs."""
    for stmt in block.statements:
        yield stmt, guards
        match stmt:
            case IfConstruct():
                cond = Guard(_norm(stmt.condition), stmt.condition)
                yield from iter_statements(stmt.consequence, guards + (cond,))
                prev = [cond]
                for elif_ in stmt.else_ifs:
                    c = Guard(_norm(elif_.condition), elif_.condition)
                    yield from iter_statements(
                        elif_.consequence,
                        guards + tuple(Guard(f"not({p})", p.node, True) for p in prev) + (c,),
                    )
                    prev.append(c)
                if stmt.else_ is not None:
                    yield from iter_statements(
                        stmt.else_.alternative, guards + tuple(Guard(f"not({p})", p.node, True) for p in prev)
                    )
            case DoLoop() | DoWhile() | AssociateConstruct():
                yield from iter_statements(stmt.body, guards)
            case WhereConstruct():
                yield from iter_statements(stmt.body, guards)
                for ew in stmt.elsewheres:
                    yield from iter_statements(ew.body, guards)
            case SelectCaseConstruct():
                sel = _norm(stmt.selector)
                for case in stmt.cases:
                    vals = ",".join(_norm(v) for v in case.values or []) or "default"
                    yield from iter_statements(case.body, guards + (Guard(f"{sel}=={vals}"),))
            case MacroIf():
                yield from iter_statements(stmt.body, guards)
                for branch in stmt.branches:
                    yield from iter_statements(branch.body, guards)
            case BlockStatement():
                yield from iter_statements(stmt, guards)


def line_guards(block: BlockStatement) -> dict[int, tuple[str, ...]]:
    return {stmt.lineno: g for stmt, g in iter_statements(block)}


def _norm(expr) -> str:
    return str(expr).replace(" ", "").lower()


def _component(expr) -> str | None:
    """`this%x(...)` -> 'x', `this%core%x(...)` -> 'core%x'; anything else -> None."""
    try:
        names = [n.lower() for n, _ in flatten_designator(expr)]
    except Exception:
        return None
    if len(names) >= 2 and names[0] == "this":
        return "%".join(names[1:])
    return None


def _keyword_args(call: SubCallStatement) -> dict[str, object]:
    out = {}
    for a in call.function.args:
        if isinstance(a, InfixExpression) and a.operator == "=":
            out[_norm(a.left_expr)] = a.right_expr
    return out


def parse_routine(
    filepath: Path, startline: int, endline: int, keep_directives: bool = False, keep_string_case: bool = False
):
    """The routine's SubroutineDefinitionConstruct, parsed from the original file."""
    src = Path(filepath).read_text(errors="replace").split("\n")
    lines = [LineTuple(line=src[i], ln=i) for i in range(startline, endline + 1)]
    parser = Parser(lines=lines, keep_directives=keep_directives, keep_string_case=keep_string_case)
    return parser.parse_program().statements[0]


def registrations(tree) -> list[Registration]:
    out: list[Registration] = []
    pointers: dict[str, str] = {}
    for stmt, guards in iter_statements(tree.body):
        if isinstance(stmt, ExpressionStatement):
            expr = stmt.expression
            if isinstance(expr, InfixExpression) and expr.operator == "=>":
                ptr = _norm(expr.left_expr)
                comp = _component(expr.right_expr)
                if comp is not None:
                    pointers[ptr] = comp
                else:
                    pointers.pop(ptr, None)
            continue
        if not isinstance(stmt, SubCallStatement):
            continue
        name = _norm(stmt.function.function)
        kwargs = _keyword_args(stmt)
        if name in HIST_CALLS:
            keys, kind = HIST_POINTERS, "hist"
        elif name == RESTART_CALL:
            keys, kind = ("data",), "restart"
        else:
            continue
        for key in keys:
            if key not in kwargs:
                continue
            value = kwargs[key]
            comp = _component(value) or pointers.get(_norm(value))
            if comp is None:
                continue
            label = kwargs.get("fname", kwargs.get("varname"))
            default = _norm(kwargs.get("default", ""))
            out.append(
                Registration(
                    kind,
                    comp,
                    _norm(label) if label is not None else "?",
                    stmt.lineno,
                    guards,
                    inactive=(default == "inactive"),
                )
            )
    return out
