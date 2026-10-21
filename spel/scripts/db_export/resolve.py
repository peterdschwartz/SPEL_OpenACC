"""
Resolve the names a routine uses to the module variables they denote.

The analysis records a GLOBAL access by the name the routine uses (the local
alias of `use m, only: a => b`), without the declaring module. Resolution
follows the routine's own `use` statements, its module's variables and the
module head's `use` statements (through re-exports), like the compiler would.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from spel.scripts.DerivedType import component_path
from spel.scripts.fortran_modules import use_items
from spel.scripts.fortran_parser.symbols import SymbolKind
from spel.scripts.module_resolver import ModuleScopes

ModVar = tuple[str, str]  # (module, variable name)


class GlobalResolver:
    def __init__(self, mod_dict: dict, sub_dict: dict, type_dict: dict):
        self.mod_dict = mod_dict
        self.sub_dict = sub_dict
        self.type_dict = type_dict
        self.scopes = ModuleScopes(mod_dict, sub_dict)
        self._cache: dict[tuple[str, str], Optional[ModVar]] = {}
        self._routine_uses: dict[str, list] = {}
        self.unresolved: Counter = Counter()

    # --- names ---
    def resolve(self, sub, name: str) -> Optional[ModVar]:
        """(module, name) of the module variable `name` denotes in `sub`, or None."""
        name = name.lower()
        key = (sub.id, name)
        if key in self._cache:
            return self._cache[key]
        hit = None
        for stmt in self.routine_uses(sub):
            hit = self._via_use(stmt, name, set())
            if hit:
                break
        if hit is None:
            hit = self.resolve_in_module(sub.module, name, set())
        if hit is None:
            var = getattr(sub, "active_global_vars", {}).get(name)
            if var is not None and var.declaration in self.mod_dict:
                hit = (var.declaration, name)
        if hit is None:
            self.unresolved[name] += 1
        self._cache[key] = hit
        return hit

    def resolve_in_module(self, mod: str, name: str, seen: set) -> Optional[ModVar]:
        """`name` as visible at module scope of `mod`: declared there or imported."""
        mod = mod.lower()
        fm = self.mod_dict.get(mod)
        if fm is None or (mod, name) in seen:
            return None
        seen.add((mod, name))
        if name in fm.global_vars:
            return (mod, name)
        for stmt in fm.use_stmts:
            if stmt.lineno < fm.end_of_head_ln:
                hit = self._via_use(stmt, name, seen)
                if hit:
                    return hit
        return None

    def _via_use(self, stmt, name: str, seen: set) -> Optional[ModVar]:
        mod = stmt.module.lower()
        if stmt.has_only:
            for local, remote in use_items(stmt):
                if local == name:
                    return self.resolve_in_module(mod, remote, seen)
            return None
        if mod not in self.mod_dict:
            return None
        sym = self.scopes.exports(mod).symbols.get(name)
        if sym is None or sym.kind is not SymbolKind.VARIABLE:
            return None
        return self.resolve_in_module(mod, name, seen)

    def routine_uses(self, sub) -> list:
        """`use` statements inside `sub` (and its host, for an internal subprogram)."""
        if sub.id in self._routine_uses:
            return self._routine_uses[sub.id]
        ranges = []
        s = sub
        while s is not None and not getattr(s, "library", False):
            ranges.append((s.startline, s.end_stmt_ln))
            s = getattr(s, "host", None) if getattr(s, "is_internal", False) else None
        fm = self.mod_dict.get(sub.module)
        stmts = []
        if fm is not None:
            for stmt in fm.use_stmts:
                if any(a <= stmt.lineno <= b for a, b in ranges):
                    stmts.append(stmt)
        self._routine_uses[sub.id] = stmts
        return stmts

    # --- variables, instances, components ---
    def variable(self, modvar: ModVar):
        return self.mod_dict[modvar[0]].global_vars.get(modvar[1])

    def dtype_of(self, modvar: ModVar):
        """The DerivedType of a module variable, if it is an instance of a known type."""
        var = self.variable(modvar)
        if var is None:
            return None
        return self.type_dict.get(var.type)

    def member(self, dtype, parts: list[str]) -> str:
        """Component path of `parts` ('core', 'leaf') in `dtype`: longest known prefix, else ''."""
        if dtype is None or not parts:
            return ""
        return component_path(dtype.components, [p.lower() for p in parts]) or ""

    def split(self, sub, path: str) -> Optional[dict]:
        """
        Resolve an access path used in `sub` to its module variable:
        {"module", "name", "dtype", "member", "rest"} or None if the base is
        not a module variable. `rest` is the path below the base as written.
        """
        base, _, rest = path.partition("%")
        mv = self.resolve(sub, base)
        if mv is None:
            return None
        return self.describe(mv, rest)

    def describe(self, mv: ModVar, rest: str) -> dict:
        dtype = self.dtype_of(mv)
        parts = rest.split("%") if rest else []
        return {
            "module": mv[0],
            "name": mv[1],
            "dtype": dtype,
            "member": self.member(dtype, parts),
            "rest": rest,
        }

    def canonical(self, sub, path: str) -> Optional[str]:
        """`module::name%rest` for a path used in `sub`, or None."""
        base, _, rest = path.partition("%")
        mv = self.resolve(sub, base)
        if mv is None:
            return None
        return f"{mv[0]}::{mv[1]}" + (f"%{rest}" if rest else "")

    def describe_canonical(self, canon: str) -> dict:
        head, _, rest = canon.partition("%")
        mod, name = head.split("::", 1)
        return self.describe((mod, name), rest)


def var_columns(info: Optional[dict], path: str = "") -> dict:
    """Instance/global columns of a resolved path for the access/trace tables."""
    if info is None:
        return {
            "path": path, "inst_module": "", "instance": "", "member": "",
            "var_module": "", "var_name": "",
        }
    if info["dtype"] is not None:
        return {
            "path": path, "inst_module": info["module"], "instance": info["name"],
            "member": info["member"], "var_module": "", "var_name": "",
        }
    return {
        "path": path, "inst_module": "", "instance": "", "member": "",
        "var_module": info["module"], "var_name": info["name"],
    }
