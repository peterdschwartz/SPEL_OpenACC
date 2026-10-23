"""
Rewrite ELM sources so the selected fields of a derived type use compact
storage (see select.py for the selection and CompactLayoutMod.F90 for the
storage).

Edits:

  * each access site ``x(p)``, p = filter_soilp(fp), becomes ``x(k0p+fp)``; the
    routine gets ``use CompactLayoutMod, only : compact_soilp_off`` and a
    local ``k0p = compact_soilp_off`` (copied once, so it is safe inside
    OpenMP/OpenACC loops)
  * the type gets a `cbuf` component and generated CompactInit, CompactView
    and FullView procedures; its Init calls CompactInit after the
    special-patch SetValues call, which registers the fields and points them
    at their compact storage
  * SetValues zeroes the fields with explicit assignments under their zeroing
    class's guard: x(k0p+1:k0p+num) once bound, x(filter(1:num)) before (so
    SPEL's own analysis still sees the writes)
  * elm_drv unpacks the history fields to their full layout copies after
    the unpack-point call (its own timer, `compact_unpack`)
  * get_clump_bounds sets the clump offset (`compact_set_clump`)
  * CompactLayoutMod.F90 is added to components/elm/src/main

Edits are located by content and checked: a site whose text doesn't match
the analysis stops the rewrite. The sources must be the ones analyzed and
not yet rewritten; `.spel-compact.json` in components/elm/src/main records
what was applied. To reapply after a rebase: drop the generated changes,
`spel analyze`, run the rewrite again.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from spel.transforms.compact.holders import base_routine, embedded_holders, nutrient_manifest
from spel.transforms.compact.inventory import DRIVER_ID
from spel.scripts.registrations import parse_routine
from spel.transforms.compact.select import Polymorphic, Selection, statement_end
from spel.scripts.fortran_parser.scope_walk import AssignEvent
from spel.scripts.fortran_parser.spel_ast import (
    AssociateConstruct,
    BoundsExpression,
    FuncExpression,
    KeywordArgument,
    SubCallStatement,
    TypeDef,
    UseStatement,
)
from spel.scripts.fortran_parser.symbols import SymbolKind
from spel.transforms.split.modules import parse_module_file, use_items

TEMPLATE = Path(__file__).parent / "templates" / "CompactLayoutMod.F90"
MANIFEST = ".spel-compact.json"
K0 = "k0p"
OFF = "compact_off"  # optional dummy of a Polymorphic routine
KC = "kc"  # its index for the compact-capable dummies
TAG = "! spel compact"
DECOMP_ROUTINES = {"get_clump_bounds_new": "bounds%begp", "get_clump_bounds_old": "begp"}


class RewriteError(Exception):
    pass


def known(rec, name: str) -> bool:
    """Whether `name` resolves in the routine (unknown names resolve as EXTERNAL)."""
    sym = rec.lookup(name)
    return sym is not None and sym.kind is not SymbolKind.EXTERNAL


@dataclass
class FileEdits:
    path: Path
    lines: list[str]
    subs: dict[int, list[tuple[re.Pattern, str]]] = field(default_factory=lambda: defaultdict(list))
    after: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    before: dict[int, list[str]] = field(default_factory=lambda: defaultdict(list))
    deletes: set[int] = field(default_factory=set)

    def result(self) -> list[str]:
        out: list[str] = []
        for i, line in enumerate(self.lines):
            out.extend(self.before.get(i, []))
            if i not in self.deletes:
                for pattern, repl in self.subs.get(i, []):
                    line = pattern.sub(repl, line)
                out.append(line)
            out.extend(self.after.get(i, []))
        return out


class Rewriter:
    """
    The edits for one or more types (`sels`). Edits shared by the types (a
    routine's k0p prologue, a module's use of CompactLayoutMod, the driver's
    unpack, the clump offset) are made once.
    """

    def __init__(self, fut, sels: Selection | list[Selection]):
        self.fut = fut
        self.sels = sels if isinstance(sels, list) else [sels]
        self.sel = self.sels[0] if self.sels else None  # the type the per-type edits work on
        self.subs = fut.subroutine_dict
        self.files: dict[str, FileEdits] = {}
        self.notes: list[str] = []
        self._prologued: set[str] = set()
        self._buffer_use: set[str] = set()
        self._trees: dict[str, object] = {}  # file -> parsed ModuleConstruct

    def file(self, path) -> FileEdits:
        key = str(path)
        if key not in self.files:
            lines = Path(path).read_text().split("\n")
            self.files[key] = FileEdits(Path(path), lines)
        return self.files[key]

    def module_tree(self, fe: FileEdits):
        """The file's parsed module (its specification part and line spans)."""
        key = str(fe.path)
        if key not in self._trees:
            _, self._trees[key] = parse_module_file(fe.path)
        return self._trees[key]

    def head_uses(self, fe: FileEdits) -> list[UseStatement]:
        return [s for s in self.module_tree(fe).spec.statements if isinstance(s, UseStatement)]

    @staticmethod
    def routine_end(sub) -> int:
        """Line of the routine's `end subroutine`, from its parse."""
        return parse_routine(sub.filepath, sub.startline, sub.endline).end_ln

    # --- access sites ---
    def rewrite_sites(self) -> None:
        by_sub: dict[str, list] = defaultdict(list)
        polymorphic: dict = {}
        for sel in self.sels:
            for site in sel.sites:
                by_sub[site.sub].append(site)
            for sub_id, poly in sel.polymorphic.items():
                prev = polymorphic.get(sub_id)
                if prev is None:
                    polymorphic[sub_id] = poly
                elif prev.dummies == poly.dummies:
                    # fields of several types through the same dummies (the shared fields on
                    # the nutrient base type, the element-specific ones on the concrete type):
                    # a call is compact when its fields are selected by either selection
                    polymorphic[sub_id] = Polymorphic(sub_id, prev.dummies, prev.compact_calls | poly.compact_calls)
                else:
                    raise RewriteError(f"{sub_id} takes compact fields of several types through different dummies")
        callers = {c for p in polymorphic.values() for c, _ in p.compact_calls}
        for sub_id in sorted(set(by_sub) | callers):
            sub = self.subs[sub_id]
            fe = self.file(sub.filepath)
            if sub_id in polymorphic:
                self.rewrite_polymorphic(fe, sub, by_sub[sub_id])
                continue
            for site in by_sub.get(sub_id, []):
                self.rewrite_site(fe, site)
            self.prologue(fe, sub)
        for poly in polymorphic.values():
            for caller, ln in sorted(poly.compact_calls):
                fe = self.file(self.subs[caller].filepath)
                self.append_argument(fe, ln, f"{OFF}={K0}")

    def rewrite_polymorphic(self, fe: FileEdits, sub, sites) -> None:
        """
        An optional `compact_off` dummy; the compact-capable dummies are
        indexed with `kc`: `compact_off + fp` if present, else `p` as before.
        """
        rec = sub.record
        for name in (OFF, KC):
            if rec.declaration(name) is not None or known(rec, name):
                raise RewriteError(f"{sub.id} already has a symbol {name}")
        gathers = {(s.sub0, s.fp) for s in sites}
        if len(gathers) != 1:
            raise RewriteError(f"{sub.id}: sites gather with {sorted(gathers)}; one gather expected")
        var, fp = gathers.pop()
        assigns = [
            e for e in rec.events
            if isinstance(e, AssignEvent) and e.lhs.path == var and not e.lhs.subscripts
            and e.reads and e.reads[-1].subs == (fp,)
        ]
        if len(assigns) != 1:
            raise RewriteError(f"{sub.id}: expected one `{var} = filter({fp})`, found {len(assigns)}")
        for site in sites:
            self.rewrite_site(fe, site, index=KC)
        self.append_argument(fe, sub.startline, OFF)
        last = statement_end(fe.lines, rec.last_decl_ln)
        fe.after[last].extend(
            [
                f"     integer, intent(in), optional :: {OFF}  ! begp-1 of the clump if the flux arrays are compact  {TAG}",
                f"     integer :: {KC}  ! index of the flux arrays  {TAG}",
            ]
        )
        indent = re.match(r"\s*", fe.lines[assigns[0].ln]).group(0)
        fe.after[statement_end(fe.lines, assigns[0].ln)].extend(
            [
                f"{indent}{KC} = {var}  {TAG}",
                f"{indent}if (present({OFF})) {KC} = {OFF} + {fp}  {TAG}",
            ]
        )

    def append_argument(self, fe: FileEdits, ln: int, arg: str) -> None:
        """Add `arg` as the last argument of the call or header statement on line `ln`."""
        end = statement_end(fe.lines, ln)
        code = fe.lines[end].split("!")[0]
        close = code.rstrip().rfind(")")
        if close < 0:
            raise RewriteError(f"{fe.path}:{end + 1}: no closing parenthesis for `{arg}`")
        pattern = re.compile(rf"^(.{{{close}}})\)")
        repl = rf"\1, {arg})"
        if (pattern, repl) not in fe.subs[end]:
            fe.subs[end].append((pattern, repl))

    def rewrite_site(self, fe: FileEdits, site, index: str | None = None) -> None:
        name = r"\s*%\s*".join(re.escape(part) for part in site.written.split("%"))
        pattern = re.compile(
            rf"(?<![%\w])(?P<name>{name})\s*\(\s*{re.escape(site.sub0)}\s*(?=[,)])",
            re.IGNORECASE,
        )
        repl = rf"\g<name>({index}" if index else rf"\g<name>({K0}+{site.fp}"
        end = statement_end(fe.lines, site.ln)
        hits = [ln for ln in range(site.ln, end + 1) if pattern.search(fe.lines[ln].split("!")[0])]
        if not hits:
            raise RewriteError(
                f"{fe.path}:{site.ln + 1}: no `{site.written}({site.sub0}` in the statement "
                f"(sources changed since the analysis?)"
            )
        for ln in hits:
            if (pattern, repl) not in fe.subs[ln]:
                fe.subs[ln].append((pattern, repl))

    def prologue(self, fe: FileEdits, sub) -> None:
        if sub.id in self._prologued:
            return
        self._prologued.add(sub.id)
        rec = sub.record
        if rec.declaration(K0) is not None or known(rec, K0):
            raise RewriteError(f"{sub.id} already has a symbol {K0}")
        header = statement_end(fe.lines, sub.startline)
        fe.after[header].append(f"    use CompactLayoutMod, only : compact_soilp_off  {TAG}")
        last = statement_end(fe.lines, rec.last_decl_ln) if rec.last_decl_ln >= 0 else header
        fe.after[last].extend(
            [
                f"    integer :: {K0}  ! begp-1 of the clump: compact index of filter_soilp(fp) is {K0}+fp  {TAG}",
                f"    {K0} = compact_soilp_off  {TAG}",
            ]
        )

    # --- the derived type ---
    def rewrite_type(self) -> None:
        holder = self.sel.holder
        if "cbuf" in self.fut.type_dict[self.sel.dtype].components:
            raise RewriteError(f"{self.sel.dtype} already has a cbuf component: already rewritten?")
        if holder is not None and holder.embedded:
            self.rewrite_embedded_type()
        else:
            self.rewrite_concrete_type()

    def buffer_use(self, fe: FileEdits) -> None:
        if str(fe.path) not in self._buffer_use:
            self._buffer_use.add(str(fe.path))
            fe.after[self.module_use_line(fe)].append(
                f"  use CompactLayoutMod, only : compact_buffer_type, compact_field  {TAG}"
            )

    def type_span(self, fe: FileEdits, type_name: str) -> tuple[int, int, int]:
        """(first line, last line of the last component, `end type` line) of the type definition."""
        td = next(
            (s for s in self.module_tree(fe).spec.statements
             if isinstance(s, TypeDef) and str(s.name).lower() == type_name.lower()),
            None,
        )
        if td is None:
            raise RewriteError(f"{fe.path}: no definition of type {type_name}")
        members = td.members.statements if td.members is not None else []
        last = statement_end(fe.lines, members[-1].lineno) if members else td.lineno
        return td.lineno, last, td.end_ln

    def init_setvalues_call(self, init) -> int:
        """Line of the one `this%SetValues` call of an Init (the special-patch zeroing)."""
        tree = parse_routine(init.filepath, init.startline, init.endline)
        calls = [
            s for s in tree.body.statements
            if isinstance(s, SubCallStatement) and str(s.function.function).lower() == "this%setvalues"
        ]
        if len(calls) != 1:
            raise RewriteError(f"{init.id}: expected one this%SetValues call, found {len(calls)}")
        return calls[0].lineno

    def rewrite_zeroing(self, setvalues, path: str, classes) -> None:
        """
        In a zeroing routine: drop the assignments of the compact fields
        (`this%<path>%x(i) = value`) and zero them by class before `end subroutine`.
        """
        fe = self.file(setvalues.filepath)
        this = f"this%{path}" if path else "this"
        zero_lines = self.zero_lines(setvalues, path)
        assigned = {
            (e.ln, e.lhs.path) for e in setvalues.record.events if isinstance(e, AssignEvent)
        }
        for comp in self.sel.components:
            for ln in zero_lines.get(comp, []):
                # one assignment statement on one line, of this component alone
                if statement_end(fe.lines, ln) != ln or (ln, f"{this}%{comp}") not in assigned:
                    raise RewriteError(
                        f"{fe.path}:{ln + 1}: unexpected zeroing line for {comp}: {fe.lines[ln].strip()}"
                    )
                fe.deletes.add(ln)
        sv_end = self.routine_end(setvalues)
        if sv_end != setvalues.endline:
            raise RewriteError(f"{fe.path}:{sv_end + 1}: not the end of {setvalues.id}")
        dummies = [d.name for d in setvalues.record.dummy_args]
        if len(dummies) < 4:
            raise RewriteError(f"{setvalues.id}: expected (this, num, filter, value) dummies, got {dummies}")
        num, filt, value = dummies[1], dummies[2], dummies[3]
        if setvalues.record.declaration("fi") is None:
            raise RewriteError(f"{setvalues.id} has no loop index fi")
        fe.before[sv_end].extend(self.zero_block(classes, num, filt, value, path))
        self.prologue(fe, setvalues)

    def generated_procedures(self, prefix: str, this_decl: str, classes) -> list[str]:
        """CompactInit / CompactView / FullView for the selected fields, named `<prefix>_<name>`."""
        comps = list(self.sel.components)
        cls_of = {c: k for k, (_, cs) in classes.items() for c in cs}
        width = max(len(c) for c in comps) + 2

        def procedure(name: str, doc: str, args: str, decls: list[str], body: list[str]) -> list[str]:
            return [
                "",
                "  !------------------------------------------------------------------------",
                f"  subroutine {prefix}_{name}(this{args})",
                "    !",
                "    ! !DESCRIPTION:",
                f"    ! {doc} (generated by spel compact rewrite)",
                "    !",
                "    ! !ARGUMENTS:",
                f"    {this_decl}",
                *decls,
                "    !------------------------------------------------------------------------",
                *body,
                f"  end subroutine {prefix}_{name}",
            ]

        def field(comp: str) -> str:
            name = f"'{comp}',".ljust(width + 1)
            unpack = ".true. " if self.sel.unpack[comp] else ".false."
            return f"compact_field({name}  unpack={unpack})"

        gen = procedure(
            "compact_init",
            "Give the fields compact storage and point them at it",
            ", beg, end",
            ["    integer, intent(in) :: beg, end"],
            ["    call this%cbuf%init(beg, end)"]
            + [f"    call this%cbuf%add({field(c)}, this%{c})" for c in comps],
        )
        gen += procedure(
            "compact_view",
            "Point the fields at their compact storage",
            "",
            [],
            [f"    call this%cbuf%compact_view(this%{c})" for c in comps] + ["    this%cbuf%bound = .true."],
        )
        gen += procedure(
            "full_view",
            "Point the fields back at their full layout copies",
            "",
            [],
            [f"    call this%cbuf%full_view(this%{c})" for c in comps] + ["    this%cbuf%bound = .false."],
        )
        return gen

    def rewrite_concrete_type(self) -> None:
        """A type with instances and type-bound procedures (the pre-nutrient flux types)."""
        dtype = self.fut.type_dict[self.sel.dtype]
        procs = dtype.procedures
        init, setvalues = self.subs[procs["init"]], self.subs[procs["setvalues"]]
        prefix = procs["init"].split("::")[1].removesuffix("_init")
        fe = self.file(init.filepath)
        classes = self.classes()
        self.buffer_use(fe)

        _, last, end = self.type_span(fe, self.sel.dtype)
        fe.after[last].append(
            f"    type(compact_buffer_type) :: cbuf  ! compact storage of some fields above {TAG}"
        )
        fe.before[end].extend(
            [
                f"    procedure, public :: CompactInit => {prefix}_compact_init  {TAG}",
                f"    procedure, public :: CompactView => {prefix}_compact_view  {TAG}",
                f"    procedure, public :: FullView    => {prefix}_full_view  {TAG}",
            ]
        )

        # Init: register after the special-patch SetValues (which zeroes the full arrays)
        ln = self.init_setvalues_call(init)
        bounds = self.init_bounds(init)
        log = self.can_log(fe)
        fe.after[statement_end(fe.lines, ln)].extend(
            [f"    call this%CompactInit({bounds})  {TAG}"]
            + ([f"    if (masterproc) write(iulog,*) '{prefix}: ', this%cbuf  {TAG}"] if log else [])
        )

        # SetValues: drop the lines of the compact fields, zero them by class
        self.rewrite_zeroing(setvalues, "", classes)

        # generated procedures, after SetValues
        fe.after[setvalues.endline].extend(
            self.generated_procedures(prefix, f"class({self.sel.dtype}) :: this", classes)
        )

    def rewrite_embedded_type(self) -> None:
        """
        A holder embedded in its instances' types (a nutrient base or role
        type): `cbuf` on the holder, plain module procedures
        `<holder>_compact_init/_compact_view/_full_view` (a type-bound
        procedure would stop SPEL's analysis from flattening the holder's
        fields into `inst%core%field`), CompactInit called from each concrete
        Init after its special-patch SetValues, and the zeroing in the shared
        `<holder>_setvalues` (base type) or in the concrete SetValues routines
        (role type, under `this%<path>%`).
        """
        holder = self.sel.holder
        base = holder.type
        fe = self.file(holder.dtype.filepath)
        classes = self.classes()
        self.buffer_use(fe)

        _, last, end = self.type_span(fe, base)
        fe.after[last].append(
            f"    type(compact_buffer_type) :: cbuf  ! compact storage of some fields above {TAG}"
        )
        fe.after[end].append(
            f"  public :: {base}_compact_init, {base}_compact_view, {base}_full_view  {TAG}"
        )
        mod_end = self.module_tree(fe).end_ln
        fe.before[mod_end].extend(
            self.generated_procedures(base, f"type({base}), intent(inout) :: this", classes)
        )
        holder_module = getattr(holder.dtype, "declaration", None) or Path(holder.dtype.filepath).stem

        # each concrete Init: CompactInit after the special-patch SetValues call
        done: set[str] = set()
        for emb in holder.embeddings:
            cdtype = self.fut.type_dict[emb.concrete]
            init_id = cdtype.procedures.get("init")
            if not isinstance(init_id, str) or init_id in done:
                if not isinstance(init_id, str):
                    raise RewriteError(f"{emb.concrete} has no Init procedure")
                continue
            done.add(init_id)
            init = self.subs[init_id]
            fe_c = self.file(init.filepath)
            ln = self.init_setvalues_call(init)
            bounds = self.init_bounds(init)
            log = self.can_log(fe_c)
            fe_c.after[statement_end(fe_c.lines, ln)].extend(
                [f"    call {base}_compact_init(this%{emb.path}, {bounds})  {TAG}"]
                + ([f"    if (masterproc) write(iulog,*) '{base} of {emb.concrete}: ', this%{emb.path}%cbuf  {TAG}"] if log else [])
            )
            if fe_c.path != fe.path:
                key = (str(fe_c.path), base)
                if key not in self._buffer_use:
                    self._buffer_use.add(key)
                    fe_c.after[self.module_use_line(fe_c)].append(
                        f"  use {holder_module}, only : {base}_compact_init  {TAG}"
                    )

        # zeroing: the shared routine of a base type, else the concrete SetValues routines
        if "setvalues" in holder.routines:
            self.rewrite_zeroing(self.subs[holder.routines["setvalues"]], "", classes)
        else:
            seen: set[str] = set()
            for emb in holder.embeddings:
                sid = self.fut.type_dict[emb.concrete].procedures.get("setvalues")
                if not isinstance(sid, str):
                    raise RewriteError(f"{emb.concrete} has no SetValues procedure")
                if sid in seen:
                    continue
                seen.add(sid)
                self.rewrite_zeroing(self.subs[sid], emb.path, classes)

    def can_log(self, fe: FileEdits) -> bool:
        """Whether the module imports masterproc and iulog (to log the buffer)."""
        names = {local for st in self.head_uses(fe) if st.has_only for local, _ in use_items(st)}
        return {"masterproc", "iulog"} <= names

    def zero_block(self, classes, num: str, filt: str, value: str, path: str = "") -> list[str]:
        """
        Explicit assignments (visible to SPEL's analysis): a contiguous fill of
        each clump's compact range once bound, the filter elements of the full
        layout copies before (the special-patch call in Init). `path`: the
        component of `this` that holds the fields and the buffer (`retrans`).
        """
        this = f"this%{path}" if path else "this"

        def guarded(guard, body, indent):
            if guard is None:
                return [f"{indent}{line}" for line in body]
            cond = guard if guard.startswith("(") and guard.count("(") == 1 else f"({guard})"
            return [f"{indent}if {cond} then", *(f"{indent}   {line}" for line in body), f"{indent}end if"]

        def loop(index: str, comps: list[str]) -> list[str]:
            return (
                [f"do concurrent (fi = 1:{num})"]
                + [f"   {this}%{c}({index}) = {value}" for c in comps]
                + ["end do"]
            )

        out = [f"    ! compact fields, by zeroing class  {TAG}", f"    if ({this}%cbuf%bound) then"]
        for guard, comps in classes.values():
            out += guarded(guard, loop(f"{K0}+fi", comps), "       ")
        out.append("    else")
        for guard, comps in classes.values():
            out += guarded(guard, loop(f"{filt}(fi)", comps), "       ")
        out.append(f"    end if  {TAG}")
        return out

    def classes(self) -> dict[int, tuple]:
        """class number -> (Fortran guard or None, [components])"""
        out: dict[int, tuple] = {}
        by_guard: dict[str, list[str]] = defaultdict(list)
        for comp, zc in self.sel.components.items():
            by_guard[zc].append(comp)
        for k, (zc, comps) in enumerate(by_guard.items(), 1):
            guards = [g if g.startswith("(") and g.endswith(")") else f"({g})" for g in zc.split(" & ")]
            guard = None if zc == "always" else " .and. ".join(guards)
            out[k] = (guard, comps)
        return out

    def init_bounds(self, init) -> str:
        names = [d.name for d in init.record.dummy_args] if init.record else []
        if not names:
            tree = parse_routine(init.filepath, init.startline, init.endline)
            names = [a.lower() for a in tree.args]
        if self.sel.subgrid == "p" and {"begp", "endp"} <= set(names):
            return "begp, endp"
        if self.sel.subgrid == "c" and {"begc", "endc"} <= set(names):
            return "begc, endc"
        raise RewriteError(f"{init.id}: no bounds dummies for subgrid {self.sel.subgrid} in {names}")

    def zero_lines(self, setvalues, path: str = "") -> dict[str, list[int]]:
        """component -> lines assigning `this%<path>%component` in the routine."""
        want = f"this%{path}%" if path else "this%"
        out: dict[str, list[int]] = defaultdict(list)
        for e in setvalues.record.accesses(status="w"):
            if not e.path.startswith(want):
                continue
            comp = e.path[len(want):]
            if "%" not in comp and e.ln not in out[comp]:
                out[comp].append(e.ln)
        return out

    # --- driver, clump bounds, module ---
    def rewrite_driver(self, unpack_after: str) -> None:
        drv = self.subs[DRIVER_ID]
        fe = self.file(drv.filepath)
        calls = [c for c in drv.record.calls if c.name.lower() == unpack_after.lower()]
        if not calls:
            raise RewriteError(f"elm_drv has no call to {unpack_after}")
        call = calls[-1]
        callee = self.subs.get(next(
            (b.callee for b in drv.record_access.bindings if b.ln == call.ln), ""
        ))
        dummies = [d.name for d in callee.record.dummy_args] if callee is not None else []
        args = {}
        for i, a in enumerate(call.args):
            key = a.keyword or (dummies[i] if i < len(dummies) else None)
            value = a.expr.value if isinstance(a.expr, KeywordArgument) else a.expr
            args[key] = str(value).replace(" ", "")
        end = statement_end(fe.lines, call.ln)
        indent = re.match(r"\s*", fe.lines[call.ln]).group(0)
        block = [
            f"{indent}! copy the compact fields to their full layout for history  {TAG}",
            f"{indent}call t_startf('compact_unpack')",
        ]
        for sel in self.sels:
            main = {"p": "soilp", "c": "soilc"}[sel.subgrid]
            num, filt = args.get(f"num_{main}"), args.get(f"filter_{main}")
            if num is None or filt is None:
                raise RewriteError(f"{unpack_after}: no num_{main}/filter_{main} arguments")
            if sel.holder is not None:
                block += [f"{indent}call {e.prefix}%cbuf%unpack({num}, {filt})" for e in sel.holder.embeddings]
            else:
                block += [f"{indent}call {inst}%cbuf%unpack({num}, {filt})" for inst in sel.instances]
        block.append(f"{indent}call t_stopf('compact_unpack')")
        fe.after[end].extend(block)

        # the instances elm_driver doesn't import yet
        missing: dict[str, list[str]] = defaultdict(list)
        for sel in self.sels:
            embs = sel.holder.embeddings if sel.holder is not None else None
            for inst in sel.instances:
                if known(drv.record, inst):
                    continue
                ctype = next((e.concrete for e in embs if e.instance == inst), sel.dtype) if embs else sel.dtype
                missing[self.fut.type_dict[ctype].instances[inst].declaration].append(inst)
        for mod, insts in sorted(missing.items()):
            fe.after[self.module_use_line(fe)].append(f"  use {mod}, only : {', '.join(insts)}  {TAG}")

    def module_use_line(self, fe: FileEdits) -> int:
        """The module's first use statement (new uses go after it)."""
        uses = self.head_uses(fe)
        if not uses:
            raise RewriteError(f"{fe.path}: the module has no use statement to add to")
        return uses[0].lineno

    def rewrite_decomp(self) -> None:
        for name, begp in DECOMP_ROUTINES.items():
            sub = self.subs.get(f"decompmod::{name}")
            if sub is None:
                raise RewriteError(f"decompmod::{name} not in the analysis")
            fe = self.file(sub.filepath)
            header = statement_end(fe.lines, sub.startline)
            fe.after[header].append(f"     use CompactLayoutMod, only : compact_set_clump  {TAG}")
            end = self.routine_end(sub)
            if end != sub.endline:
                raise RewriteError(f"{fe.path}:{sub.endline + 1}: not the end of {sub.id}")
            fe.before[end].append(f"     call compact_set_clump({begp})  {TAG}")

    # --- blocked filter loops ---
    def rewrite_blocked_loops(self, sub) -> int:
        """
        `do fi = 1, num, block` around `associate (idx => filter(fi:min(...)))`
        and assignments `x(idx, ...) = ...` becomes `do concurrent (fi = 1:num)`
        with `x(filter(fi), ...) = ...`: the same fields, one element per
        iteration. nvfortran handles the associate-name subscript very slowly (a
        per-statement cost about 1000x the stores). A block the compact rewrite
        emptied is dropped. Returns the loops rewritten.
        """
        rec = sub.record
        fe = self.file(sub.filepath)
        n = 0
        for loop in rec.all_loops():
            node = loop.node
            body = node.body.statements
            if node.step is None or len(body) != 1 or not isinstance(body[0], AssociateConstruct):
                continue
            assoc = body[0]
            if len(assoc.associations) != 1:
                continue
            (name, selector), = assoc.associations.items()
            if not isinstance(selector, FuncExpression) or len(selector.args) != 1:
                continue
            bounds = selector.args[0]
            if not isinstance(bounds, BoundsExpression) or str(bounds.start).lower() != loop.index:
                continue
            filt = str(selector.function)
            start, end = str(node.start), str(node.end)
            do_ln, end_ln = loop.start_ln, loop.end_ln
            if statement_end(fe.lines, do_ln) != do_ln or node.lineno != do_ln or node.end_ln != end_ln:
                raise RewriteError(f"{fe.path}:{do_ln + 1}: unexpected blocked loop: {fe.lines[do_ln].strip()}")
            assoc_end = statement_end(fe.lines, assoc.lineno)
            for ln in (assoc.end_ln, *range(assoc.lineno, assoc_end + 1)):
                fe.deletes.add(ln)
            use = re.compile(rf"(?<![%\w]){re.escape(name)}\b", re.IGNORECASE)
            kept = 0
            for ln in range(assoc_end + 1, assoc.end_ln):
                if use.search(fe.lines[ln].split("!")[0]) and ln not in fe.deletes:
                    fe.subs[ln].append((use, f"{filt}({loop.index})"))
                    kept += 1
            if kept:
                fe.subs[do_ln].append(
                    (re.compile(r"^(\s*).*$"), rf"\g<1>do concurrent ({loop.index} = {start}:{end})  {TAG}")
                )
            else:  # every field of the block is compact now
                for ln in range(do_ln, end_ln + 1):
                    fe.deletes.add(ln)
            n += 1
        return n

    # --- run ---
    def build(self, unpack_after: str, loop_types=()) -> None:
        if self.sels:
            self.rewrite_sites()
            for sel in self.sels:
                self.sel = sel
                self.rewrite_type()
            self.rewrite_driver(unpack_after)
            self.rewrite_decomp()
        done: set[str] = set()
        for dtype in loop_types:
            dt = self.fut.type_dict[dtype]
            sids = [dt.procedures.get("setvalues")]
            sids += [base_routine(self.subs, h, "setvalues") for _, h in embedded_holders(self.fut.type_dict, dt)]
            for sid in sids:
                if isinstance(sid, str) and sid in self.subs and sid not in done:
                    done.add(sid)
                    self.notes.append(f"{sid}: {self.rewrite_blocked_loops(self.subs[sid])} blocked loops -> do concurrent")

    def main_dir(self) -> Path:
        return Path(self.subs[DRIVER_ID].filepath).parent

    def diff(self) -> str:
        out = []
        for fe in self.files.values():
            out.extend(
                difflib.unified_diff(
                    [l + "\n" for l in fe.lines],
                    [l + "\n" for l in fe.result()],
                    fromfile=str(fe.path),
                    tofile=str(fe.path),
                )
            )
        return "".join(out)

    def apply(self, manifest: dict, output: Path | None = None, replace: bool = False) -> list[Path]:
        """
        Rewrite the sources in place, or write the rewritten files (by
        basename, as for a case's SourceMods/src.elm) to `output`. An `output`
        with an earlier rewrite's manifest is refused, unless `replace`: then
        exactly the files that manifest lists are removed first.
        """
        main = self.main_dir()
        if (main / TEMPLATE.name).exists() or (main / MANIFEST).exists():
            raise RewriteError(f"{main} already has {TEMPLATE.name} or {MANIFEST}: already rewritten?")
        dest = main if output is None else Path(output)
        if output is not None and (dest / MANIFEST).exists():
            if not replace:
                raise RewriteError(f"{dest} has an earlier rewrite ({MANIFEST}); pass --replace")
            for path in written_files(dest):
                path.unlink()
        dest.mkdir(parents=True, exist_ok=True)
        written = []
        for fe in self.files.values():
            target = fe.path if output is None else dest / fe.path.name
            target.write_text("\n".join(fe.result()))
            written.append(target)
        (dest / MANIFEST).write_text(json.dumps(manifest, indent=1) + "\n")
        if not self.sels:  # SetValues loops only
            return written + [dest / MANIFEST]
        shutil.copy(TEMPLATE, dest / TEMPLATE.name)
        return written + [dest / TEMPLATE.name, dest / MANIFEST]


