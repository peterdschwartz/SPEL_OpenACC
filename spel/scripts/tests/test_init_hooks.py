import textwrap
from types import SimpleNamespace

from spel.scripts.init_hooks import hook_reads_and_allocs, hook_routines

SRC = textwrap.dedent("""\
    module subgridAveMod
    contains
      subroutine init_subgrid_ave(bounds)
        call init_scale_c2l(bounds)
        allocate(grc_col_ptr(begg:endg+1), grc_col_idx(begc:endc))
        call build_child_map(begg, endg, begc, endc, col_pp%gridcell(begc:endc), grc_col_ptr, grc_col_idx)
      end subroutine init_subgrid_ave
      subroutine init_scale_c2l(bounds)
        allocate(main_scale_c2l(bounds%begc:bounds%endc, num_c2l_types))
        main_scale_c2l(c,urbanf) = 3.0 * lun_pp%canyon_hwr(l)  ! urban walls
      end subroutine init_scale_c2l
    end module subgridAveMod
    """)


def test_hook_reads_and_allocations(tmp_path):
    path = tmp_path / "subgridAveMod.F90"
    path.write_text(SRC)
    lines = SRC.splitlines()

    def sub(name):
        start = next(i for i, ln in enumerate(lines) if f"subroutine {name}(" in ln)
        end = next(i for i, ln in enumerate(lines) if f"end subroutine {name}" in ln)
        return SimpleNamespace(filepath=path, startline=start, endline=end)

    sub_dict = {
        "subgridavemod::init_subgrid_ave": sub("init_subgrid_ave"),
        "subgridavemod::init_scale_c2l": sub("init_scale_c2l"),
    }
    subs = hook_routines(sub_dict, "subgridavemod::init_subgrid_ave")
    assert len(subs) == 2
    reads, allocs = hook_reads_and_allocs(subs)
    assert reads == {"col_pp%gridcell", "lun_pp%canyon_hwr"}
    assert allocs == {"grc_col_ptr", "grc_col_idx", "main_scale_c2l"}
