"""
These tests similar to those in test_ParseSubroutine but they 
act the ELM source code itself and not examples
"""

from pprint import pprint

from scripts.utilityFunctions import find_file_for_subroutine


def test_info_SoilTemp():
    import scripts.dynamic_globals as dg
    from scripts.analyze_subroutines import Subroutine
    from scripts.DerivedType import DerivedType
    from scripts.edit_files import process_for_unit_test
    from scripts.fortran_modules import FortranModule
    from scripts.helper_functions import construct_call_tree
    from scripts.variable_analysis import determine_global_variable_status

    dg.populate_interface_list()
    sub_name = "LakeTemperature"
    mod_dict: dict[str, FortranModule] = {}
    main_sub_dict: dict[str, Subroutine] = {}

    fn, startl, endl = find_file_for_subroutine(sub_name)

    file_list = process_for_unit_test(
        fname=fn,
        case_dir="./",
        mod_dict=mod_dict,
        mods=[],
        required_mods=[],
        sub_dict=main_sub_dict,
        overwrite=True,
        verbose=False,
    )
    test_sub_name = sub_name

    sub_name_list = [test_sub_name]
    subroutines: dict[str, Subroutine] = {s: main_sub_dict[s] for s in sub_name_list}

    determine_global_variable_status(mod_dict, subroutines)

    type_dict: dict[str, DerivedType] = {}
    for mod in mod_dict.values():
        for utype, dtype in mod.defined_types.items():
            type_dict[utype] = dtype

        instance_to_user_type = {}
        instance_dict: dict[str, DerivedType] = {}
        for type_name, dtype in type_dict.items():
            for instance in dtype.instances.values():
                instance_to_user_type[instance.name] = type_name
                instance_dict[instance.name] = dtype

        active_vars = subroutines[test_sub_name].active_global_vars
        pprint(active_vars)

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
                sub.abstract_call_tree.print_tree()
                # for node in sub.abstract_call_tree.traverse_postorder():
                #     print(node)
