"""
Initialization routines main.F90 calls once after elm_init, for module state
ELM derives at initialization from the subgrid structure (not captured: the
reference branch may not have it). E.g. the refactored subgridAveMod builds
its scale lookups and gridcell -> column maps in init_subgrid_ave
(elm_instMod), which c2g/p2g use.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import spel.scripts.config as cfg

if TYPE_CHECKING:
    from spel.scripts.analyze_subroutines import Subroutine

# routine id -> call statement in main.F90 (bounds_proc: the process bounds)
INIT_HOOKS = {
    "subgridavemod::init_subgrid_ave": "call init_subgrid_ave(bounds_proc)",
}

_regex_field = re.compile(r"\b(\w+_pp)\s*%\s*(\w+)", re.IGNORECASE)
_regex_call = re.compile(r"^\s*call\s+(\w+)", re.IGNORECASE)
_regex_alloc = re.compile(r"\ballocate\s*\((.*)\)", re.IGNORECASE)
_regex_alloc_name = re.compile(r"(?:^|,)\s*(\w+)\s*\(")


def _source(sub: Subroutine) -> list[str]:
    path = Path(sub.filepath)
    if not path.is_absolute():
        path = Path(cfg.E3SM_SRCROOT) / path
    lines = path.read_text().splitlines()
    return lines[sub.startline : sub.endline + 1]


def hook_routines(sub_dict: dict[str, Subroutine], hook: str) -> list[Subroutine]:
    """The hook and the routines of its module it calls (recursively)."""
    module = hook.split("::")[0]
    found: dict[str, Subroutine] = {}
    todo = [hook]
    while todo:
        sid = todo.pop()
        if sid in found or sid not in sub_dict:
            continue
        found[sid] = sub_dict[sid]
        for line in _source(sub_dict[sid]):
            if m := _regex_call.match(line.split("!")[0]):
                todo.append(f"{module}::{m.group(1).lower()}")
    return list(found.values())


def hook_reads_and_allocs(subs: list[Subroutine]) -> tuple[set[str], set[str]]:
    """inst%field the routines read (subgrid structure) and the arrays they allocate."""
    reads: set[str] = set()
    allocs: set[str] = set()
    for sub in subs:
        for line in _source(sub):
            code = line.split("!")[0]
            reads |= {f"{i.lower()}%{f.lower()}" for i, f in _regex_field.findall(code)}
            for args in _regex_alloc.findall(code):
                # allocate(grc_pft_ptr(begg:endg+1), grc_pft_idx(begp:endp)): names at depth 0
                depth, top = 0, []
                for ch in args:
                    depth += ch == "("
                    depth -= ch == ")"
                    top.append(ch if depth == 0 or ch == "(" and depth == 1 else "")
                allocs |= {a.lower() for a in _regex_alloc_name.findall("".join(top))}
    return reads, allocs
