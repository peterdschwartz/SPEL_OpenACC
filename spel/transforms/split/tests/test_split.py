import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from spel.scripts.fortran_modules import FortranModule
from spel.scripts.fortran_parser.scope_walk import walk_subroutine
from spel.scripts.fortran_parser.spel_ast import AccessStatement, ModuleConstruct, SaveStatement, TypeDef
from spel.scripts.module_resolver import ModuleResolver
from spel.scripts.types import LineTuple, LogicalLineIterator
from spel.scripts.utilityFunctions import Variable
from spel.scripts.registrations import parse_routine
from spel.transforms.split.modules import (
    SplitError,
    Splitter,
    elm_data_types_plan,
    load_source,
    spelled,
    squeeze,
    wrap,
)

gfortran = pytest.mark.skipif(not shutil.which("gfortran"), reason="needs gfortran")

KIND = """\
module shr_kind_mod
  implicit none
  integer, parameter :: shr_kind_r8 = selected_real_kind(12)
end module shr_kind_mod
"""

HELPER = """\
module helper_mod
  use shr_kind_mod, only : r8 => shr_kind_r8
  implicit none
  real(r8), parameter :: spval = 1.e36_r8
  integer :: unused_thing = 0
end module helper_mod
"""

# a second split source defining the same parameter: one copy in the new module
OTHER = """\
module OtherMod
  use shr_kind_mod, only : r8 => shr_kind_r8
  implicit none
  save
  private
  integer, parameter, private :: block_size = 32
  type, public :: other_state
     real(r8), pointer :: q(:) => null()
   contains
     procedure, public :: init => other_init
  end type other_state
  public :: other_stays
contains
  subroutine other_init(this, n)
    class(other_state) :: this
    integer, intent(in) :: n
    allocate(this%q(n)) ; this%q(:) = block_size
  end subroutine other_init
  subroutine other_stays(x)
    real(r8), intent(inout) :: x
    x = x + block_size
  end subroutine other_stays
end module OtherMod
"""

# a module outside the analysis (like shr_infnan_mod): a defined assignment, used without its name
NAN = """\
module nan_mod
  use shr_kind_mod, only : r8 => shr_kind_r8
  implicit none
  type, public :: nan_type
  end type nan_type
  type(nan_type), parameter :: nan_value = nan_type()
  interface assignment(=)
     module procedure set_nan
  end interface
contains
  elemental subroutine set_nan(x, v)
    real(r8), intent(out) :: x
    type(nan_type), intent(in) :: v
    x = 1.e36_r8
  end subroutine set_nan
end module nan_mod
"""

BIG = """\
module BigMod
  !
  ! the module's description stays
  !
  use shr_kind_mod, only : r8 => shr_kind_r8
  use helper_mod  , only : spval, unused_thing
  use nan_mod     , only : nan => nan_value, assignment(=)
  implicit none
  save
  public
  real(r8), public :: scale = 2._r8
  !$acc declare copyin(scale)
  integer, parameter, private :: block_size = 32

  ! the energy state
  type, public :: energy_state
     real(r8), pointer :: t(:) => null()
   contains
     procedure, public :: init => energy_init
  end type energy_state

  type, public :: water_state
     real(r8), pointer :: h2o(:) => null()
   contains
     procedure, public :: init => water_init
  end type water_state

  type(energy_state), public, target :: es
  type(water_state) , public, target :: ws
  !$acc declare create(es, ws)

contains

  !-----------------------------------------------------------------------
  subroutine energy_init(this, n)
    class(energy_state) :: this
    integer, intent(in) :: n
    allocate(this%t(n)) ; this%t(:) = nan
    this%t(1) = spval + block_size
  end subroutine energy_init

  !-----------------------------------------------------------------------
  subroutine water_init(this, n)
    class(water_state) :: this
    integer, intent(in) :: n
    allocate(this%h2o(n))
    this%h2o(:) = es%t(:) * scale
  end subroutine water_init

  !-----------------------------------------------------------------------
  subroutine stays_here(x)
    real(r8), intent(inout) :: x
    x = x * block_size
  end subroutine stays_here

end module BigMod
"""

CLIENT = """\
module client
  use shr_kind_mod, only : r8 => shr_kind_r8
  use BigMod      , only : es, ws, Energy_State   ! instances and a type
  implicit none
contains
  subroutine setup(e)
    type(energy_state), intent(in) :: e
    call es%init(3)
    call ws%init(3)
  end subroutine setup
end module client
"""

