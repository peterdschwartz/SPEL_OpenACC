"""Pickling of a FunctionalUnitTest (the CSV export lives in spel.scripts.db_export)."""

import pickle
import shutil
from itertools import chain
from typing import Optional
from pathlib import Path

from spel.scripts.analyze_subroutines import Subroutine
from spel.scripts.config import E3SM_SRCROOT, scripts_dir
from spel.scripts.DerivedType import DerivedType
from spel.scripts.fortran_modules import FortranModule
from spel.scripts.functional_unit_test import FunctionalUnitTest


def _fut_objects(fut: FunctionalUnitTest):
    return chain(
        fut.module_dict.values(),
        fut.subroutine_dict.values(),
        fut.type_dict.values(),
    )


CASE_PICKLE = "fut.pkl"


def pickle_unit_test(fut: FunctionalUnitTest) -> None:
    """
    Serialize a FunctionalUnitTest to spel/scripts/fut_<case>.pkl (export,
    database) and <case_dir>/fut.pkl (`spel instrument`, survives other creates).
    """
    output_path = Path(scripts_dir) / f"fut_{fut.case_name}.pkl"
    # Case copy first: a concurrent `spel create` may clear scripts_dir/*.pkl
    if Path(fut.case_dir).is_dir():
        dump_unit_test(fut, Path(fut.case_dir) / CASE_PICKLE)
        shutil.copyfile(Path(fut.case_dir) / CASE_PICKLE, output_path)
    else:
        dump_unit_test(fut, output_path)


def dump_unit_test(fut: FunctionalUnitTest, output_path: Path) -> None:
    """Pickle `fut` with source paths relative to E3SM_SRCROOT (see _load_pickle)."""
    objects = list(_fut_objects(fut))
    original_paths = [obj.filepath for obj in objects]

    try:
        for obj in objects:
            path = Path(obj.filepath)
            # paths outside the source tree (e.g. libraries) stay absolute;
            # _load_pickle's `E3SM_SRCROOT / path` leaves them unchanged.
            if path.is_relative_to(E3SM_SRCROOT):
                path = path.relative_to(E3SM_SRCROOT)
            obj.filepath = path

        with output_path.open("wb") as dbfile:
            pickle.dump(fut, dbfile)
    finally:
        for obj, filepath in zip(objects, original_paths):
            obj.filepath = filepath


def unpickle_unit_test(casename: str) -> FunctionalUnitTest:
    """
    Function to load SPEL's output from pickled files.
    """
    return _load_pickle(Path(scripts_dir) / f"fut_{casename}.pkl")


def unpickle_case(case_dir: Path) -> FunctionalUnitTest:
    """Load the FunctionalUnitTest `spel create` stored in a case directory."""
    return _load_pickle(Path(case_dir) / CASE_PICKLE)


def _load_pickle(input_path: Path, srcroot: Optional[Path] = None) -> FunctionalUnitTest:
    """
    Load a pickle written by dump_unit_test, re-anchoring source paths to
    `srcroot` (default: the configured E3SM_SRCROOT).
    """
    root = Path(srcroot) if srcroot is not None else E3SM_SRCROOT
    with input_path.open("rb") as dbfile:
        fut: FunctionalUnitTest = pickle.load(dbfile)

    for obj in _fut_objects(fut):
        obj.filepath = root / obj.filepath

    return fut
