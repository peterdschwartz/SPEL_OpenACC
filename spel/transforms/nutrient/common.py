"""
Fields the C/N/P variants of a derived type have in common.

A family is the set of types whose names differ only in the element:
``vegetation_carbon_flux``, ``vegetation_nitrogen_flux`` and
``vegetation_phosphorus_flux`` form the family ``vegetation_nutrient_flux``.

Two components of a family's types are variants of one field when their names
are the same except at positions where each has its own element letter
(``deadcrootc``/``deadcrootn``: the last letter; the ``c`` of ``croot`` is the
same in both). Each name is reduced to its masks, the name with any subset of
its element letters replaced by ``#``; variants share a mask. A name takes
the mask shared with the most types, then the one with the fewest ``#``, so
names identical in every type (``species``) match as themselves.

The base name of a field is its mask without the ``#`` (``leaf#_to_litter``
-> ``leaf_to_litter``, ``soil_#_immob_flux_vr`` -> ``soil_immob_flux_vr``),
unless BASE_NAMES gives a more descriptive one (``beg#b`` -> ``balance_beg``). A base name that is also a component of one of the
types, or the base name of another field, is a collision to resolve by hand.

Variants are only grouped by name; declarations that differ (type, rank,
pointer/allocatable) are reported as mismatches, and such a field can't move
to the base type as it is. Variants allocated with different bounds
(``nlevdecomp`` in N, ``nlevdecomp_full`` in P) share the declaration; they are
listed so the base type's Init allocates them by species.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

ELEMENTS = {"carbon": "c", "nitrogen": "n", "phosphorus": "p"}
ORDER = tuple(ELEMENTS.values())
_ELEMENT_RE = re.compile("|".join(ELEMENTS))
MAX_LETTERS = 6  # element letters per name tried as substitution sites (2**6 masks)
# base names for masks whose stripped name says too little (any family)
BASE_NAMES = {
    "beg#b": "balance_beg",  # begcb: (gC/m2) carbon mass, beginning of time step
    "end#b": "balance_end",
    "err#b": "balance_err",
    "#trunc": "trunc_sink",  # ctrunc: sink for truncation
    "#trunc_vr": "trunc_sink_vr",
    "#deploy": "pool_deploy",  # ndeploy: total N deployed in new growth
}


@dataclass
class Variant:
    """One field's declaration in one type of the family."""

    name: str
    type: str
    rank: int
    bounds: str
    storage: str  # pointer | allocatable | plain
    ln: int  # 0-based declaration line
    comment: str = ""

    @property
    def known_bounds(self) -> bool:
        """Bounds from the allocation; `(:)` (allocation not found) only gives the rank."""
        return bool(self.bounds) and "(" not in self.bounds


@dataclass
class CommonField:
    mask: str
    base: str
    variants: dict[str, Variant]  # element letter -> declaration

    @property
    def elements(self) -> str:
        return "".join(e for e in ORDER if e in self.variants)

    @property
    def consistent(self) -> bool:
        """The variants can share one declaration (type, rank, pointer/allocatable)."""
        return len({(v.type, v.rank, v.storage) for v in self.variants.values()}) == 1

    @property
    def alloc_differs(self) -> bool:
        """Allocated with different bounds (the base Init selects them by species)."""
        return len({v.bounds for v in self.variants.values() if v.known_bounds}) > 1


@dataclass
class Family:
    name: str  # vegetation_nutrient_flux
    types: dict[str, str]  # element letter -> type name
    fields: list[CommonField] = field(default_factory=list)  # in the first type's order
    collisions: dict[str, list[str]] = field(default_factory=dict)  # base name -> why
    procedures: dict[str, list[str]] = field(default_factory=dict)  # binding -> elements
    # single-type fields that match another type's after dropping an `_<letter>` token
    near: list[tuple[str, str]] = field(default_factory=list)  # (element:name, element:name)

    def by_elements(self, elements: str) -> list[CommonField]:
        return [f for f in self.fields if f.elements == elements]

    @property
    def common(self) -> list[CommonField]:
        """Fields every type of the family has."""
        return self.by_elements("".join(e for e in ORDER if e in self.types))


def family_name(type_name: str) -> tuple[str, str] | None:
    """(family name, element letter) of a C/N/P type name, else None."""
    found = _ELEMENT_RE.findall(type_name)
    if len(found) != 1:
        return None
    return _ELEMENT_RE.sub("nutrient", type_name), ELEMENTS[found[0]]