MAIN = """\
program main
  use client, only : setup
  use BigMod, only : es, ws
  implicit none
  call setup(es)
  print '(es12.4)', ws%h2o(2)
end program main
"""


class Sub:
    """The bits of an analyzed Subroutine the splitter uses."""

    def __init__(self, module, path, start, end):
        self.module, self.filepath, self.startline, self.endline = module, path, start, end
        self.is_internal, self.host, self.record, self.syntax_tree = False, None, None, None

    def parse(self):
        self.syntax_tree = parse_routine(self.filepath, self.startline, self.endline)

    def walk_syntax_tree(self, scopes):
        res = ModuleResolver(self.module, scopes.mod_dict, scopes.sub_dict,
                             line_ranges=[(self.startline, self.endline)], scopes=scopes)
        self.record = walk_subroutine(self.syntax_tree, resolver=res)
        return self.record


def analysis(root: Path, files: dict[str, str]):
    """module_dict/subroutine_dict for small files, from SPEL's parse (paths relative to root)."""
    md, sd = {}, {}
    for name, text in files.items():
        path = root / name
        path.write_text(text)
        src = load_source(path)
        mod = FortranModule(name=src.key, fname=name, ln=src.tree.lineno)
        end = src.tree.contains_ln if src.tree.contains_ln is not None else src.tree.end_ln
        it = LogicalLineIterator([LineTuple(line=l, ln=i) for i, l in enumerate(src.lines)], log_name="t")
        mod.module_lines = [LineTuple(line=lt.line.strip().lower(), ln=lt.ln) for lt in it if lt.ln < end]
        mod.end_of_head_ln = end
        mod.use_stmts = [p.node for p in src.head if p.kind == "use"]
        for st in mod.use_stmts:
            st.module = st.module.lower()
        mod.modules = {st.module: None for st in mod.use_stmts}
        mod.defined_types = {p.node.name.lower(): None for p in src.head if p.kind == "type"}
        mod.global_vars = {d: Variable("real", d, "?", 0, 0) for p in src.head if p.kind == "var" for d in p.defines}
        for p in src.subs:
            sid = f"{src.key}::{p.defines[0]}"
            mod.subroutines.add(sid)
            sd[sid] = Sub(src.key, path, p.node.lineno, p.node.end_ln)
        md[src.key] = mod
    return SimpleNamespace(module_dict=md, subroutine_dict=sd)


def plan(mod, type_name):
    return "StateTypes" if type_name.endswith("_state") else None


@pytest.fixture
def split(tmp_path):
    (tmp_path / "components").mkdir()
    files = {"components/shr_kind_mod.F90": KIND, "components/helper_mod.F90": HELPER,
             "components/BigMod.F90": BIG, "components/OtherMod.F90": OTHER, "components/client.F90": CLIENT}
    fut = analysis(tmp_path, files)
    sp = Splitter(fut, ["bigmod", "othermod"], plan, tmp_path)
    sp.build()
    return tmp_path, sp


def text(sp, root, name):
    return "\n".join(sp.client_edits[root / "components" / name])


def test_parser_module_construct(tmp_path):
    path = tmp_path / "b.F90"
    path.write_text(BIG)
    src = load_source(path)
    assert isinstance(src.tree, ModuleConstruct) and src.tree.name == "bigmod"
    kinds = [type(p.node).__name__ for p in src.head]
    assert "SaveStatement" in kinds and "AccessStatement" in kinds
    (t,) = [p.node for p in src.head if isinstance(p.node, TypeDef) and p.node.name == "energy_state"]
    assert src.lines[t.end_ln].strip() == "end type energy_state"
    # comments before a piece belong to it
    (e,) = [p for p in src.head if p.defines == ["energy_state"]]
    assert src.lines[e.first].strip() == "! the energy state"
    assert [p.defines[0] for p in src.subs] == ["energy_init", "water_init", "stays_here"]
    assert src.lines[src.subs[0].first].startswith("  !----")


