"""
Unit-test support for types rewritten by `spel compact rewrite`.

A generated unit test reads and writes the full layout (nc_io works on the
components as allocated), and duplicate_sets offsets them. Around the compute
loop main.F90 therefore binds the compact instances and packs each clump's
filter elements from the full copies, and afterwards unpacks every compact
field and unbinds:

  !#COMPACT_INIT    after elm_init: give the fields compact storage (CompactInit)
  !#COMPACT_BEFORE  CompactView, then pack per clump
  !#COMPACT_AFTER   unpack(all) per clump, then FullView

The clump offset comes from get_clump_bounds (the rewritten decompMod).
"""

from __future__ import annotations

from dataclasses import dataclass

from spel.transforms.compact.index_forms import MAIN_FILTER

BIND = "compactview"
# component types built at run time (CompactInit), never captured
RUNTIME_TYPES = {"compact_buffer_type"}


@dataclass(frozen=True)
class CompactInstance:
    """
    An instance with compact storage: `inst%cbuf` of a type with type-bound
    Compact procedures (`bound`), or `inst%<path>%cbuf` of an embedded holder
    (a nutrient base/role type) whose procedures are plain module procedures
    `<holder>_compact_init/_compact_view/_full_view` in `module`.
    """

    instance: str
    subgrid: str
    path: str = ""
    holder: str = ""
    module: str = ""  # module declaring the instance (bound) or the holder's procedures
    bound: bool = True
    holder_module: str = ""  # for a capture: the holder's module when `module` is the instance's

    @property
    def prefix(self) -> str:
        return f"{self.instance}%{self.path}" if self.path else self.instance

    def call(self, what: str) -> str:
        """`what`: init(args) | view | full."""
        if self.bound:
            name = {"view": "CompactView()", "full": "FullView()"}.get(what, f"CompactInit({what[5:-1]})")
            return f"call {self.instance}%{name}"
        proc = {"view": "compact_view", "full": "full_view"}.get(what, "compact_init")
        args = f"{self.prefix}, {what[5:-1]}" if what.startswith("init(") else self.prefix
        return f"call {self.holder}_{proc}({args})"

    @property
    def procedures(self) -> list[str]:
        return [f"{self.holder}_{p}" for p in ("compact_init", "compact_view", "full_view")]


def deactivate_runtime_components(type_dict: dict) -> list[str]:
    """Mark components of RUNTIME_TYPES inactive, so no IO/alloc/copy code is made for them."""
    dropped = []
    for dtype in type_dict.values():
        for name, comp in dtype.components.items():
            if comp.active and str(comp.type).lower() in RUNTIME_TYPES:
                comp.active = False
                dropped.append(f"{dtype.type_name}%{name}")
    return sorted(dropped)


def _subgrid(dtype, name: str) -> str:
    subgrids = {
        (v.bounds or "").replace(" ", "").lower().split(":")[0].split("%")[-1][-1:]
        for v in dtype.components.values()
        if not getattr(v, "nested", False)
        and (v.bounds or "").replace(" ", "").lower().startswith(("begp", "begc", "bounds%begp", "bounds%begc"))
    }
    if len(subgrids) != 1 or (sg := subgrids.pop()) not in MAIN_FILTER:
        raise ValueError(f"{name}: compact type {dtype.type_name} on subgrids {subgrids}")
    return sg


def compact_instances(type_dict: dict, active_instances: dict) -> list[CompactInstance]:
    """
    The case's instances with compact storage: their type has CompactView
    (bound), or one of its data-only components (`core`, `retrans`) has a
    `cbuf` (an embedded holder, with plain procedures).
    """
    out = []
    for name, var in sorted(active_instances.items()):
        dtype = type_dict.get(var.type)
        if dtype is None:
            continue
        if BIND in {str(k).lower() for k in dtype.procedures}:
            out.append(CompactInstance(name, _subgrid(dtype, name)))
            continue
        for cname, comp in dtype.components.items():
            if getattr(comp, "nested", False) or str(comp.type).lower() in RUNTIME_TYPES:
                continue
            holder = type_dict.get(comp.type)
            if holder is None or "cbuf" not in holder.components:
                continue
            module = getattr(holder, "declaration", None) or ""
            out.append(CompactInstance(name, _subgrid(holder, name), cname, holder.type_name, module, bound=False))
    return out


def hook_lines(instances: list[CompactInstance]) -> dict[str, list[str]]:
    """Lines for the !#COMPACT_* tokens of main.F90 (empty if no instance)."""
    if not instances:
        return {}
    # multicore OpenACC runs in host memory, so the compact buffers and views need
    # nothing; a real device (SPEL_ACC_GPU, set by the generated CMake for ACC=GPU)
    # would need the buffer and its views deep-copied
    init = [
        "#if defined(_OPENACC) && defined(SPEL_ACC_GPU)\n",
        '   stop "compact layout (spel compact rewrite): no OpenACC GPU unit tests yet"\n',
        "#endif\n",
    ]
    before, after, uses = [], [], []
    seen_mod: dict[str, list[str]] = {}
    for ci in instances:
        sg = ci.subgrid
        main = MAIN_FILTER[sg].split("%")[1]
        init.append(f"{ci.call(f'init(bounds_proc%beg{sg}, bounds_proc%end{sg})')}\n")
        before.append(f"      {ci.call('view')}\n")
        after_bind = f"      {ci.call('full')}\n"
        filt = f"filter(nc)%num_{main}, filter(nc)%{main}"
        before += [
            "      do nc = 1, nclumps\n",
            "         call get_clump_bounds(nc, bounds_clump)\n",
            f"         call {ci.prefix}%cbuf%pack({filt})\n",
            "      end do\n",
        ]
        after += [
            "      do nc = 1, nclumps\n",
            "         call get_clump_bounds(nc, bounds_clump)\n",
            f"         call {ci.prefix}%cbuf%unpack({filt}, all=.true.)\n",
            "      end do\n",
            after_bind,
        ]
        if not ci.bound and ci.module:
            procs = seen_mod.setdefault(ci.module, [])
            procs.extend(p for p in ci.procedures if p not in procs)
    for mod, procs in sorted(seen_mod.items()):
        uses.append(f"use {mod}, only : {', '.join(procs)}\n")
    out = {"!#COMPACT_INIT": init, "!#COMPACT_BEFORE": before, "!#COMPACT_AFTER": after}
    if uses:
        out["!#USE_START"] = uses
    return out
