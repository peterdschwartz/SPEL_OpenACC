"""
Move the fields the C/N/P types of a family share into a common base type,
held by each concrete type as its component ``core``.

For each family (common.py), the fields every type has, declared alike, move
to a base type named after the family (``vegetation_nutrient_flux``):

  * the base type is inserted in the module of the family's types, before the
    first of them; each field is declared like the carbon type's variant,
    under its base name, with a comment naming the old components,
  * each concrete type gets a component ``type(<base>) :: core`` (first) and
    loses those declarations; composition rather than ``extends``, so routines
    on the base fields take a plain ``type(<base>)`` argument (no polymorphic
    dummies or type-bound dispatch, which device code doesn't handle well),
  * every use ``obj%leafn`` in components/elm/src (FATES and EMI's standalone
    stubs excluded) whose
    object is an instance of the type becomes ``obj%leaf``. An object is an
    instance when it is one of the type's module-level instances (``veg_ns``,
    ``c13_veg_cs``), a dummy or local declared ``type(T)``/``class(T)`` (so
    ``this`` in its procedures), or an associate name bound to one of these
    (``ns => veg_ns``) becomes ``obj%core%leaf``. Associate names of fields
    keep their names, so process code changes only in the selectors
    (``leafn => veg_ns%core%leaf``). OpenACC/OpenMP directives are renamed too.

Procedures are not merged here (only their component names change), so the
model is bit-for-bit with the sources before the rewrite. Text edits, on code
only (not comments or strings), located by declaration line and checked.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from spel.transforms.nutrient.common import ORDER, CommonField, Family
from spel.transforms.nutrient.procedures import _split_code

MANIFEST = ".spel-nutrient.json"
CORE = "core"  # the component of each concrete type that holds the base fields
# not part of the ELM build: FATES, and EMI's standalone stubs of the ELM types
EXCLUDE = ("external_models/fates", "external_models/emi/src/elm_stub", "external_models/emi/src/demo")
_ROUTINE_START = re.compile(
    r"^\s*(?:(?:pure|elemental|recursive|impure|module)\s+)*"
    r"(?:(?:real|integer|logical|character|type|class|double\s+precision)\b[^!]*?\s+)?"
    r"(?:subroutine|function)\s+(\w+)",
    re.I,
)
_ROUTINE_END = re.compile(r"^\s*end\s*(?:subroutine|function)\b", re.I)


class ExtractError(Exception):
    pass


@dataclass
class TypeEdit:
    type_name: str
    element: str
    moved: dict[str, str]  # old component -> its path in the new component (core%leaf)


ELEMENT_WORDS = {"c": "carbon", "n": "nitrogen", "p": "phosphorus"}


def generic_description(text: str, elements, old_names: dict[str, str]) -> str:
    """
    A C/N/P variant's comment for the shared field (comment text, not code):
    `carbon`/`nitrogen`/`phosphorus` and the element letters used as words become
    `nutrient` (`leaf C storage`, `c pools`), units lose the element (`gC/m2` -> `g/m2`),
    and old component names (`leafc`) become their base names.
    """
    letters = "".join(e.upper() for e in elements)
    out = re.sub(rf"\bg(?:C1[34]|[{letters}])(?=\s*/|\s*\)|\s*\^|$)", "g", text, flags=re.I)
    for e in elements:
        word = ELEMENT_WORDS[e]
        out = re.sub(rf"\b{word}\b", lambda m: "Nutrient" if m.group(0)[0].isupper() else "nutrient", out, flags=re.I)
    out = re.sub(rf"(?<![\w/:.%-])[{letters}{letters.lower()}](?![\w/:%(-])", "nutrient", out)
    for old, base in sorted(old_names.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"(?<![\w%]){re.escape(old)}(?!\w)", base, out, flags=re.I)
    return out


@dataclass
class FamilyEdit:
    """Fields of some of a family's types that move to a component of a new type."""

    family: Family
    fields: list[CommonField]
    type_name: str  # the component's type (vegetation_nutrient_flux, column_mineral_flux)
    component: str  # its name in each concrete type (core, mineral)
    elements: tuple[str, ...]  # the types that get it
    names: dict[str, str] = field(default_factory=dict)  # base name -> name in the type, if not the base
    note: str = ""  # comment on the component's declaration
    types: list[TypeEdit] = field(default_factory=list)

    def __post_init__(self):
        for e in self.elements:
            moved = {f.variants[e].name: f"{self.component}%{self.name(f)}" for f in self.fields}
            self.types.append(TypeEdit(self.family.types[e], e, moved))

    def name(self, f: CommonField) -> str:
        return self.names.get(f.base, f.base)


