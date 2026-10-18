"""
Gridcell subsets of the reference data.

A subset capture writes only some gridcells of the reference simulation,
with all of their topounits, landunits, columns and patches, renumbered
from 1, so the spel-*.nc files look like a capture of a smaller domain and
the unit test needs no changes.

The gridcells are chosen in ELM, at the first capture, by a mask
(`SubsetSpec`): named presets (`urban`, `lake`, `crop`, ...) or a Fortran
logical expression at one subgrid level, e.g.

    landunit: lun_pp%itype(l) == istsoil .and. lun_pp%wtgcell(l) > 0.5_r8

A gridcell matches if the expression is true for it or any of its
topounits/landunits/columns/patches. Up to `max_cells` matching gridcells
are kept, evenly spaced over the matches. With several MPI ranks, the rank
with the most matches writes the capture and the others write nothing.

nc_io does the writing (spel_subset_type, nc_subset_select): it keeps the
selected positions along each variable's subgrid dimension and renumbers the
subgrid index fields (netcdf_io.SUBGRID_INDEX_FIELDS). `subset_files` applies
the same rules offline to existing captures.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_CELLS = 100

# level -> (loop index, Fortran index of its gridcell, process bounds suffix)
LEVELS = {
    "g": ("g", "g", "g"),
    "t": ("t", "top_pp%gridcell(t)", "t"),
    "l": ("l", "lun_pp%gridcell(l)", "l"),
    "c": ("c", "col_pp%gridcell(c)", "c"),
    "p": ("p", "veg_pp%gridcell(p)", "p"),
}
LEVEL_NAMES = {
    "gridcell": "g", "g": "g",
    "topounit": "t", "t": "t",
    "landunit": "l", "l": "l",
    "column": "c", "c": "c",
    "patch": "p", "p": "p",
}
# Instances the selection uses (always) and the modules custom masks may use
TYPE_USES = (
    "GridcellType, only : grc_pp",
    "TopounitType, only : top_pp",
    "LandunitType, only : lun_pp",
    "ColumnType, only : col_pp",
    "VegetationType, only : veg_pp",
)
CUSTOM_USES = ("landunit_varcon", "column_varcon", "pftvarcon")


class SubsetError(ValueError):
    pass


@dataclass(frozen=True)
class MaskTerm:
    """A gridcell matches if `expr` holds at `level` for it or one of its children."""

    level: str
    expr: str
    uses: tuple[str, ...] = ()


# Weights: zero-weight landunits exist (e.g. urban with run_zero_weight_urban),
# so presets require a positive weight on the gridcell.
PRESETS: dict[str, tuple[MaskTerm, str]] = {
    "all": (MaskTerm("g", ".true."), "every gridcell"),
    "urban": (
        MaskTerm("l", "lun_pp%urbpoi(l) .and. lun_pp%wtgcell(l) > 0._r8"),
        "an urban landunit with weight > 0",
    ),
    "lake": (
        MaskTerm("l", "lun_pp%lakpoi(l) .and. lun_pp%wtgcell(l) > 0._r8"),
        "a lake landunit with weight > 0",
    ),
    "crop": (
        MaskTerm(
            "l",
            "lun_pp%itype(l) == istcrop .and. lun_pp%wtgcell(l) > 0._r8",
            ("landunit_varcon, only : istcrop",),
        ),
        "a crop landunit (istcrop) with weight > 0",
    ),
    "glacier": (
        MaskTerm(
            "l",
            "(lun_pp%itype(l) == istice .or. lun_pp%itype(l) == istice_mec) "
            ".and. lun_pp%wtgcell(l) > 0._r8",
            ("landunit_varcon, only : istice, istice_mec",),
        ),
        "a glacier landunit with weight > 0",
    ),
    "wetland": (
        MaskTerm(
            "l",
            "lun_pp%itype(l) == istwet .and. lun_pp%wtgcell(l) > 0._r8",
            ("landunit_varcon, only : istwet",),
        ),
        "a wetland landunit with weight > 0",
    ),
}

_CUSTOM = re.compile(r"^\s*(\w+)\s*:(.*)$", re.S)
_MAX = re.compile(r";\s*max\s*=\s*(\d+)\s*$", re.I)


@dataclass(frozen=True)
class SubsetSpec:
    mask: str
    terms: tuple[MaskTerm, ...]
    max_cells: int = DEFAULT_MAX_CELLS
    custom: bool = False

    @classmethod
    def parse(cls, text: str, max_cells: int | None = None) -> "SubsetSpec":
        """
        `urban`, `urban,lake` (either), or `<level>: <Fortran expression>`;
        an optional `; max=N` suffix overrides `max_cells`.
        """
        if m := _MAX.search(text):
            max_cells = int(m.group(1))
            text = text[: m.start()]
        text = text.strip()
        if max_cells is None:
            max_cells = DEFAULT_MAX_CELLS
        if max_cells < 1:
            raise SubsetError(f"subset max must be >= 1, got {max_cells}")
        if (m := _CUSTOM.match(text)) and m.group(1).lower() in LEVEL_NAMES:
            level = LEVEL_NAMES[m.group(1).lower()]
            expr = " ".join(m.group(2).split())
            check_expression(expr, level)
            return cls(text, (MaskTerm(level, expr),), max_cells, custom=True)
        names = [n.strip().lower() for n in text.split(",")]
        if unknown := [n for n in names if n not in PRESETS]:
            raise SubsetError(
                f"unknown subset mask {', '.join(unknown)!s}: use one of "
                f"{', '.join(PRESETS)} or '<level>: <Fortran expression>' "
                f"with level one of gridcell, topounit, landunit, column, patch"
            )
        return cls(",".join(names), tuple(PRESETS[n][0] for n in names), max_cells)

    @property
    def description(self) -> str:
        return f"{self.mask} (max {self.max_cells} gridcells)"

    def to_json(self) -> dict:
        return {"mask": self.mask, "max_cells": self.max_cells}

    @classmethod
    def from_json(cls, data: dict) -> "SubsetSpec":
        return cls.parse(data["mask"], data.get("max_cells", DEFAULT_MAX_CELLS))

    def uses(self) -> list[str]:
        uses = list(TYPE_USES)
        for term in self.terms:
            uses += [u for u in term.uses if u not in uses]
        if self.custom:
            uses += list(CUSTOM_USES)
        return uses


def check_expression(expr: str, level: str) -> None:
    """Cheap checks; the ELM build is the real test of a custom expression."""
    if not expr:
        raise SubsetError("empty subset expression")
    if bad := set(expr) & set(";!&\"'\n"):
        raise SubsetError(f"subset expression may not contain {''.join(sorted(bad))!r}: {expr}")
    if expr.count("(") != expr.count(")"):
        raise SubsetError(f"unbalanced parentheses in subset expression: {expr}")
    idx = LEVELS[level][0]
    if not re.search(rf"\b{idx}\b", expr, re.I):
        raise SubsetError(f"a {level}-level subset expression must use the index {idx!r}: {expr}")


# --------------------------------------------------------------------------
# Capture module (ELM side)
# --------------------------------------------------------------------------
def fortran_string(text: str, width: int = 60) -> str:
    """A character literal, split into concatenated pieces to keep lines short."""
    pieces = [text[i : i + width] for i in range(0, len(text), width)] or [""]
    return " // &\n      ".join("'" + p.replace("'", "''") + "'" for p in pieces)


def wrap_expression(expr: str, width: int = 70) -> str:
    """Continue a long expression over several lines (custom masks have no strings)."""
    lines, line = [], ""
    for word in expr.split(" "):
        if line and len(line) + len(word) > width:
            lines.append(line)
            line = ""
        line += ("" if not line else " ") + word
    return " &\n          ".join(lines + [line])


def capture_select_routine(spec: SubsetSpec, tag: str) -> str:
    """
    spel_select_subset(bounds) for SpelCapture_<tag>: sets spel_sub (the
    subset), spel_bounds_sub (its bounds, from 1) and spel_writer.
    """
    loops = ""
    for term in spec.terms:
        idx, parent, b = LEVELS[term.level]
        loops += (
            f"    do {idx} = bounds%beg{b}, bounds%end{b}\n"
            f"      if ({wrap_expression(term.expr)}) match({parent}) = .true.\n"
            f"    end do\n"
        )
    mask = fortran_string(spec.mask[:500])
    return f"""
  subroutine spel_select_subset(bounds)
    ! Gridcells of bounds matching the subset mask. The rank with the most
    ! matches (the lowest such rank) keeps up to spel_subset_max of them,
    ! evenly spaced, with their topounits, landunits, columns and patches;
    ! the other ranks write nothing.
    type(bounds_type), intent(in) :: bounds
    type(bounds_type) :: bp
    logical, allocatable :: match(:), keep(:)
    integer, allocatable :: cand(:)
    integer :: g, t, l, c, p, k, n, nmatch, nmax, rank, ierr
    call get_proc_bounds(bp)
    allocate (match(bp%begg:bp%endg), keep(bp%begg:bp%endg))
    match = .false.
    keep = .false.
{loops}    nmatch = count(match)
    call mpi_allreduce(nmatch, nmax, 1, MPI_INTEGER, MPI_MAX, mpicom, ierr)
    k = npes
    if (nmatch == nmax) k = iam
    call mpi_allreduce(k, rank, 1, MPI_INTEGER, MPI_MIN, mpicom, ierr)
    spel_writer = nmax > 0 .and. iam == rank
    if (nmax == 0 .and. masterproc) print *, 'SPEL subset ({tag}): no gridcell matches ', &
      {mask}
    if (.not. spel_writer) return

    cand = pack([(g, g = bp%begg, bp%endg)], match)
    n = min(nmatch, spel_subset_max)
    do k = 1, n
      keep(cand(1 + ((k - 1)*nmatch)/n)) = .true.
    end do
    call nc_subset_set_level(spel_sub, 1, bp%begg, keep)
    call nc_subset_set_level(spel_sub, 2, bp%begt, keep(top_pp%gridcell(bp%begt:bp%endt)))
    call nc_subset_set_level(spel_sub, 3, bp%begl, keep(lun_pp%gridcell(bp%begl:bp%endl)))
    call nc_subset_set_level(spel_sub, 4, bp%begc, keep(col_pp%gridcell(bp%begc:bp%endc)))
    call nc_subset_set_level(spel_sub, 5, bp%begp, keep(veg_pp%gridcell(bp%begp:bp%endp)))
    spel_sub%mask = {mask}
    spel_sub%gindex = pack(grc_pp%gindex(bp%begg:bp%endg), keep)
    spel_sub%latdeg = pack(grc_pp%latdeg(bp%begg:bp%endg), keep)
    spel_sub%londeg = pack(grc_pp%londeg(bp%begg:bp%endg), keep)

    spel_bounds_sub = bounds
    spel_bounds_sub%begg = 1; spel_bounds_sub%endg = nc_subset_count(spel_sub, 1)
    spel_bounds_sub%begt = 1; spel_bounds_sub%endt = nc_subset_count(spel_sub, 2)
    spel_bounds_sub%begl = 1; spel_bounds_sub%endl = nc_subset_count(spel_sub, 3)
    spel_bounds_sub%begc = 1; spel_bounds_sub%endc = nc_subset_count(spel_sub, 4)
    spel_bounds_sub%begp = 1; spel_bounds_sub%endp = nc_subset_count(spel_sub, 5)
    print *, 'SPEL subset ({tag}): rank', iam, ' writes', n, ' of', nmatch, ' matching gridcells'
    print *, 'SPEL subset ({tag}): gindex', spel_sub%gindex
  end subroutine spel_select_subset
