import cProfile
import pstats
from pprint import pprint

import scripts.dynamic_globals as dg
from scripts.aggregate import aggregate_dtype_vars
from scripts.analyze_subroutines import Subroutine
from scripts.DerivedType import DerivedType
from scripts.edit_files import sort_file_dependency
from scripts.fortran_modules import FortranModule, get_filename_from_module
from scripts.helper_functions import construct_call_tree
from scripts.mod_config import (
    _bc,
    default_mods,
    scripts_dir,
    spel_mods_dir,
    spel_output_dir,
    unittests_dir,
)
from scripts.utilityFunctions import Variable
from scripts.variable_analysis import determine_global_variable_status

ModDict = dict[str, FortranModule]
SubDict = dict[str, Subroutine]
TypeDict = dict[str, DerivedType]


def main() -> None:
    """
    Edit case_dir and sub_name_list to create a Functional Unit Test
    in a directory called {case_dir} for the subroutines in sub_name_list.
    """
    import argparse
    import csv
    import os
    import sys

    import scripts.write_routines as wr
    from scripts.edit_files import process_for_unit_test
    from scripts.export_objects import pickle_unit_test
    from scripts.utilityFunctions import (
        find_file_for_subroutine,
        insert_header_for_unittest,
    )

    # Set up Argument Parser
    desc = (
        " Given input of subroutine names,"
        " SPEL analyzes all dependencies related"
        " to the subroutines"
    )
    parser = argparse.ArgumentParser(prog="SPEL", description=desc)
    parser.add_argument("-u", action="store_true", required=False, dest="keep")
    parser.add_argument("-c", required=False, dest="casename")
    parser.add_argument("-s", nargs="+", required=False, dest="sub_names")
    args = parser.parse_args()

    # Define name of function for logging.
    func_name = "main"

    # Note unittests_dir is a location to make unit tests directories named {casename}
    if args.casename:
        casename = args.casename
    else:
        casename = "fut"

    case_dir = unittests_dir + casename

    if args.sub_names:
        sub_name_list = [s.lower() for s in args.sub_names]
    else:
        sys.exit("Error- No subroutines provided for analysis")

    print(f"Creating UnitTest {casename} || {' '.join(sub_name_list)}")

    # Determines if SPEL should run to make optimizations
    opt = False
    preprocess = False

    # Create script output directory if not present:
    if not os.path.isdir(f"{scripts_dir}/script-output"):
        print("Making script output directory")
        os.system(f"mkdir {scripts_dir}/script-output")

    # Create case directory
    if not os.path.isdir(f"{case_dir}"):
        print(f"Making case directory {case_dir}")
        if not os.path.isdir(f"{unittests_dir}"):
            os.system(f"mkdir {unittests_dir}")
        os.system(f"mkdir {case_dir}")
        preprocess = True
    else:
        # Check if user wants to re-use existing case without preprocessing
        # TODO: Instead, have this section checkout for any pickle or existing
        #       databases and load those. Currently, preprocess is required if not `opt`!
        if args.keep:
            preprocess = False
        else:
            os.system(f"rm -rf {case_dir}/*")
            os.system(f"rm {scripts_dir}/*.pkl")
            preprocess = True

    # Retrieve possible interfaces
    dg.populate_interface_list()
    # Initialize dictionary that will hold instance of all subroutines encountered.
    main_sub_dict: SubDict = {}

    # dictionary holds instances for Unit Test specific subroutines
    sub_name_list: list[str] = [s.lower() for s in sub_name_list]
    subroutines: SubDict = {}

    # List to hold all the modules needed for the unit test
    needed_mods = []
    mod_dict: ModDict = {}
    # Get general info of the subroutine
    # Process files by removing certain modules
    # so that a standalone unit test can be compiled.
    # All file information will be stored in `mod_dict` and `main_sub_dict`
    ordered_mods = process_for_unit_test(
        mod_dict=mod_dict,
        mods=needed_mods,
        required_mods=default_mods,
        sub_dict=main_sub_dict,
        sub_name_list=sub_name_list,
        overwrite=True,
        verbose=False,
    )

    for s in sub_name_list:
        subroutines[s] = main_sub_dict[s]
        subroutines[s].unit_test_function = True

    if not mod_dict or not ordered_mods:
        print(f"{func_name}::Error didn't find any modules related to subroutines")
        sys.exit(1)

    type_dict: TypeDict = {}
    for mod in mod_dict.values():
        for utype, dtype in mod.defined_types.items():
            type_dict[utype] = dtype

    for dtype in type_dict.values():
        dtype.find_instances(mod_dict)

    bounds_inst = Variable(type="bounds_type", name="bounds", dim=0, subgrid="?", ln=-1)
    type_dict["bounds_type"].instances["bounds"] = bounds_inst.copy()

    instance_to_user_type: dict[str, str] = {}
    for type_name, dtype in type_dict.items():
        if "bounds" in type_name:
            continue
        # All instances should have been found so throw an error
        if not dtype.instances:
            print(
                _bc.WARNING + f"Warning: no instances found for {type_name}" + _bc.ENDC
            )
        for instance in dtype.instances.values():
            instance_to_user_type[instance.name] = type_name

    process_subroutines_for_unit_test(
        mod_dict=mod_dict,
        sub_dict=main_sub_dict,
        type_dict=type_dict,
    )

    aggregate_dtype_vars(
        sub_dict=main_sub_dict,
        type_dict=type_dict,
        inst_to_dtype_map=instance_to_user_type,
    )

    instance_dict: dict[str, DerivedType] = {}
    for type_name, dtype in type_dict.items():
        for instance in dtype.instances.values():
            instance_dict[instance.name] = dtype

    active_set: set[str] = set()
    for inst_name, dtype in instance_dict.items():
        if not dtype.instances[inst_name].active:
            continue
        for field_var in dtype.components.values():
            if field_var.active:
                active_set.add(f"{inst_name}%{field_var.name}")

    print("=================== ACTIVE ELMTYPES ==================")
    pprint(sorted(active_set))
    for sub in subroutines.values():
        for key in list(sub.elmtype_access_sum.keys()):
            c13c14 = bool("c13" in key or "c14" in key)
            if c13c14:
                del sub.elmtype_access_sum[key]
                continue

    # Create a makefile for the unit test
    file_list = [get_filename_from_module(m) for m in ordered_mods]
    wr.generate_makefile(files=file_list, case_dir=case_dir)

    # Make sure physical properties types are read/written:
    set_pp = {"veg_pp", "lun_pp", "col_pp", "grc_pp", "top_pp"}

    aggregated_elmtypes_list = {v.split("%")[0] for v in active_set}

    # Will need to read in physical properties type
    # so set all components to True
    for type_name, dtype in type_dict.items():
        for var in dtype.instances.values():
            if var.name in set_pp:
                dtype.active = True
                var.active = True
                for field_var in dtype.components.values():
                    field_var.active = True

    print(f"Call Tree for {case_dir}")
    for sub in subroutines.values():
        if sub.abstract_call_tree:
            sub.abstract_call_tree.print_tree()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                        VERIFICATION MODULE                                #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Generate modules to output results from unit-test for validation purposes.
    # Call the relevant update_vars_{sub} after the parallel region.

    elmvars_dict = {}
    for dtype in type_dict.values():
        for inst in dtype.instances.values():
            elmvars_dict[inst.name] = inst

    # create list of variables that should be used for verification.
    # Will go ahead and use all variables for now but can limit to just w,rw
    # to save memory if needed.
    for sub in subroutines.values():
        verify_vars = {}
        total_vars = []
        total_vars.extend(sub.elmtype_access_sum.keys())
        for var in total_vars:
            if "bounds" in var or var in instance_to_user_type:
                continue
            dtype, component = var.split("%")
            verify_vars.setdefault(dtype, []).append(component)

        sub.generate_update_directives(elmvars_dict, verify_vars)

    with open(f"{scripts_dir}/script-output/concat.F90", "w") as outfile:
        outfile.write("module verificationMod \n")
        outfile.write("contains \n")

        for s in sub_name_list:
            with open(f"{scripts_dir}/script-output/update_vars_{s}.F90") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
        outfile.write("end module verificationMod\n")

    cmd = f"cp {scripts_dir}/script-output/concat.F90 {case_dir}/verificationMod.F90"
    os.system(cmd)

    # Print and Write stencil for acc directives to screen to be c/p'ed in main.F90
    # may be worth editing main.F90 directly.
    aggregated_elmtypes_list = sorted(aggregated_elmtypes_list)
    acc = _bc.BOLD + _bc.HEADER + "!$acc "
    endc = _bc.ENDC
    print(acc + "enter data copyin( &" + endc)
    with open(f"{case_dir}/global_data_types.txt", "w") as ofile:
        for el in aggregated_elmtypes_list:
            ofile.write(el)
    i = 0
    for el in aggregated_elmtypes_list:
        i += 1
        if i == len(aggregated_elmtypes_list):
            print(acc + el + "      &" + endc)
        else:
            print(acc + el + "     , &" + endc)
    print(acc + "  )" + endc)

    unittest_global_vars: dict[str, Variable] = {}
    for sub in main_sub_dict.values():
        unittest_global_vars.update(sub.active_global_vars)

    # Generate/modify FORTRAN files needed to initialize and run Unit Test
    wr.prepare_unit_test_files(
        inst_list=aggregated_elmtypes_list,
        type_dict=type_dict,
        files=needed_mods,
        case_dir=case_dir,
        global_vars=unittest_global_vars,
        subroutines=subroutines,
        instance_to_type=instance_to_user_type,
    )
    # elm_instMod.F90
    wr.write_elminstMod(type_dict, case_dir)
    # duplicateMod.F90
    wr.duplicate_clumps(type_dict)
    # readMod.F90
    wr.create_read_vars(type_dict)
    # writeMod.F90
    wr.create_write_vars(type_dict, casename, use_isotopes=False)

    # Go through all needed files and include a header that defines some constants
    insert_header_for_unittest(
        file_list=needed_mods, casedir=case_dir, mod_dict=mod_dict
    )
    cmd = (
        f"cp {spel_output_dir}duplicateMod.F90 "
        + f"{spel_output_dir}readMod.F90 {spel_output_dir}writeMod.F90 {case_dir}"
    )
    os.system(cmd)
    os.system(f"cp {spel_mods_dir}fileio_mod.F90 {case_dir}")
    os.system(f"cp {spel_mods_dir}unittest_defs.h {case_dir}")
    os.system(f"cp {spel_mods_dir}decompInitMod.F90 {case_dir}")

    pickle_unit_test(mod_dict, main_sub_dict, type_dict)

    return None


