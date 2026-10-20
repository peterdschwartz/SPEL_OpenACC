"""
Loops whose body is dominated by an `if` block: candidates for a design change.

Four shapes are reported, from the analysis (`Subroutine.flat_ifs` and the
record's `loop_nest`), for every loop that is not nested in another loop:

- `invariant`: the condition reads only scalars that the loop never writes and
  that are not indexed by a loop index (e.g. `if (.not. lake)` on a dummy
  argument inside a column loop, ch4_prod). The test runs once per element for
  nothing and stops the compiler from vectorizing the body; hoist it and split
  the loop.
- `range`: the condition compares a loop index with a per-element bound
  (`j > jwt(c)`, `j >= snl(c)+1`): a loop limit written as an `if`.
- `element`: the condition reads a per-element value or flag (`lakpoi(l)`,
  `itype(c)`, a state threshold). Most elements of the filter take one branch;
  a filter per branch, or a specialized routine, turns the branch into a bound.
- `mixed`: a conjunction of the above; the report names the hoistable terms and
  the range terms separately.

The fraction is the lines of the `if` block over the lines of the loop body;
only blocks covering at least `min_fraction` of the body are listed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

SUBGRID_FLAGS = re.compile(
    r"\b(lakpoi|urbpoi|itype|ltype|ctype|is_bareground|is_fates|ispolygon|wtgcell|active|"
    r"ist(soil|crop|wet|ice|dlak|ice_mec)|icol_\w+|landunit|column|gridcell)\b",
    re.IGNORECASE,
)
IDENT = re.compile(r"[A-Za-z_]\w*(?:%\w+)*")
FORTRAN_KEYWORDS = {"not", "and", "or", "eqv", "neqv", "true", "false", "if", "then", "present"}


@dataclass(frozen=True)
class GuardedLoop:
    routine: str
    file: str
    loop_lines: tuple[int, int]      # 1-based, inclusive
    if_lines: tuple[int, int]        # 1-based, inclusive
    condition: str
    kind: str                        # 'invariant' | 'range' | 'element' | 'mixed'
    fraction: float
    loop_index: Optional[str]
    hoistable: str = ""              # the loop-invariant terms of a 'mixed' condition
    range_terms: str = ""            # the index-vs-bound terms (loop-limit candidates)

    def __str__(self) -> str:
        extra = ""
        if self.hoistable:
            extra += f" hoist[{self.hoistable}]"
        if self.range_terms:
            extra += f" bounds[{self.range_terms}]"
        return (f"{self.file}:{self.loop_lines[0]}-{self.loop_lines[1]} do {self.loop_index or '?'}: "
                f"{self.kind:9s} {100 * self.fraction:3.0f}% under if ({self.condition[:60]}){extra}  ({self.routine})")


def _names(condition: str) -> set[str]:
    return {m.group(0).lower() for m in IDENT.finditer(condition)} - FORTRAN_KEYWORDS


def _writes_in(lines: list[str], names: set[str]) -> bool:
    """Any of `names` (base names) assigned in `lines`?"""
    bases = {n.split("%")[0] for n in names}
    if not bases:
        return False
    pat = re.compile(r"^\s*(" + "|".join(map(re.escape, sorted(bases))) + r")\s*(\(.*\))?\s*=[^=]", re.IGNORECASE)
    return any(pat.match(ln) for ln in lines)


def _and_terms(cond: str) -> list[str]:
    """Top-level `.and.` terms of a normalized condition (outer parentheses stripped)."""
    s = cond.strip()
    while s.startswith("(") and s.endswith(")") and _balanced(s[1:-1]):
        s = s[1:-1].strip()
    terms, depth, start = [], 0, 0
    i = 0
    low = s.lower()
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and low.startswith(".and.", i):
            terms.append(s[start:i].strip()); start = i + 5; i += 5; continue
        i += 1
    terms.append(s[start:].strip())
    return [tm for tm in terms if tm]


def _balanced(s: str) -> bool:
    depth = 0
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if depth < 0:
            return False
    return depth == 0


def classify_term(term: str, indices: set[str], body: list[str]) -> str:
    """'range' (loop index vs a bound), 'invariant' (scalars the loop doesn't write), else 'element'."""
    names = _names(term)
    indexed = re.search(r"\w\s*\(", term) is not None  # an identifier followed by '(' (array element or call)
    ops = r"(?:<=|>=|==|/=|<|>|\.[lg][te]\.|\.[en]q\.)"
    bare = "|".join(re.escape(i) for i in sorted(indices)) if indices else None
    if bare and re.search(rf"(?<![\w%])(?:{bare})\s*{ops}|{ops}\s*(?:{bare})(?![\w(])", term, re.IGNORECASE):
        return "range"  # the loop index itself is compared with a bound
    if not indexed and names and not (names & indices) and not _writes_in(body, names):
        return "invariant"
    return "element"


def guarded_loops(sub, min_fraction: float = 0.5, source: Optional[list[str]] = None) -> list[GuardedLoop]:
    """Dominant `if` blocks inside the outermost loops of `sub` (see the module doc)."""
    rec = getattr(sub, "record", None)
    nest = getattr(rec, "loop_nest", None) if rec else None
    if not nest:
        return []
    if source is None:
        source = Path(sub.filepath).read_text().splitlines()
    out: list[GuardedLoop] = []
    loops = [L for lp in (nest if isinstance(nest, list) else [nest]) for L in lp.walk() if L.depth == 0]
    for L in loops:
        body_len = L.end_ln - L.start_ln - 1
        if body_len <= 0:
            continue
        indices = {x.index.lower() for x in L.walk() if x.index}
        body = source[L.start_ln + 1 : L.end_ln]
        for x in sub.flat_ifs:
            if not (L.start_ln < x.start_ln and x.end_ln <= L.end_ln):
                continue
            frac = (x.end_ln - x.start_ln + 1) / body_len
            if frac < min_fraction:
                continue
            cond = str(x.condition)
            kinds = {tm: classify_term(tm, indices, body) for tm in _and_terms(cond)}
            distinct = set(kinds.values())
            kind = distinct.pop() if len(distinct) == 1 else "mixed"
            hoist = " .and. ".join(tm for tm, k in kinds.items() if k == "invariant") if kind == "mixed" else ""
            rng = " .and. ".join(tm for tm, k in kinds.items() if k == "range") if kind == "mixed" else ""
            out.append(GuardedLoop(sub.name, Path(sub.filepath).name, (L.start_ln + 1, L.end_ln + 1),
                                   (x.start_ln + 1, x.end_ln + 1), cond, kind, frac, L.index, hoist, rng))
    return out


def report(subs: Iterable, min_fraction: float = 0.5) -> list[GuardedLoop]:
    found: list[GuardedLoop] = []
    for sub in subs:
        found.extend(guarded_loops(sub, min_fraction))
    return sorted(found, key=lambda g: (g.file, g.loop_lines))
