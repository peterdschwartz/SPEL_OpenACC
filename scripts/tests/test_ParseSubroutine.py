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


def test_getArguments(subtests):
    """
    Test for parsing function/subroutine calls
    """
    with patch("scripts.mod_config.ELM_SRC", test_dir), patch(
        "scripts.mod_config.SHR_SRC", test_dir
    ):
        import scripts.dynamic_globals as dg
        from scripts.analyze_subroutines import Subroutine
        from scripts.DerivedType import DerivedType
        from scripts.edit_files import process_for_unit_test
        from scripts.fortran_modules import FortranModule
        from scripts.helper_functions import construct_call_tree
        from scripts.mod_config import scripts_dir
        from scripts.variable_analysis import determine_global_variable_status

        expected_arg_status = {
            "test_parsing_sub": {
                "bounds": "r",
                "bounds%begg": "r",
                "bounds%endg": "r",
                "var1": "r",
                "var2": "r",
                "var3": "rw",
                "input4": "rw",
            },
            "add": {
                "x": "r",
                "y": "rw",
            },
            "ptr_test_sub": {
                "numf": "-",
                "soilc": "-",
                "arr": "w",
            },
            "tridiagonal_sr": {
                "bounds": "r",
                "bounds%begc": "r",
                "bounds%endc": "r",
                "lbj": "r",
                "ubj": "r",
                "jtop": "r",
                "numf": "r",
                "filter": "r",
                "a": "r",
                "b": "r",
                "c": "r",
                "r": "r",
                "u": "w",
                "is_col_active": "r",
            },
            "call_sub": {
                "numf": "r",
                "bounds": "r",
                "bounds%begc": "r",
                "bounds%endc": "r",
                "mytype": "w",
                "mytype%field2": "w",
                "mytype%field1": "w",
            },
            "col_nf_init": {
                "begc": "r",
                "endc": "r",
                "this": "w",
                "this%hrv_deadstemn_to_prod100n": "w",
                "this%hrv_deadstemn_to_prod10n": "w",
                "this%m_n_to_litr_lig_fire": "w",
                "this%m_n_to_litr_met_fire": "w",
            },
        }

        dg.populate_interface_list()
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

        determine_global_variable_status(mod_dict, main_sub_dict)

        type_dict: dict[str, DerivedType] = {}
        for mod in mod_dict.values():
            for utype, dtype in mod.defined_types.items():
                type_dict[utype] = dtype

        for dtype in type_dict.values():
            dtype.find_instances(mod_dict)

        instance_to_user_type = {}
        instance_dict: dict[str, DerivedType] = {}
        for type_name, dtype in type_dict.items():
            for instance in dtype.instances.values():
                instance_to_user_type[instance.name] = type_name
                instance_dict[instance.name] = dtype

        active_vars = subroutines[test_sub_name].active_global_vars

        assert (
            len(active_vars) == 2
        ), f"Didn't correctly find the active global variables:\n{active_vars}"

        for s in sub_name_list:
            sub = subroutines[s]
            sub.parse_subroutine(
                dtype_dict=type_dict,
                main_sub_dict=main_sub_dict,
                verbose=True,
            )
            flat_list = construct_call_tree(
                sub=sub,
                sub_dict=main_sub_dict,
                dtype_dict=type_dict,
                nested=0,
            )

            if sub.abstract_call_tree:
                for tree in sub.abstract_call_tree.traverse_postorder():
                    subname = tree.node.subname
                    childsub = main_sub_dict[subname]
                    if not childsub.args_analyzed:
                        childsub.parse_arguments(main_sub_dict, type_dict)
                        test_dict = {
                            k: rw.status
                            for k, rw in childsub.arguments_read_write.items()
                        }
                        with subtests.test(msg=subname):
                            assert expected_arg_status[subname] == test_dict


def test_arg_intent():
    with patch("scripts.mod_config.ELM_SRC", test_dir), patch(
        "scripts.mod_config.SHR_SRC", test_dir
    ):
        import scripts.dynamic_globals as dg
        from scripts.analyze_subroutines import Subroutine
        from scripts.edit_files import process_for_unit_test
        from scripts.fortran_modules import FortranModule, get_module_name_from_file
        from scripts.mod_config import scripts_dir

        dg.populate_interface_list()
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
        print("Sorted mods:\n", [get_module_name_from_file(m) for m in file_list])

        assert 1 == 1