def process_subroutines_for_unit_test(
    mod_dict: ModDict,
    sub_dict: SubDict,
    type_dict: TypeDict,
):

    fut_subs: set[str] = {
        sub.name for sub in sub_dict.values() if sub.unit_test_function
    }

    for sub in sub_dict.values():
        determine_global_variable_status(mod_dict, sub)

    for sub_name in fut_subs:
        sub = sub_dict[sub_name]
        sub.collect_var_and_call_info(
            dtype_dict=type_dict,
            sub_dict=sub_dict,
            verbose=False,
        )
        flat_list = construct_call_tree(
            sub=sub,
            sub_dict=sub_dict,
            dtype_dict=type_dict,
            nested=0,
        )

        if sub.abstract_call_tree:
            sub.abstract_call_tree.print_tree()
            for tree in sub.abstract_call_tree.traverse_postorder():
                subname = tree.node.subname
                childsub = sub_dict[subname]
                if childsub.library:
                    continue
                if not childsub.args_analyzed:
                    childsub.parse_arguments(sub_dict, type_dict)
                if not childsub.global_analyzed:
                    childsub.analyze_variables(sub_dict, type_dict)

    for sub in sub_dict.values():
        sub.match_arg_to_inst(type_dict)

    for sub in sub_dict.values():
        if sub.elmtype_access_by_ln:
            sub.summarize_readwrite()

    return


if __name__ == "__main__":
    main()