def masks(name: str, letter: str) -> list[str]:
    """`name` with each subset of its `letter`s replaced by '#' (the empty subset first)."""
    sites = [i for i, ch in enumerate(name) if ch == letter][-MAX_LETTERS:]
    out = []
    for n in range(len(sites) + 1):
        for subset in itertools.combinations(sites, n):
            chars = list(name)
            for i in subset:
                chars[i] = "#"
            out.append("".join(chars))
    return out


def base_name(mask: str) -> str:
    """The mask without its element letters (`soil_#_immob` -> `soil_immob`), or its BASE_NAMES entry."""
    if mask in BASE_NAMES:
        return BASE_NAMES[mask]
    return re.sub("_+", "_", mask.replace("#", "")).strip("_") or mask


def variant(comp, lines: list[str]) -> Variant:
    """`comp`'s declaration; attributes and comment come from its source line."""
    text = lines[comp.ln] if 0 <= comp.ln < len(lines) else ""
    code, _, comment = text.partition("!")
    attrs = code.partition("::")[0].lower().replace(" ", "").split(",")
    storage = "pointer" if "pointer" in attrs else "allocatable" if "allocatable" in attrs else "plain"
    return Variant(
        name=comp.name.lower(),
        type=comp.type.lower(),
        rank=comp.dim,
        bounds=(comp.bounds or "").replace(" ", "").lower(),
        storage=storage,
        ln=comp.ln,
        comment=comment.strip(),
    )


def match_fields(components: dict[str, dict[str, Variant]]) -> list[CommonField]:
    """Group the components of each type ({letter: {name: Variant}}) into fields."""
    # mask -> letter -> names having it
    index: dict[str, dict[str, list[str]]] = {}
    for letter, comps in components.items():
        for name in comps:
            for m in masks(name, letter):
                index.setdefault(m, {}).setdefault(letter, []).append(name)

    def rank(m: str) -> tuple[int, int]:
        # shared with more types first, then the fewest substitutions
        return (-len(index[m]), m.count("#"))

    # each name's best mask; a mask is used only if its names chose it in every type
    best: dict[tuple[str, str], str] = {}
    for letter, comps in components.items():
        for name in comps:
            best[(letter, name)] = min(masks(name, letter), key=rank)

    fields: list[CommonField] = []
    taken: set[tuple[str, str]] = set()
    for letter, comps in components.items():  # the first type's order, then the others' leftovers
        for name in comps:
            if (letter, name) in taken:
                continue
            m = best[(letter, name)]
            variants = {}
            for other, names in index[m].items():
                # a mask matching two names of one type is ambiguous: keep only this name
                chosen = [n for n in names if best[(other, n)] == m and (other, n) not in taken]
                if other == letter:
                    chosen = [name]
                if len(chosen) == 1:
                    variants[other] = components[other][chosen[0]]
            if len(variants) == 1:
                m = name  # no partner: the field keeps its own name
            for other, v in variants.items():
                taken.add((other, v.name))
            fields.append(CommonField(mask=m, base=base_name(m), variants=variants))
    return fields


def find_collisions(fam: Family, components: dict[str, dict[str, Variant]]) -> dict[str, list[str]]:
    shared = [f for f in fam.fields if len(f.variants) > 1]
    out: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for f in shared:
        if f.base in seen:
            out.setdefault(f.base, []).append(f"also the base name of {seen[f.base]}")
        seen.setdefault(f.base, f.mask)
        for letter, comps in components.items():
            v = comps.get(f.base)
            if v is not None and f.variants.get(letter) is not v:
                out.setdefault(f.base, []).append(f"component of {fam.types[letter]}")
    return out


def near_misses(fam: Family) -> list[tuple[str, str]]:
    """Pairs of single-type fields that differ by an inserted element token (`_p`)."""
    singles = {e: {f.base for f in fam.by_elements(e)} for e in fam.types}
    out = []
    for e, names in singles.items():
        for name in sorted(names):
            dropped = re.sub(rf"_{e}(?=_|$)", "", name)
            if dropped == name:
                continue
            for other, onames in singles.items():
                if other != e and dropped in onames:
                    out.append((f"{other}:{dropped}", f"{e}:{name}"))
    return out


