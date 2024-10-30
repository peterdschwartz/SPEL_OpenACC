from DerivedType import DerivedType
from helper_functions import replace_ptr_with_targets


def main() -> None:
    """
    Edit case_dir and sub_name_list to create a Functional Unit Test
    in a directory called {case_dir} for the subroutines in sub_name_list.
    """
    import argparse
    import csv
    import os
    import sys

    import write_routines as wr
    from analyze_subroutines import Subroutine
    from edit_files import process_for_unit_test
    from export_objects import pickle_unit_test
    from fortran_modules import FortranModule
    from mod_config import (
        _bc,
        default_mods,
        scripts_dir,
        spel_mods_dir,
        spel_output_dir,
        unittests_dir,
    )
    from utilityFunctions import find_file_for_subroutine, insert_header_for_unittest
    from variable_analysis import determine_global_variable_status

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
        casename = "canflux"

    case_dir = unittests_dir + casename

    # List of subroutines to be analyzed
    # sub_name_list = ["LakeTemperature", "SoilTemperature"]
    sub_name_list = [
        "Allocation1_PlantNPDemand",
        "Allocation2_ResolveNPLimit",
        "Allocation3_PlantCNPAlloc",
    ]
    # sub_name_list = ["SoilLittVertTransp"]
    if args.sub_names:
        sub_name_list = [s.lower() for s in args.sub_names]

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
            os.system("rm *.pkl")
            preprocess = True

    # Initialize dictionary that will hold instance of all subroutines encountered.
    main_sub_dict = {}

    # Initialize lists that will hold global variables based on read/write status
    read_types = []
    write_types = []

    # dictionary holds instances for Unit Test specific subroutines
    sub_name_list = [s.lower() for s in sub_name_list]
    subroutines: dict[str, Subroutine] = {}

    # List to hold all the modules needed for the unit test
    needed_mods = []
    mod_dict: dict[str, FortranModule] = {}
    for s in sub_name_list:
        # Get general info of the subroutine
        # subroutines[s] = Subroutine(s, calltree=["elm_drv"])

        # Process files by removing certain modules
        # so that a standalone unit test can be compiled.
        # All file information will be stored in `mod_dict` and `main_sub_dict`
        if preprocess and not opt:
            fn, startl, endl = find_file_for_subroutine(name=s)
            mod_dict, file_list, main_sub_dict = process_for_unit_test(
                fname=fn,
                case_dir=case_dir,
                mod_dict=mod_dict,
                mods=needed_mods,
                required_mods=default_mods,
                main_sub_dict=main_sub_dict,
                overwrite=True,
                verbose=False,
            )
            # Update initial subroutine with data collected by `process_for_unit_test`
            # NOTE: direct assignment here means that changes to subroutines[s] object
            #       below will be reflected immediately in main_sub_dict. Make explicit instead?
            subroutines[s] = main_sub_dict[s]
            subroutines[s].print_subroutine_info()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # examineLoops performs adjustments that go beyond the "naive"                  #
    # reliance on the "!$acc routine" directive.                                    #
    #    * adjust_allocation : rewrites local variable allocation and indexing      #
    #    * add_acc : accelerated via "!$acc parallel loop" directives               #
    #              which relies on using processor level filters in main.F90.       #
    #                                                                               #
    # NOTE: avoid having both adjust_allocation and add_acc both True for now       #
    #       as they don't currently communicate and they both modify the same files #
    #       which may cause subroutine line numbers to change, etc...               #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # TODO: Adjust expected arguments to examineLoops after recent refactoring.
    # if opt:
    #     for s in sub_name_list:
    #         if subroutines[s].name not in main_sub_dict:
    #             main_sub_dict[subroutines[s].name] = subroutines[s]
    #         subroutines[s].examineLoops(
    #             global_vars=[],
    #             varlist=var_list,
    #             main_sub_dict=main_sub_dict,
    #             verbose=False,
    #             add_acc=add_acc,
    #             adjust_allocation=adjust_allocation,
    #         )
    #     print("Done running in Optimization Mode")

    if not mod_dict:
        print(f"{func_name}::Error didn't find any modules related to subroutines")
        sys.exit(1)

    # print_spel_module_dependencies(mod_dict=mod_dict,subs=subroutines)

    with open(f"{case_dir}/source_files_needed.txt", "w") as ofile:
        for f in file_list:
            ofile.write(f + "\n")

    type_dict: dict[str, DerivedType] = {}
    for mod in mod_dict.values():
        for utype, dtype in mod.defined_types.items():
            type_dict[utype] = dtype

    instance_to_user_type = {}
    for type_name, dtype in type_dict.items():
        if "bounds" in type_name:
            continue
        # All instances should have been found so throw an error
        if not dtype.instances:
            print(
                _bc.WARNING + f"Warning: no instances found for {type_name}" + _bc.ENDC
            )
        for instance in dtype.instances:
            instance_to_user_type[instance.name] = type_name

    # 'main_sub_dict' contains Subroutine instances for all subroutines
    # in any needed modules. Next, each subroutine within the call trees of the user
    # specified subroutines will be further analyzed to trace usage of global variables
    #
    for s in sub_name_list:
        #
        # Parsing means getting info on the variables read and written
        # to by the subroutine and any of its callees
        #
        subroutines[s].parse_subroutine(
            dtype_dict=type_dict, main_sub_dict=main_sub_dict, verbose=False
        )

        subroutines[s].child_subroutines_analysis(
            dtype_dict=type_dict, main_sub_dict=main_sub_dict, verbose=False
        )

    for sub in subroutines.values():

        sub.elmtype_r = replace_ptr_with_targets(
            sub.elmtype_r, type_dict, instance_to_user_type
        )
        sub.elmtype_w = replace_ptr_with_targets(
            sub.elmtype_w, type_dict, instance_to_user_type
        )
        sub.elmtype_rw = replace_ptr_with_targets(
            sub.elmtype_rw, type_dict, instance_to_user_type
        )

        print(_bc.OKGREEN + f"Derived Type Analysis for {sub.name}")
        print(f"{func_name}::Read-Only")
        for key in sub.elmtype_r.keys():
            print(key, sub.elmtype_r[key])
        print(f"{func_name}::Write-Only")
        for key in sub.elmtype_w.keys():
            print(key, sub.elmtype_w[key])
        print(f"{func_name}::Read-Write")
        for key in sub.elmtype_rw.keys():
            print(key, sub.elmtype_rw[key])
        print(_bc.ENDC)

        for key in list(sub.elmtype_r.keys()):
            c13c14 = bool("c13" in key or "c14" in key)
            if c13c14:
                del sub.elmtype_r[key]
                continue
            read_types.append(key)

        for key in list(sub.elmtype_w.keys()):
            c13c14 = bool("c13" in key or "c14" in key)
            if c13c14:
                del sub.elmtype_w[key]
                continue
            write_types.append(key)

        for key in list(sub.elmtype_rw.keys()):
            c13c14 = bool("c13" in key or "c14" in key)
            if c13c14:
                del sub.elmtype_rw[key]
                continue
            write_types.append(key)

    argument_vars = {}
    for sub in subroutines.values():
        for key in list(sub.elmtype_r.keys()):
            if "%" not in key:
                argument_vars[key] = sub.elmtype_r.pop(key)
        for key in list(sub.elmtype_w.keys()):
            if "%" not in key:
                argument_vars[key] = sub.elmtype_w.pop(key)
        for key in list(sub.elmtype_rw.keys()):
            if "%" not in key:
                argument_vars[key] = sub.elmtype_rw.pop(key)

    # Create a makefile for the unit test
    wr.generate_makefile(files=file_list, case_dir=case_dir)

    # Make sure physical properties types are read/written:
    list_pp = ["veg_pp", "lun_pp", "col_pp", "grc_pp", "top_pp"]

    aggregated_elmtypes_list = []
    for x in read_types:
        dtype_inst = x.split("%")[0]
        if dtype_inst not in aggregated_elmtypes_list:
            aggregated_elmtypes_list.append(dtype_inst)
    for x in write_types:
        dtype_inst = x.split("%")[0]
        if dtype_inst not in aggregated_elmtypes_list:
            aggregated_elmtypes_list.append(dtype_inst)

    dtype_info_list = []

    for s in sub_name_list:
        set_active_variables(
            type_dict, instance_to_user_type, subroutines[s].elmtype_r, dtype_info_list
        )
        set_active_variables(
            type_dict, instance_to_user_type, subroutines[s].elmtype_w, dtype_info_list
        )
        set_active_variables(
            type_dict, instance_to_user_type, subroutines[s].elmtype_rw, dtype_info_list
        )

    # Will need to read in physical properties type
    # so set all components to True
    for type_name, dtype in type_dict.items():
        for var in dtype.instances:
            if var.name in ["veg_pp", "lun_pp", "col_pp", "grc_pp", "top_pp"]:
                dtype.active = True
                var.active = True
                for c in dtype.components.values():
                    c["active"] = True

    for el in write_types:
        if el not in read_types:
            read_types.append(el)
    #
    # Write derived type info to csv file
    #
    ofile = open(f"{case_dir}/derive_type_info.csv", "w")
    csv_file = csv.writer(ofile)
    row = ["Derived Type", "Component", "Type", "Dimension"]
    csv_file.writerow(row)
    for row in dtype_info_list:
        csv_file.writerow(row)
    ofile.close()

    print(f"Call Tree for {case_dir}")
    for sub in subroutines.values():
        tree = sub.calltree[2:]
        sub.analyze_calltree(tree, case_dir)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                        VERIFICATION MODULE                                #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Generate modules to output results from unit-test for validation purposes.
    # Call the relevant update_vars_{sub} after the parallel region.

    elmvars_dict = {}
    for dtype in type_dict.values():
        for inst in dtype.instances:
            elmvars_dict[inst.name] = inst

    # create list of variables that should be used for verification.
    # Will go ahead and use all variables for now but can limit to just w,rw
    # to save memory if needed.
    for sub in subroutines.values():
        verify_vars = {}
        total_vars = []
        total_vars.extend(sub.elmtype_r.keys())
        total_vars.extend(sub.elmtype_w.keys())
        total_vars.extend(sub.elmtype_rw.keys())
        for var in total_vars:
            if "bounds" in var:
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
    aggregated_elmtypes_list.sort(key=lambda v: v.upper())
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

    # Remove xxx_pp from read_types
    for var in list_pp:
        if var in read_types:
            read_types.remove(var)

    # type_dict["conctransporttype"].manual_deep_copy()
    active_global_vars = determine_global_variable_status(mod_dict, subroutines)

    # Subroutine analysis should be complete. Store info in main_sub_dict
    for sub in subroutines.values():
        main_sub_dict[sub.name] = sub

    # Generate/modify FORTRAN files needed to initialize and run Unit Test
    # main.F90
    wr.clean_main(aggregated_elmtypes_list, files=needed_mods, case_dir=case_dir)
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


