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

from spel.transforms.compact.index_forms import MAIN_FILTER

BIND = "compactview"
# component types built at run time (CompactInit), never captured
RUNTIME_TYPES = {"compact_buffer_type"}


def deactivate_runtime_components(type_dict: dict) -> list[str]:
    """Mark components of RUNTIME_TYPES inactive, so no IO/alloc/copy code is made for them."""
    dropped = []
    for dtype in type_dict.values():
        for name, comp in dtype.components.items():
            if comp.active and str(comp.type).lower() in RUNTIME_TYPES:
                comp.active = False
                dropped.append(f"{dtype.type_name}%{name}")
    return sorted(dropped)


def compact_instances(type_dict: dict, active_instances: dict) -> list[tuple[str, str]]:
    """(instance, subgrid) of the case's instances whose type has CompactView."""
    out = []
    for name, var in sorted(active_instances.items()):
        dtype = type_dict.get(var.type)
        if dtype is None or BIND not in {str(k).lower() for k in dtype.procedures}:
            continue
        subgrids = {
            (v.bounds or "").replace(" ", "").lower().split(":")[0].split("%")[-1][-1:]
            for v in dtype.components.values()
            if (v.bounds or "").replace(" ", "").lower().startswith(("begp", "begc", "bounds%begp", "bounds%begc"))
        }
        if len(subgrids) != 1 or (sg := subgrids.pop()) not in MAIN_FILTER:
            raise ValueError(f"{name}: compact type {dtype.type_name} on subgrids {subgrids}")
        out.append((name, sg))
    return out


def hook_lines(instances: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Lines for the !#COMPACT_* tokens of main.F90 (empty if no instance)."""
    if not instances:
        return {}
    init = [
        "#ifdef _OPENACC\n",
        '   stop "compact layout (spel compact rewrite): no OpenACC unit tests yet"\n',
        "#endif\n",
    ]
    before, after = [], []
    for inst, sg in instances:
        main = MAIN_FILTER[sg].split("%")[1]
        init.append(f"call {inst}%CompactInit(bounds_proc%beg{sg}, bounds_proc%end{sg})\n")
        before.append(f"      call {inst}%CompactView()\n")
        after_bind = f"      call {inst}%FullView()\n"
        filt = f"filter(nc)%num_{main}, filter(nc)%{main}"
        before += [
            "      do nc = 1, nclumps\n",
            "         call get_clump_bounds(nc, bounds_clump)\n",
            f"         call {inst}%cbuf%pack({filt})\n",
            "      end do\n",
        ]
        after += [
            "      do nc = 1, nclumps\n",
            "         call get_clump_bounds(nc, bounds_clump)\n",
            f"         call {inst}%cbuf%unpack({filt}, all=.true.)\n",
            "      end do\n",
            after_bind,
        ]
    return {"!#COMPACT_INIT": init, "!#COMPACT_BEFORE": before, "!#COMPACT_AFTER": after}
