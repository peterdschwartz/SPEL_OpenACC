import re
import unittest

from analyze_subroutines import Subroutine
from edit_files import get_filename_from_module, get_used_mods


class SubroutineTests(unittest.TestCase):
    """
    Tests to exercise the Subroutine class methods.
    NOTE: Hardcoding answers may be difficult if E3SM version
          is changed.
          Storing copy of files, may not allow testing of E3SM's directory structure.
          Sol'n:  store the commit hash the tests were validated against?
    """

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
        file_path = get_filename_from_module(module_name)
        correct_filepath = "E3SM/share/util/shr_kind_mod.F90"
        regex_fp = re.compile(f"({correct_filepath})")
        self.assertRegex(file_path, regex_fp)

        # Next attempt to parse the file for used modules, variables, subroutines, etc...
        mods = []
        mod_dict = {}
        singlefile = False

        mods, mod_dict = get_used_mods(
            ifile=file_path,
            mods=mods,
            verbose=False,
            singlefile=singlefile,
            mod_dict=mod_dict,
        )
        # No module depencies for shr_kind_mod
        self.assertListEqual(mods, [])
        # Mod dict should only contain shr_kind_mod
        key_list = [key for key in mod_dict.keys()]
        self.assertListEqual(key_list, ["shr_kind_mod"])
        # Check variables in module:
        correct_var_list = [
            "SHR_KIND_R8",
            "SHR_KIND_R4",
            "SHR_KIND_RN",
            "SHR_KIND_I8",
            "SHR_KIND_I4",
            "SHR_KIND_I2",
            "SHR_KIND_IN",
            "SHR_KIND_CS",
            "SHR_KIND_CM",
            "SHR_KIND_CL",
            "SHR_KIND_CX",
            "SHR_KIND_CXX",
        ]
        correct_var_list = [x.lower() for x in correct_var_list]
        var_list = [x.name for x in mod_dict["shr_kind_mod"].global_vars]
        self.assertListEqual(var_list, correct_var_list)


if __name__ == "__main__":
    import os

    print(os.getcwd())
    unittest.main()
