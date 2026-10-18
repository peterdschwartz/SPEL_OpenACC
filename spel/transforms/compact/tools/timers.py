"""
Pull GPTL timers out of E3SM timing files and compare cases.

    python timers.py CASEDIR [CASEDIR ...] [--timers CNZero CNPsum ...]

Reads the newest CASEDIR/timing/e3sm_timing_stats.* (gzipped or not) and
prints, per timer, count and wallmax / wallmin (seconds, max / min over MPI
tasks) for every case, plus the ratio of wallmax to the first case's.
"""

import argparse
import gzip
import re
from pathlib import Path

DEFAULT = [
    "elm_run", "ecosysdyn", "CNZero", "CNZero-veg_cf", "CNZero-veg_nf", "CNZero-veg_pf",
    "CNZero-col_cf", "CNZero-col_nf", "CNZero-col_pf", "CNPsum", "SoilLittDecompAlloc",
    "compact_unpack", "hbuf",
]
ROW = re.compile(
    r'^"(?P<name>[^"]+)"\s+\S+\s+(?P<procs>\d+)\s+(?P<thrds>\d+)\s+(?P<count>\S+)\s+(?P<total>\S+)'
    r"\s+(?P<max>\S+)\s+\(\s*\d+\s+\d+\s*\)\s+(?P<min>\S+)"
)


def stats(case: Path) -> dict[str, dict[str, float]]:
    files = sorted((case / "timing").glob("e3sm_timing_stats.*"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f"{case}: no timing/e3sm_timing_stats.*")
    path = files[-1]
    text = gzip.open(path, "rt").read() if path.suffix == ".gz" else path.read_text()
    out = {}
    for line in text.splitlines():
        if m := ROW.match(line.strip()):
            name = m["name"].removeprefix("l:")
            out.setdefault(name, {k: float(m[k]) for k in ("count", "max", "min")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="+", type=Path)
    ap.add_argument("--timers", nargs="+", default=DEFAULT)
    args = ap.parse_args()
    all_stats = [stats(c) for c in args.cases]
    print(f"{'timer':22s}" + "".join(f"{c.name[-28:]:>32s}" for c in args.cases))
    for t in args.timers:
        cells = []
        base = all_stats[0].get(t, {}).get("max")
        for s in all_stats:
            if t not in s:
                cells.append(f"{'-':>32s}")
                continue
            r = f" ({s[t]['max'] / base:.2f}x)" if base else ""
            cells.append(f"{s[t]['max']:10.3f} / {s[t]['min']:8.3f}{r:>10s}".rjust(32))
        print(f"{t:22s}" + "".join(cells))
    print("cells: wallmax / wallmin over MPI tasks (s); ratio: wallmax vs the first case")


if __name__ == "__main__":
    main()
