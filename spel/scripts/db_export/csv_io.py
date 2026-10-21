"""CSV writing/reading for the export directory (stdlib csv, one file per table)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Iterable

from spel.scripts.db_export.schema import TABLES


def cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def write_table(out_dir: Path, name: str, rows: Iterable[dict]) -> int:
    """Write `rows` (dicts keyed by column) as `<out_dir>/<name>.csv`; returns the row count."""
    columns = TABLES[name]
    n = 0
    with (Path(out_dir) / f"{name}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for row in rows:
            extra = set(row) - set(columns)
            if extra:
                raise KeyError(f"{name}: unknown columns {sorted(extra)}")
            w.writerow([cell(row.get(c)) for c in columns])
            n += 1
    return n


def read_table(path: Path) -> list[dict[str, str]]:
    """Rows of a CSV written by write_table; the header must match TABLES."""
    csv.field_size_limit(sys.maxsize)  # subroutine_code.text can exceed the 128 KB default
    name = Path(path).stem
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != TABLES[name]:
            raise ValueError(
                f"{path}: columns {reader.fieldnames} do not match schema {TABLES[name]}"
            )
        return list(reader)