def core_edits(families: list[Family]) -> tuple[list[FamilyEdit], dict[str, dict[str, str]]]:
    """The base-type (`core`) edit of each family: its fields common to all types."""
    edits, skipped = [], {}
    for fam in families:
        fields, skipped[fam.name] = movable(fam)
        if fields:
            edits.append(
                FamilyEdit(
                    fam, fields, fam.name, CORE, tuple(fam.types),
                    note="fields common to the C/N/P types",
                )
            )
    return edits, skipped


def movable(fam: Family) -> tuple[list[CommonField], dict[str, str]]:
    """(fields that move to the base, {base: why not} for common fields that don't)."""
    out, skipped = [], {}
    for f in fam.common:
        if not f.consistent:
            skipped[f.base] = "declared differently"
        elif f.base in fam.collisions:
            skipped[f.base] = "base name collides: " + "; ".join(fam.collisions[f.base])
        else:
            out.append(f)
    return out, skipped


def entity_count(code: str) -> int:
    ents = code.split("::", 1)[1] if "::" in code else ""
    depth, n = 0, 1
    for ch in ents:
        depth += ch == "("
        depth -= ch == ")"
        n += ch == "," and depth == 0
    return n


class Extractor:
    def __init__(self, edits: list[FamilyEdit], type_dict: dict, elm_src: Path, skipped=None):
        self.type_dict = type_dict
        self.elm_src = Path(elm_src)
        self.edits = edits
        self.skipped: dict[str, dict[str, str]] = skipped or {}
        self.files: dict[Path, list[str]] = {}  # path -> edited lines
        self.renamed: dict[Path, int] = {}

    def lines(self, path: Path) -> list[str]:
        if path not in self.files:
            self.files[path] = Path(path).read_text().split("\n")
        return self.files[path]

    # --- type definitions -------------------------------------------------

    def type_line(self, lines: list[str], type_name: str) -> int:
        rx = re.compile(rf"^\s*type\s*(,[^:]*)?::\s*{type_name}\b", re.I)
        hits = [i for i, l in enumerate(lines) if rx.match(_split_code(l)[0])]
        if len(hits) != 1:
            raise ExtractError(f"definition of {type_name}: {len(hits)} matches")
        return hits[0]

    def base_definition(self, fe: FamilyEdit, lines: list[str]) -> list[str]:
        fam = fe.family
        e0 = next(e for e in ORDER if e in fe.elements)
        holders = ", ".join(fam.types[e] for e in ORDER if e in fe.elements)
        out = [
            "  !-----------------------------------------------------------------------",
            f"  ! {fe.component}: fields of {holders}",
            "  !-----------------------------------------------------------------------",
            f"  type, public :: {fe.type_name}",
        ]
        src = Path(self.type_dict[fam.types[e0]].filepath).read_text().split("\n")
        # old component names -> base names, for the descriptions: every family in this run
        # (flux comments name state fields: "from leafc_storage"), the field's own first
        old_names = {v.name: g.base for e in self.edits for g in e.family.fields for v in g.variants.values()}
        # after extract, the earlier steps' old names are only in their manifest (groups)
        manifest_path = Path(self.type_dict[fam.types[e0]].filepath).parent / ".spel-nutrient.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text())
            for key in ("families", "groups"):
                for entry in data.get(key, {}).values():
                    for moved in entry.get("types", {}).values():
                        for o, n in moved.items():
                            old_names.setdefault(o, n.split("%")[-1])
        old_names |= {v.name: g.base for g in fam.fields for v in g.variants.values()}
        for f in fe.fields:
            v = f.variants[e0]
            code, comment = _split_code(src[v.ln])
            decl = re.sub(rf"(::\s*){v.name}\b", rf"\g<1>{fe.name(f)}", code, count=1, flags=re.I).rstrip()
            note = generic_description(comment.lstrip("!").strip(), fe.elements, old_names)
            out.append(f"{decl} ! {note}" if note else decl)
        out.append(f"  end type {fe.type_name}")
        out.append("")
        return out

    def edit_types(self) -> None:
        # edits by original line, applied once per file (a file can hold several families)
        drop: dict[Path, set[int]] = {}
        replace: dict[Path, dict[int, str]] = {}
        insert: dict[Path, dict[int, list[str]]] = {}
        for fe in self.edits:
            fam = fe.family
            paths = {Path(self.type_dict[t.type_name].filepath) for t in fe.types}
            if len(paths) != 1:
                raise ExtractError(f"{fam.name}: types in several files {sorted(map(str, paths))}")
            path = paths.pop()
            lines = self.lines(path)
            for t in fe.types:
                comps = self.type_dict[t.type_name].components
                for old in t.moved:
                    ln = comps[old].ln
                    code = _split_code(lines[ln])[0]
                    if not re.search(rf"::\s*{old}\b", code, re.I):
                        raise ExtractError(f"{t.type_name}%{old}: line {ln + 1} is not its declaration")
                    if entity_count(code) != 1 or code.rstrip().endswith("&"):
                        raise ExtractError(f"{t.type_name}%{old}: line {ln + 1} declares more than it")
                    drop.setdefault(path, set()).add(ln)
            if fe.type_name in self.type_dict:
                raise ExtractError(f"type {fe.type_name} exists already")
            starts = {t.type_name: self.type_line(lines, t.type_name) for t in fe.types}
            for tname, ln in starts.items():
                comps = self.type_dict[tname].components
                if fe.component in comps:
                    raise ExtractError(f"{tname} already has a component {fe.component}")
                first_decl = min(comps[old].ln for old in next(t for t in fe.types if t.type_name == tname).moved)
                indent = re.match(r"\s*", lines[first_decl]).group(0)
                insert.setdefault(path, {}).setdefault(ln + 1, []).append(
                    f"{indent}type({fe.type_name}) :: {fe.component}" + (f"  ! {fe.note}" if fe.note else "")
                )
            insert.setdefault(path, {}).setdefault(min(starts.values()), []).extend(
                self.base_definition(fe, lines)
            )
        for path, lines in list(self.files.items()):
            new = []
            for i, l in enumerate(lines):
                new.extend(insert.get(path, {}).get(i, []))
                if i not in drop.get(path, set()):
                    new.append(replace.get(path, {}).get(i, l))
            self.files[path] = new

    # --- uses -------------------------------------------------------------

    def rename_uses(self) -> None:
        by_type: dict[str, dict[str, str]] = {}
        for fe in self.edits:
            for t in fe.types:
                by_type.setdefault(t.type_name, {}).update(t.moved)
        instances = {}
        for tname in by_type:
            for inst in self.type_dict[tname].instances:
                instances[inst.lower()] = tname
        decl_rx = re.compile(r"^\s*(?:type|class)\s*\(\s*(\w+)\s*\)[^:]*::(.*)$", re.I)
        sources = sorted(p for p in self.elm_src.rglob("*.F90") if not any(x in str(p) for x in EXCLUDE))
        for path in sources:
            text = self.files[path] if path in self.files else path.read_text(errors="replace").split("\n")
            if not any("%" in l for l in text):
                continue
            count = rename_in_lines(text, instances, by_type, decl_rx)
            if count:
                self.files[path] = text
                self.renamed[path] = count

    def build(self) -> None:
        self.edit_types()
        self.rename_uses()

    def write(self, manifest: dict) -> list[Path]:
        """Write the edited files, and add `manifest`'s entries to the manifest."""
        written = []
        for path, lines in self.files.items():
            text = "\n".join(lines)
            if text != Path(path).read_text(errors="replace"):
                Path(path).write_text(text)
                written.append(path)
        mpath = self.elm_src / "data_types" / MANIFEST
        data = json.loads(mpath.read_text()) if mpath.exists() else {}
        data.update(manifest)
        mpath.write_text(json.dumps(data, indent=1) + "\n")
        written.append(mpath)
        return written

    def report(self) -> str:
        out = []
        for fe in self.edits:
            out.append(f"{fe.type_name}: {len(fe.fields)} fields")
            for t in fe.types:
                out.append(f"  {t.type_name}%{fe.component}: type({fe.type_name})")
            for base, why in self.skipped.get(fe.family.name, {}).items():
                out.append(f"  kept in the concrete types: {base} ({why})")
        out.append(f"uses renamed: {sum(self.renamed.values())} in {len(self.renamed)} files")
        return "\n".join(out)


