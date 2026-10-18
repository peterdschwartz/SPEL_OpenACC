from __future__ import annotations

import re
from typing import TYPE_CHECKING

from spel.scripts.fortran_parser.spel_ast import (
    AssociateConstruct,
    BlockStatement,
    Expression,
    FuncExpression,
    Statement,
)

if TYPE_CHECKING:
    from spel.scripts.analyze_subroutines import Subroutine


def associate_constructs(block: BlockStatement | None) -> list[AssociateConstruct]:
    """
    Every associate construct in `block`, in source order, also those nested in
    loops, if/select/where blocks and other associate constructs.
    """
    found: list[AssociateConstruct] = []
    if block is None:
        return found
    for stmt in block.statements:
        found.extend(_constructs_in(stmt))
    return found


def _constructs_in(stmt: Statement) -> list[AssociateConstruct]:
    found: list[AssociateConstruct] = []
    if isinstance(stmt, AssociateConstruct):
        found.append(stmt)
    if isinstance(stmt, BlockStatement):
        return found + associate_constructs(stmt)
    # blocks of the constructs the scope walker descends into (scope_walk.walk_statement)
    for attr in ("body", "consequence"):
        child = getattr(stmt, attr, None)
        if isinstance(child, BlockStatement):
            found.extend(associate_constructs(child))
    else_ = getattr(stmt, "else_", None)
    if else_ is not None:
        found.extend(associate_constructs(getattr(else_, "alternative", None)))
    for attr in ("else_ifs", "cases", "elsewheres", "branches"):
        for part in getattr(stmt, attr, None) or []:
            for inner in ("consequence", "body"):
                child = getattr(part, inner, None)
                if isinstance(child, BlockStatement):
                    found.extend(associate_constructs(child))
    return found


_regex_remove_index = re.compile(r"\(.*\)")


def selector_name(selector: Expression) -> str:
    """
    The variable a selector refers to: `this%hr` for `this%hr`, `filter_column`
    for an array element or section such as `filter_column(fi:min(fi+n-1,num))`.
    """
    if isinstance(selector, FuncExpression):
        selector = selector.function
    return _regex_remove_index.sub("", str(selector)).strip().lower()


def getAssociateClauseVars(sub: Subroutine, verbose=False):
    """
    Associate names of the subroutine (from its syntax tree) and the variables
    they refer to, with the line of its first associate statement and of the
    first line after it.

    All associate constructs of the routine's own body count (not those of its
    internal subprograms), including block-local ones nested in loops such as
    `associate (idx => filter_column(fi:...))` in col_cf_setvalues. Their names
    are merged; the scope walker (scope_walk.walk_associate) keeps each
    construct's own frame for the access analysis.
    """
    associate_vars: dict[str, str] = {}
    associate_start = 0
    associate_end = 0

    tree = sub.syntax_tree
    constructs = associate_constructs(tree.body if tree is not None else None)
    if not constructs:
        return associate_vars, associate_start, associate_end

    constructs.sort(key=lambda node: node.lineno)
    for node in constructs:
        for name, selector in node.associations.items():
            name = name.lower()
            target = selector_name(selector)
            if associate_vars.get(name, target) != target:
                sub.logger.warning(
                    f"associate name {name} => {target} (line {node.lineno + 1}) "
                    f"differs from an earlier {name} => {associate_vars[name]}; keeping it"
                )
                continue
            associate_vars[name] = target

    # the first associate statement ends the specification part (get_file_info)
    associate_start = constructs[0].lineno
    associate_end = next(
        (lt.ln for lt in sub.sub_lines if lt.ln > associate_start), associate_start
    )

    if verbose:
        sub.logger.info(f"associate variables of {sub.name}:")
        for key, value in associate_vars.items():
            sub.logger.info(f"  {key} => {value}")

    return associate_vars, associate_start, associate_end
