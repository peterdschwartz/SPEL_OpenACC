import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import utilityFunctions as uf
from DerivedType import DerivedType
from edit_files import get_used_mods
from mod_config import scripts_dir


class DerivedTypeTests(unittest.TestCase):

    def test_type_bound_methods(self):
        fn = f"{scripts_dir}/tests/example_types.f90"

        TYPE_PROCS = {
            "column_nitrogen_flux": {
                "init": "col_nf_init",
                "setvalues": "col_nf_setvalues",
                "type_stuff": "type_stuff",
            }
        }

        mod_dict = {}
        mods, mod_dict = get_used_mods(
            ifile=fn,
            mods=[],
            verbose=False,
            singlefile=False,
            mod_dict=mod_dict,
        )

        print("mod_dict:", mod_dict)

        type_dict: dict[str, DerivedType] = {}
        for mod in mod_dict.values():
            for utype, dtype in mod.defined_types.items():
                type_dict[utype] = dtype

        for key, dtype in type_dict.items():
            comp = dtype.procedures
            with self.subTest(key=key):
                self.assertDictEqual(TYPE_PROCS[key], comp)


if __name__ == "__main__":
    unittest.main()