"""


# --------------------------------------------------------------------------
# Offline subsets of existing captures
# --------------------------------------------------------------------------
SUBGRID_DIMS = {"gridcell": "g", "topo": "t", "landunit": "l", "column": "c", "patch": "p"}
# Parent gridcell of each level in the captured index fields
PARENT_VARS = {"t": "top_pp__gridcell", "l": "lun_pp__gridcell", "c": "col_pp__gridcell", "p": "veg_pp__gridcell"}


def level_keep(structure: Path, gridcells: Sequence[int]) -> dict:
    """
    Kept positions of each level for 1-based `gridcells`, from the index
    fields of a capture (an inputs/outputs file; time step 0).
    """
    import netCDF4
    import numpy as np

    with netCDF4.Dataset(structure) as ds:
        ds.set_auto_mask(False)
        ng = len(ds.dimensions["gridcell"]) if "gridcell" in ds.dimensions else None
        if ng is None:
            raise SubsetError(f"{structure} has no gridcell dimension")
        bad = [g for g in gridcells if not 1 <= g <= ng]
        if bad:
            raise SubsetError(f"gridcells {bad} out of range 1..{ng}")
        keep_g = np.zeros(ng, bool)
        keep_g[np.asarray(gridcells, int) - 1] = True
        begg = int(ds["bounds__begg"][...]) if "bounds__begg" in ds.variables else 1
        keep = {"g": keep_g}
        for dim, lev in SUBGRID_DIMS.items():
            if lev == "g" or dim not in ds.dimensions:
                continue
            var = PARENT_VARS[lev]
            if var in ds.variables:
                parent = np.asarray(ds[var][0] if "time" in ds[var].dimensions else ds[var][...])
                keep[lev] = keep_g[parent - begg]
            elif lev == "t" and len(ds.dimensions[dim]) == ng:
                keep[lev] = keep_g.copy()  # one topounit per gridcell
            else:
                raise SubsetError(f"{structure} has a {dim} dimension but no {var}")
    return keep


def _renumber(values, field: str, lev: str, keep: dict, beg: int):
    import numpy as np

    if field == "gindex":
        return np.broadcast_to(np.arange(1, values.shape[-1] + 1, dtype=values.dtype), values.shape)
    newidx = np.zeros(keep[lev].size, np.int64)
    newidx[keep[lev]] = np.arange(1, keep[lev].sum() + 1)
    v = values.astype(np.int64)
    k = v - beg
    inside = (k >= 0) & (k < keep[lev].size)
    new = np.where(inside, newidx[np.clip(k, 0, keep[lev].size - 1)], 0)
    out = np.where(inside, np.where(new > 0, new, -9999), v)
    return out.astype(values.dtype)


def subset_dataset(src: Path, dst: Path, keep: dict, mask: str = "", gindex=None) -> None:
    """Write the kept gridcells of capture file `src` to `dst`, as nc_io does in ELM."""
    import netCDF4
    import numpy as np

    from spel.scripts.io.netcdf_io import index_field_levels

    fields = index_field_levels()
    counts = {lev: int(k.sum()) for lev, k in keep.items()}
    with netCDF4.Dataset(src) as si, netCDF4.Dataset(dst, "w", format=si.data_model) as so:
        si.set_auto_mask(False)
        so.set_auto_mask(False)
        begs = {
            lev: int(si[f"bounds__beg{lev}"][...]) if f"bounds__beg{lev}" in si.variables else 1
            for lev in keep
        }
        so.setncatts({a: si.getncattr(a) for a in si.ncattrs()})
        so.setncattr("spel_subset_mask", mask)
        so.setncattr("spel_subset_gindex", np.asarray(gindex if gindex is not None else
                                                      np.flatnonzero(keep["g"]) + 1, np.int32))
        for name, dim in si.dimensions.items():
            lev = SUBGRID_DIMS.get(name)
            if dim.isunlimited():
                so.createDimension(name, None)
            elif lev is not None:
                if len(dim) != keep[lev].size:
                    raise SubsetError(f"{src}: {name} has {len(dim)} entries, structure has {keep[lev].size}")
                so.createDimension(name, counts[lev])
            else:
                so.createDimension(name, len(dim))
        for name, vi in si.variables.items():
            attrs = {a: vi.getncattr(a) for a in vi.ncattrs()}
            fill = attrs.pop("_FillValue", None)
            vo = so.createVariable(name, vi.datatype, vi.dimensions, fill_value=fill)
            data = vi[...]
            axes = [i for i, d in enumerate(vi.dimensions) if d in SUBGRID_DIMS]
            if axes:
                ax = axes[-1]  # netCDF order is reversed: the first Fortran subgrid dim
                lev = SUBGRID_DIMS[vi.dimensions[ax]]
                data = np.compress(keep[lev], data, axis=ax)
                fdims = [d for d in vi.dimensions if d != "time"][::-1]
                fi = fdims.index(vi.dimensions[ax])
                for key, val in (("lbounds", 1), ("ubounds", counts[lev])):
                    if key in attrs:
                        b = np.array(attrs[key], ndmin=1).copy()
                        b[fi] = val
                        attrs[key] = b
            if (m := re.fullmatch(r"bounds__(beg|end)([gtlcp])", name)) and m.group(2) in counts:
                data = np.asarray(1 if m.group(1) == "beg" else counts[m.group(2)], vi.dtype)
            i = name.rfind("_pp__")
            if i >= 0 and name[i + 5:] in fields:
                lev = fields[name[i + 5:]]
                data = _renumber(np.asarray(data), name[i + 5:], lev, keep, begs[lev])
            vo.setncatts(attrs)
            vo[...] = data


def subset_files(src_dir: Path, dst_dir: Path, gridcells: Sequence[int], mask: str = "") -> list[Path]:
    """Subset every spel-*.nc capture in src_dir to the 1-based `gridcells`."""
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    files = sorted(src_dir.glob("spel-*.nc"))
    structure = next((f for f in files if not f.name.startswith("spel-constants")), None)
    if structure is None:
        raise SubsetError(f"no spel-inputs/outputs*.nc in {src_dir}")
    keep = level_keep(structure, gridcells)
    mask = mask or f"gridcells {','.join(map(str, gridcells))}"
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        subset_dataset(f, dst_dir / f.name, keep, mask=mask, gindex=sorted(gridcells))
        out.append(dst_dir / f.name)
    for extra in ("lnd_in",):
        if (src_dir / extra).is_file():
            shutil.copy2(src_dir / extra, dst_dir / extra)
    return out


def diff_datasets(a: Path, b: Path, ignore_attrs: Sequence[str] = ()) -> list[str]:
    """Differences between two netCDF files (dimensions, variables bit-for-bit, attributes)."""
    import netCDF4
    import numpy as np

    out: list[str] = []
    with netCDF4.Dataset(a) as da, netCDF4.Dataset(b) as db:
        da.set_auto_mask(False)
        db.set_auto_mask(False)
        for name in sorted(set(da.dimensions) | set(db.dimensions)):
            la = len(da.dimensions[name]) if name in da.dimensions else None
            lb = len(db.dimensions[name]) if name in db.dimensions else None
            if la != lb:
                out.append(f"dimension {name}: {la} vs {lb}")
        for att in sorted((set(da.ncattrs()) | set(db.ncattrs())) - set(ignore_attrs)):
            va = da.getncattr(att) if att in da.ncattrs() else None
            vb = db.getncattr(att) if att in db.ncattrs() else None
            if not np.array_equal(np.asarray(va), np.asarray(vb)):
                out.append(f"global attribute {att}: {va} vs {vb}")
        for name in sorted(set(da.variables) | set(db.variables)):
            if name not in da.variables or name not in db.variables:
                out.append(f"variable {name} only in {'b' if name in db.variables else 'a'}")
                continue
            va, vb = da[name], db[name]
            if va.dimensions != vb.dimensions:
                out.append(f"{name}: dimensions {va.dimensions} vs {vb.dimensions}")
                continue
            xa, xb = np.asarray(va[...]), np.asarray(vb[...])
            if xa.dtype != xb.dtype or xa.shape != xb.shape:
                out.append(f"{name}: {xa.dtype}{xa.shape} vs {xb.dtype}{xb.shape}")
            elif xa.tobytes() != xb.tobytes():
                out.append(f"{name}: {int(np.sum(xa != xb))} values differ")
            for att in sorted(set(va.ncattrs()) | set(vb.ncattrs())):
                aa = va.getncattr(att) if att in va.ncattrs() else None
                ab = vb.getncattr(att) if att in vb.ncattrs() else None
                if not np.array_equal(np.asarray(aa), np.asarray(ab)):
                    out.append(f"{name}:{att}: {aa} vs {ab}")
    return out
