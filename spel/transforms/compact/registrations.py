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
    MacroIf,
    SelectCaseConstruct,
    Statement,
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
    field: str  # component of `this`
    name: str  # history field / restart variable name
    ln: int
    guards: tuple[str, ...]
    inactive: bool = False  # history field with default='inactive'

    def applies_to(self, instance: str) -> bool:
        """Whether the registration's carbon_type guards admit `instance`."""
        iso = next((t for t in ("c13", "c14") if instance.startswith(f"{t}_")), "c12")
        conds = [g for g in self.guards if "carbon_type" in g]
        return all(_admits(g, iso) for g in conds)


def _admits(guard: str, iso: str) -> bool:
    negated = guard.startswith("not(")
    names = [t for t in ("c12", "c13", "c14") if t in guard]
    hit = iso in names
    return not hit if negated else hit


def iter_statements(
    block: BlockStatement, guards: tuple[str, ...] = ()
) -> Iterator[tuple[Statement, tuple[str, ...]]]:
    """Every statement in `block` with the conditions of its enclosing ifs."""
    for stmt in block.statements:
        yield stmt, guards
        match stmt:
            case IfConstruct():
                cond = _norm(stmt.condition)
                yield from iter_statements(stmt.consequence, guards + (cond,))
                prev = [cond]
                for elif_ in stmt.else_ifs:
                    c = _norm(elif_.condition)
                    yield from iter_statements(
                        elif_.consequence,
                        guards + tuple(f"not({p})" for p in prev) + (c,),
                    )
                    prev.append(c)
                if stmt.else_ is not None:
                    yield from iter_statements(
                        stmt.else_.alternative, guards + tuple(f"not({p})" for p in prev)
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
                    yield from iter_statements(case.body, guards + (f"{sel}=={vals}",))
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
    """`this%x(...)` -> 'x'; anything else -> None."""
    try:
        names = [n.lower() for n, _ in flatten_designator(expr)]
    except Exception:
        return None
    if len(names) >= 2 and names[0] == "this":
        return names[1]
    return None


def _keyword_args(call: SubCallStatement) -> dict[str, object]:
    out = {}
    for a in call.function.args:
        if isinstance(a, InfixExpression) and a.operator == "=":
            out[_norm(a.left_expr)] = a.right_expr
    return out


def parse_routine(filepath: Path, startline: int, endline: int):
    """The routine's SubroutineDefinitionConstruct, parsed from the original file."""
    src = Path(filepath).read_text(errors="replace").split("\n")
    lines = [LineTuple(line=src[i], ln=i) for i in range(startline, endline + 1)]
    return Parser(lines=lines).parse_program().statements[0]


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
