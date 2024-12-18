import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import utilityFunctions as uf
from analyze_subroutines import Subroutine
from edit_files import get_filename_from_module, modify_file
from mod_config import E3SM_SRCROOT, scripts_dir


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
        num_subs = len(sub_dict.keys())
        self.assertEqual(num_subs, NUM_SUBS)
        for key, ans in SUB_NAME_DICT.items():
            sub_dict[key].print_subroutine_info()
            comp = sub_dict[key].result
            with self.subTest(ans=ans):
                self.assertEqual(ans, comp)

    def test_getArguments(self):

        func_calls = [
            "call sub1__test (var(i,:), var_2 (isoilorder (c) , j), veg%member(bounds%begc:bounds%endc,isoil (c) ) )"
        ]
        func_1 = func_calls[0]
        args = uf.getArguments(func_1)
        ans1 = ["var", "var_2", "veg%member"]
        self.assertListEqual(args, ans1)

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