def set_active_variables(type_dict, type_lookup, variable_list, dtype_info_list):
    """
    This function sets the active status of the user defined types
    based on variable list
        * type_dict   : dictionary of all user-defined types found in the code
        * type_lookup : dictionary that maps an variable to it's user-defined type
        * variable_list   : list of variables that are used (eg. elmtype_r, elmtype_w)
        * dtype_info_list : list for saving to file (redundant?)
    """
    argument_variables = [var for var in variable_list if "%" not in var]
    instance_member_vars = [var for var in variable_list if "%" in var]
    for var in instance_member_vars:
        dtype, component = var.split("%")
        if "bounds" in dtype:
            continue
        type_name = type_lookup[dtype]
        type_dict[type_name].active = True
        # Set which components of derived type are active
        for c in type_dict[type_name].components.values():
            field_var = c["var"]
            if field_var.name == component and not c["active"]:
                c["active"] = True
                datatype = field_var.type
                dim = field_var.dim
                dtype_info_list.append([dtype, field_var.name, datatype, f"{dim}D"])

    # Set which instances of derived types are actually used.
    global_vars = [v.split("%")[0] for v in instance_member_vars]
    global_vars = list(set(global_vars))
    for var in global_vars:
        if "bounds" == var:
            continue
        type_name = type_lookup[var]
        # Set which instances of the derived type are active
        for inst in type_dict[type_name].instances:
            if inst.name == var and not inst.active:
                inst.active = True

    return None


if __name__ == "__main__":
    main()