def object_scopes(lines: list[str], instances: dict, type_names, decl_rx) -> list[dict[str, str]]:
    """
    For each line, the names that refer to objects of `type_names` there:
    module instances, the line's routine's dummies/locals declared type(T) or
    class(T), and associate names bound to one of these.
    """
    module_scope: dict[str, str] = {}

    def collect(start: int, end: int, into: dict[str, str]) -> None:
        stmt = ""
        for l in lines[start:end]:
            code = _split_code(l)[0]
            stmt += code.rstrip().rstrip("&") + " " if code.rstrip().endswith("&") else code
            if code.rstrip().endswith("&"):
                continue
            m = decl_rx.match(stmt)
            if m and m.group(1).lower() in type_names:
                for ent in re.split(r",(?![^(]*\))", m.group(2)):
                    name = re.match(r"\s*(\w+)", ent)
                    if name:
                        into[name.group(1).lower()] = m.group(1).lower()
            stmt = ""

    def aliases(start: int, end: int, into: dict[str, str]) -> None:
        known = {**instances, **module_scope, **into}
        rx = re.compile(r"(\w+)\s*=>\s*(\w+)\b(?!\s*[%(])", re.I)
        for l in lines[start:end]:
            for alias, target in rx.findall(_split_code(l)[0]):
                t = known.get(target.lower())
                if t:
                    into[alias.lower()] = t

    spans, stack = [], []
    for i, l in enumerate(lines):
        code = _split_code(l)[0]
        if _ROUTINE_END.match(code):
            if stack:
                spans.append((stack.pop(), i + 1))
        elif _ROUTINE_START.match(code) and not re.match(r"^\s*end\b", code, re.I):
            stack.append(i)
    first = min((s for s, _ in spans), default=len(lines))
    collect(0, first, module_scope)
    owner = [None] * len(lines)
    for s, e in sorted(spans, key=lambda x: x[1] - x[0], reverse=True):  # inner routines last
        for i in range(s, e):
            owner[i] = (s, e)
    scopes: dict[tuple[int, int], dict[str, str]] = {}
    for s, e in spans:
        sc: dict[str, str] = {}
        collect(s, e, sc)
        aliases(s, e, sc)
        scopes[(s, e)] = {**instances, **module_scope, **sc}
    top = {**instances, **module_scope}
    return [scopes.get(owner[i], top) for i in range(len(lines))]


