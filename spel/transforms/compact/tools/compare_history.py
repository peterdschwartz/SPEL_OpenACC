"""
Compare the ELM history files of two run directories, variable by variable.

    python compare_history.py BASE_RUNDIR TEST_RUNDIR

Files are matched by the part of the name after `.elm.` (h0/h1 and date).
Prints, per file, how many numeric variables differ (bit-for-bit, NaN = NaN)
and the largest absolute and relative difference of each that does. Exit
status 1 if any variable differs or a file is missing.
"""

import sys
from pathlib import Path

import netCDF4
import numpy as np

SKIP = {"date_written", "time_written"}


def main(base: Path, test: Path) -> int:
    files = sorted(base.glob("*.elm.h*.nc"))
    if not files:
        print(f"no history files in {base}")
        return 1
    bad = 0
    for bf in files:
        suffix = bf.name.split(".elm.", 1)[1]
        tf = next(test.glob(f"*.elm.{suffix}"), None)
        if tf is None:
            print(f"{bf.name}: missing in {test}")
            bad += 1
            continue
        a, b = netCDF4.Dataset(bf), netCDF4.Dataset(tf)
        nvar = ndiff = 0
        for v in a.variables:
            if v in SKIP or v not in b.variables:
                continue
            x, y = np.asarray(a[v][:]), np.asarray(b[v][:])
            if x.dtype.kind not in "fi":
                continue
            nvar += 1
            if x.shape == y.shape and np.array_equal(x, y, equal_nan=True):
                continue
            ndiff += 1
            if x.shape != y.shape:
                print(f"  {v}: shape {x.shape} vs {y.shape}")
                continue
            d = np.abs(x.astype(float) - y.astype(float))
            scale = np.maximum(np.abs(x.astype(float)), 1e-300)
            print(f"  {v}: max |diff| {np.nanmax(d):.3e}, max rel {np.nanmax(d / scale):.3e}")
        print(f"{bf.name} vs {tf.name}: {nvar} variables, {ndiff} differ")
        bad += ndiff
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