def find_families(type_dict: dict) -> list[Family]:
    groups: dict[str, dict[str, object]] = {}
    for tname, dtype in type_dict.items():
        fn = family_name(tname)
        if fn:
            groups.setdefault(fn[0], {})[fn[1]] = dtype
    families = []
    for name, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        members = {e: members[e] for e in ORDER if e in members}
        components = {}
        for e, t in members.items():
            lines = Path(t.filepath).read_text().split("\n")
            components[e] = {n.lower(): variant(c, lines) for n, c in t.components.items()}
        fam = Family(name=name, types={e: t.type_name for e, t in members.items()})
        fam.fields = match_fields(components)
        fam.collisions = find_collisions(fam, components)
        procs: dict[str, list[str]] = {}
        for e, t in members.items():
            for binding in t.procedures:
                procs.setdefault(str(binding).lower(), []).append(e)
        fam.procedures = procs
        fam.near = near_misses(fam)
        families.append(fam)
    return families


def summary(families: list[Family]) -> str:
    out = [
        f"{'family':30s} {'types':>5s} {'fields':>7s} {'common':>7s} {'pairs':>6s} "
        f"{'single':>7s} {'mismatch':>9s} {'alloc':>6s} {'collide':>8s} {'near':>5s}"
    ]
    for fam in families:
        n = len(fam.types)
        common = fam.common
        pairs = [f for f in fam.fields if 1 < len(f.variants) < n]
        single = [f for f in fam.fields if len(f.variants) == 1]
        bad = [f for f in fam.fields if len(f.variants) > 1 and not f.consistent]
        alloc = [f for f in fam.fields if f.consistent and f.alloc_differs]
        total = sum(1 for f in fam.fields for _ in f.variants)
        out.append(
            f"{fam.name:30s} {''.join(fam.types):>5s} {total:7d} {len(common):7d} {len(pairs):6d} "
            f"{len(single):7d} {len(bad):9d} {len(alloc):6d} {len(fam.collisions):8d} {len(fam.near):5d}"
        )
    out.append(
        "\nfields: components of all types; common: fields in every type; pairs: in two of\n"
        "three; single: in one type only; mismatch: variants declared differently;\n"
        "alloc: allocated with different bounds (allocate by species);\n"
        "near: single-type fields matching another type's but for an `_<letter>` token"
    )
    return "\n".join(out)


def detail(fam: Family) -> str:
    out = [f"== {fam.name}: " + ", ".join(f"{e}={t}" for e, t in fam.types.items())]
    n = len(fam.types)

    def row(f: CommonField) -> str:
        names = " ".join(f"{f.variants[e].name if e in f.variants else '-':28s}" for e in fam.types)
        if not f.consistent:
            decl = "  MISMATCH " + "; ".join(
                f"{e}: {v.type} rank {v.rank} {v.bounds} {v.storage}" for e, v in f.variants.items()
            )
        else:
            v = next(iter(f.variants.values()))
            decl = f"  {v.type} rank {v.rank} {v.storage}"
            if f.alloc_differs:
                decl += "  ALLOC " + "; ".join(f"{e}: {v.bounds}" for e, v in f.variants.items())
        return f"  {f.base:30s} {names}{decl}"

    header = f"  {'base':30s} " + " ".join(f"{fam.types[e]:28s}" for e in fam.types)
    groups = [("common", fam.common)]
    for k in range(n - 1, 0, -1):
        for combo in itertools.combinations(fam.types, k):
            groups.append(("only " + "".join(combo), fam.by_elements("".join(combo))))
    for label, fields in groups:
        if fields:
            out.append(f"\n {label} ({len(fields)}):")
            out.append(header)
            out.extend(row(f) for f in fields)
    if fam.near:
        out.append("\n not matched, differ by an element token (review):")
        out.extend(f"  {a:30s} {b}" for a, b in fam.near)
    if fam.collisions:
        out.append("\n collisions:")
        for base, why in fam.collisions.items():
            out.append(f"  {base}: {'; '.join(why)}")
    out.append("\n procedures: " + ", ".join(f"{b} ({''.join(es)})" for b, es in fam.procedures.items()))
    return "\n".join(out)


def to_json(families: list[Family], path: Path) -> None:
    import json

    data = []
    for fam in families:
        d = asdict(fam)
        for f, fd in zip(fam.fields, d["fields"]):
            fd["elements"] = f.elements
            fd["consistent"] = f.consistent
            fd["alloc_differs"] = f.alloc_differs
        data.append(d)
    path.write_text(json.dumps(data, indent=1))
