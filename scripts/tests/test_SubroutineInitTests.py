import os
import re
import sys
import unittest
from typing import Dict

#sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
import scripts.utilityFunctions as uf
from scripts.analyze_subroutines import Subroutine
from scripts.DerivedType import DerivedType
from scripts.edit_files import (get_filename_from_module, modify_file,
                                process_for_unit_test)
from scripts.mod_config import E3SM_SRCROOT, scripts_dir


class SubroutineTests(unittest.TestCase):
    """
    Tests to exercise the Subroutine class methods.
    NOTE: Hardcoding answers may be difficult if E3SM version is changed.
          Storing copy of files, may not allow testing of E3SM's directory structure.
          Sol'n:  store the commit hash the tests were validated against?
    """

    def test_CallTree(self):
        """
        unit-test for call tree
        """

    def test_Functions(self):

        fn = f"{scripts_dir}/tests/example_functions.f90"

        SUB_NAME_DICT = {
            "landunit_is_special": uf.Variable(
                type="logical",
                name="is_special",
                dim=0,
                subgrid="?",
                ln=-1,
            ),
            "constructor": uf.Variable(
                type="prior_weights_type",
                name="constructor",
                dim=0,
                subgrid="?",
                ln=-1,
            ),
            "old_weight_was_zero": uf.Variable(
                type="logical",
                name="old_weight_was_zero",
                dim=1,
                subgrid="?",
                ln=-1,
            ),
            "cnallocate_carbon_only": uf.Variable(
                type="logical",
                name="cnallocate_carbon_only",
                dim=0,
                subgrid="?",
                ln=-1,
            ),
            "get_beg": uf.Variable(
                type="integer",
                name="beg_index",
                dim=0,
                subgrid="?",
                ln=-1,
            ),
        }

        NUM_SUBS = len(SUB_NAME_DICT.keys())
        ifile = open(fn, "r")
        lines = ifile.readlines()
        ifile.close()
        sub_dict = {}
        sub_dict = modify_file(
            lines,
            fn,
            sub_dict,
            verbose=False,
            overwrite=False,
        )
        for key, ans in SUB_NAME_DICT.items():
            func: Subroutine = sub_dict[key]
            if func.func:
                sub_dict[key].print_subroutine_info()
                comp = sub_dict[key].result
                with self.subTest(ans=ans):
                    self.assertEqual(ans, comp)

    def test_getArguments(self):

        fn = f"{scripts_dir}/tests/example_functions.f90"
        mod_dict = {}
        main_sub_dict = {}

        mod_dict, file_list, main_sub_dict = process_for_unit_test(
            fname=fn,
            case_dir="./",
            mod_dict=mod_dict,
            mods=[],
            required_mods=[],
            main_sub_dict=main_sub_dict,
            overwrite=True,
            verbose=False,
        )

        sub_name_list = ["call_sub"]
        subroutines: Dict[str, Subroutine] = {
            s: main_sub_dict[s] for s in sub_name_list
        }

        type_dict: Dict[str, DerivedType] = {}
        for mod in mod_dict.values():
            for utype, dtype in mod.defined_types.items():
                type_dict[utype] = dtype

        instance_to_user_type = {}
        for type_name, dtype in type_dict.items():
            if "bounds" in type_name:
                continue
            for instance in dtype.instances.values():
                instance_to_user_type[instance.name] = type_name

        for s in sub_name_list:
            #
            # Parsing means getting info on the variables read and written
            # to by the subroutine and any of its callees
            #
            subroutines[s].parse_subroutine(
                dtype_dict=type_dict,
                main_sub_dict=main_sub_dict,
                verbose=False,
            )

            subroutines[s].child_subroutines_analysis(
                dtype_dict=type_dict,
                main_sub_dict=main_sub_dict,
                verbose=False,
            )

        self.assertListEqual([], [1])

    def test_get_subroutine_file(self):
        sname = "SoilTemperature"
        # Initilize Subroutine
        s = Subroutine(sname, calltree=["elm_drv"])
        correct_filepath = "E3SM/components/elm/src/biogeophys/SoilTemperatureMod.F90"
        regex_fp = re.compile(f"({correct_filepath})$")
        self.assertRegex(s.filepath, regex_fp)

    def test_parse_modules_simple(self):
        """
        Test to verfiy that modules are parsed correctly
        """
        module_name = "shr_kind_mod"
        file_path = get_filename_from_module(module_name, verbose=True)
        correct_filepath = "/share/util/shr_kind_mod.F90"
        file_path = file_path.replace(E3SM_SRCROOT, "")
        self.assertEqual(file_path, correct_filepath)


if __name__ == "__main__":
    import os

    print(os.getcwd())
    unittest.main()