def code_pieces(line: str) -> tuple[list[str], str]:
    """(code split around string literals: even items are code, comment)."""
    code, comment = _split_code(line)
    return re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", code), comment


def rename_in_lines(lines: list[str], instances: dict, by_type: dict, decl_rx) -> int:
    """Rename `obj%old` to `obj%<by_type[type][old]>` in place (directives too); returns the number of renames."""
    count = 0
    scopes = object_scopes(lines, instances, set(by_type), decl_rx)
    obj_rx = re.compile(r"(?<![%\w])(\w+)(\s*%\s*)(\w+)\b", re.I)
    for i, l in enumerate(lines):
        if "%" not in l:
            continue
        sc = scopes[i]
        pieces, comment = code_pieces(l)
        directive = re.match(r"^(\s*!\$(?:acc|omp)\b)(.*)$", l, re.I)
        if directive:  # renamed like code
            pieces, comment = code_pieces(directive.group(2))
            pieces[0] = directive.group(1) + pieces[0]
        changed = False
        for k in range(0, len(pieces), 2):

            def sub(m: re.Match) -> str:
                nonlocal count, changed
                t = sc.get(m.group(1).lower())
                base = by_type.get(t, {}).get(m.group(3).lower()) if t else None
                if base is None:
                    return m.group(0)
                count += 1
                changed = True
                return f"{m.group(1)}{m.group(2)}{base}"

            pieces[k] = obj_rx.sub(sub, pieces[k])
        if changed:
            lines[i] = "".join(pieces) + comment
    return count


def manifest(ex: Extractor, spel_commit: str | None, e3sm: dict, key: str = "families") -> dict:
    """The manifest entries of this edit (`families` for extract, `groups` for groups)."""
    entry = {
        fe.type_name: {
            "component": fe.component,
            "types": {t.type_name: t.moved for t in fe.types},
            "kept": ex.skipped.get(fe.family.name, {}) if fe.component == CORE else {},
        }
        for fe in ex.edits
    }
    out = {key: entry, f"{key}_spel_commit": spel_commit, f"{key}_e3sm": e3sm}
    if key == "families":  # the extract's provenance, as before
        out.update({"spel_commit": spel_commit, "e3sm": e3sm})
    return out