def test_split_moves_types_and_keeps_instances(split):
    root, sp = split
    new = text(sp, root, "StateTypes.F90")
    big = text(sp, root, "BigMod.F90")
    # types, their procedures, and the variable only their procedures use (with its directive)
    for s in ("type, public :: energy_state", "subroutine water_init", "real(r8), public :: scale",
              "!$acc declare copyin(scale)", "! the energy state"):
        assert s in new
    # the source keeps its description, the instances and their directive, nothing else
    assert "! the module's description stays" in big and "type(energy_state), public, target :: es" in big
    assert "!$acc declare create(es, ws)" in big and "subroutine energy_init" not in big
    assert big.count("the module's description stays") == 1
    assert "use StateTypes, only : energy_state, water_state" in big
    # uses: what the code needs, spelled as the source spells it; unused names dropped
    assert "use nan_mod, only : nan => nan_value, assignment(=)" in new
    assert "use helper_mod, only : spval" in new
    assert "unused_thing" not in new and "helper_mod" not in big and "nan_mod" not in big
    assert "use shr_kind_mod, only : r8 => shr_kind_r8" in new
    # a parameter used on both sides is copied, not moved (no use of the source, no cycle)
    assert new.count("integer, parameter, private :: block_size = 32") == 1  # from two sources, once
    assert "subroutine other_init" in new and "type, public :: other_state" in new
    assert "integer, parameter, private :: block_size = 32" in big and "subroutine stays_here" in big
    assert "block_size" not in " ".join(l for l in new.split("\n") if l.strip().startswith("use "))


def test_split_passes_instances_the_moved_code_reads(split):
    root, sp = split
    new = text(sp, root, "StateTypes.F90")
    assert "subroutine water_init(this, n, es)" in new
    assert "type(energy_state), intent(in) :: es" in new
    client = text(sp, root, "client.F90")
    assert "call ws%init(3, es=es)" in client and "call es%init(3)" in client


def test_split_rewrites_client_uses(split):
    root, sp = split
    client = text(sp, root, "client.F90")
    assert "use BigMod, only : es, ws" in client
    assert "use StateTypes, only : Energy_State ! instances and a type" in client


def test_split_refuses_existing_targets(tmp_path):
    (tmp_path / "components").mkdir()
    files = {"components/shr_kind_mod.F90": KIND, "components/helper_mod.F90": HELPER,
             "components/BigMod.F90": BIG, "components/client.F90": CLIENT}
    fut = analysis(tmp_path, files)
    (tmp_path / "components" / "StateTypes.F90").write_text("module StateTypes\nend module StateTypes\n")
    with pytest.raises(SplitError, match="exist already"):
        Splitter(fut, ["bigmod"], plan, tmp_path).build()


@gfortran
def test_split_output_compiles_and_runs(split, tmp_path):
    root, sp = split
    sp.apply()
    comp = root / "components"
    (comp / "main.F90").write_text(MAIN)
    (comp / "nan_mod.F90").write_text(NAN)
    order = ["shr_kind_mod", "helper_mod", "nan_mod", "StateTypes", "BigMod", "client", "main"]
    for m in order:
        r = subprocess.run(["gfortran", "-c", f"{m}.F90"], cwd=comp, capture_output=True, text=True)
        assert r.returncode == 0, f"{m}: {r.stderr}"
    subprocess.run(["gfortran", "-o", "t"] + [f"{m}.o" for m in order], cwd=comp, check=True)
    out = subprocess.run(["./t"], cwd=comp, capture_output=True, text=True, check=True).stdout
    assert float(out) == 2e36


def test_helpers():
    assert spelled(["  use ColumnDataType , only : x"], "columndatatype") == "ColumnDataType"
    assert spelled(["  x_columndatatype = 1"], "columndatatype") == "columndatatype"
    lines = wrap("  use m, only : ", [f"name_{i:02d}" for i in range(20)], width=60)
    assert all(len(l) <= 62 for l in lines) and lines[0].endswith("&") and not lines[-1].endswith("&")
    assert squeeze(["a", "", "", "b", "", ""]) == ["a", "", "b", ""]


def test_elm_plan():
    assert elm_data_types_plan("vegetationdatatype", "vegetation_nutrient_state") == "NutrientStateType"
    assert elm_data_types_plan("columndatatype", "column_mineral_flux") == "NutrientFluxType"
    assert elm_data_types_plan("gridcelldatatype", "gridcell_nutrient_flux") == "NutrientFluxType"
    assert elm_data_types_plan("columndatatype", "column_water_state") == "ColumnStateTypes"
    assert elm_data_types_plan("vegetationdatatype", "vegetation_carbon_flux") == "VegetationFluxTypes"
    assert elm_data_types_plan("gridcelldatatype", "gridcell_carbon_state") is None