def written_files(dest: Path) -> list[Path]:
    """The files an earlier rewrite wrote to `dest` (by its manifest)."""
    m = json.loads((dest / MANIFEST).read_text())
    names = {Path(f).name for f in m["files"]} | {TEMPLATE.name, MANIFEST}
    return [dest / n for n in sorted(names) if (dest / n).is_file()]


def manifest(rewriter: Rewriter, unpack_after: str, spel_commit: str, e3sm: dict) -> dict:
    types = {}
    sel0 = rewriter.sel
    for sel in rewriter.sels:
        rewriter.sel = sel
        types[sel.dtype] = {
            "instances": sel.instances,
            "embedded_in": {e.instance: e.path for e in sel.holder.embeddings} if sel.holder and sel.holder.embedded else {},
            "classes": {k: {"guard": g, "fields": cs} for k, (g, cs) in rewriter.classes().items()},
            "unpack": sorted(c for c, u in sel.unpack.items() if u),
            "sites": len(sel.sites),
        }
    rewriter.sel = sel0
    out = {
        "generated_by": "spel compact rewrite",
        "spel_commit": spel_commit,
        "e3sm": e3sm,
        "unpack_after": unpack_after,
        "types": types,
        "files": sorted(str(f.path) for f in rewriter.files.values()),
    }
    nm = nutrient_manifest(rewriter.fut)
    if nm is not None:  # the nutrient transform state the rewrite assumed
        out["nutrient"] = {k: nm.get(k) for k in ("spel_commit", "e3sm", "generated_by") if k in nm}
    return out
