import re
import unittest

import utilityFunctions as uf
from analyze_subroutines import Subroutine
from edit_files import get_filename_from_module, get_used_mods
from mod_config import E3SM_SRCROOT


class SubroutineTests(unittest.TestCase):
    """
    Tests to exercise the Subroutine class methods.
    NOTE: Hardcoding answers may be difficult if E3SM version
          is changed.
          Storing copy of files, may not allow testing of E3SM's directory structure.
          Sol'n:  store the commit hash the tests were validated against?
    """

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
