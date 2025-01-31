import os
from pprint import pprint
from typing import Dict
from unittest.mock import patch

import pytest

test_dir = os.path.dirname(__file__)


def test_Functions():
    """
    Test for parsing functions
    """
    with patch("scripts.mod_config.ELM_SRC", test_dir), patch(
        "scripts.mod_config.SHR_SRC", test_dir
    ):
        from scripts.analyze_subroutines import Subroutine
        from scripts.edit_files import modify_file
        from scripts.mod_config import scripts_dir
        from scripts.utilityFunctions import Variable

        fn = f"{scripts_dir}/tests/example_functions.f90"

        SUB_NAME_DICT = {
            "landunit_is_special": Variable(
                type="logical", name="is_special", dim=0, subgrid="?", ln=-1
            ),
            "constructor": Variable(
                type="prior_weights_type", name="constructor", dim=0, subgrid="?", ln=-1
            ),
            "old_weight_was_zero": Variable(
                type="logical", name="old_weight_was_zero", dim=1, subgrid="?", ln=-1
            ),
            "cnallocate_carbon_only": Variable(
                type="logical", name="cnallocate_carbon_only", dim=0, subgrid="?", ln=-1
            ),
            "get_beg": Variable(
                type="integer", name="beg_index", dim=0, subgrid="?", ln=-1
            ),
        }

        with open(fn, "r") as ifile:
            lines = ifile.readlines()

        sub_dict = modify_file(lines, fn, sub_dict={}, verbose=False, overwrite=False)

        for key, ans in SUB_NAME_DICT.items():
            func: Subroutine = sub_dict[key]
            if func.func:
                func.print_subroutine_info()
                comp = func.result
                assert ans == comp, f"Failed for function: {key}"


def test_getArguments():
    """
    Test for parsing function/subroutine calls
    """
    with patch("scripts.mod_config.ELM_SRC", test_dir), patch(
        "scripts.mod_config.SHR_SRC", test_dir
    ):
        from scripts.analyze_subroutines import Subroutine
        from scripts.DerivedType import DerivedType
        from scripts.edit_files import process_for_unit_test
        from scripts.fortran_modules import FortranModule
        from scripts.mod_config import scripts_dir
        from scripts.variable_analysis import determine_global_variable_status

        fn = f"{scripts_dir}/tests/example_functions.f90"
        mod_dict: dict[str, FortranModule] = {}
        main_sub_dict: dict[str, Subroutine] = {}

        mod_dict, file_list, main_sub_dict = process_for_unit_test(
            fname=fn,
            case_dir="./",
            mod_dict=mod_dict,
            mods=[],
            required_mods=[],
            main_sub_dict=main_sub_dict,
            overwrite=False,
            verbose=False,
        )
        test_sub_name = "call_sub"

        sub_name_list = [test_sub_name]
        subroutines: dict[str, Subroutine] = {
            s: main_sub_dict[s] for s in sub_name_list
        }

        determine_global_variable_status(mod_dict, subroutines)

        type_dict: dict[str, DerivedType] = {}
        for mod in mod_dict.values():
            for utype, dtype in mod.defined_types.items():
                type_dict[utype] = dtype

        instance_to_user_type = {}
        instance_dict: dict[str, DerivedType] = {}
        for type_name, dtype in type_dict.items():
            if "bounds" in type_name:
                continue
            for instance in dtype.instances.values():
                instance_to_user_type[instance.name] = type_name
                instance_dict[instance.name] = dtype

        active_vars = subroutines[test_sub_name].active_global_vars

        subroutines[test_sub_name].get_dtype_vars(instance_dict)

        assert (
            len(active_vars) == 1
        ), f"Didn't correctly find the active global variables:\n{active_vars}"

        for s in sub_name_list:
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
