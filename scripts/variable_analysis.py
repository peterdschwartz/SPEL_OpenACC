import re
import sys

from analyze_subroutines import Subroutine
from fortran_modules import get_module_name_from_file
from utilityFunctions import Variable


def check_global_vars(regex_variables, sub: Subroutine) -> list:
    """
    Function that checks sub for usage of any variables matched by
    regex_variables.
    """
    func_name = "check_global_vars"
    if sub.cpp_filepath:
        fn = sub.cpp_filepath
    else:
        fn = sub.filepath
    file = open(fn, "r")
    lines = file.readlines()
    file.close()
    if sub.associate_end == 0:
        if sub.cpp_startline:
            startline = sub.cpp_startline
        else:
            startline = sub.startline
    else:
        startline = sub.associate_end

    if sub.cpp_endline:
        endline = sub.cpp_endline
    else:
        endline = sub.endline

    # Loop through subroutine line by line starting after the associate clause
    active_vars = []
    ct = startline
    while ct < endline:
        line = lines[ct]
        line = line.split("!")[0].strip().lower()
        if not line:
            ct += 1
            continue
        match_var = regex_variables.findall(line)
        for var in match_var:
            if var not in active_vars:
                active_vars.append(var)
        ct += 1
    return active_vars


def determine_global_variable_status(
    mod_dict, subroutines: dict[str, Subroutine]
) -> dict[str, Variable]:
    """
    Function that goes through the list of subroutines and returns the non-derived type
    global variables that are used inside those subroutines

    Arguments:
        * mod_dict : dictionary of unit test modules
        * subroutines : list of Subroutine objects
    """
    func_name = "determine_global_variables_status"
    all_subs = {}
    for sub in subroutines.values():
        all_subs[sub.name] = sub
        for child_sub in sub.child_Subroutine.values():
            if child_sub.name not in all_subs:
                all_subs[child_sub.name] = child_sub

    # Create dict of modules containing unit-test subroutines
    test_modules = {}
    for sub in all_subs.values():
        modln, modname = get_module_name_from_file(sub.filepath)
        sub_mod = mod_dict[modname]
        for m in sub_mod.modules.keys():
            if m not in test_modules:
                test_modules[m] = mod_dict[m]
                test_modules[m].sort_used_variables(mod_dict)

    # Create dict of all variables to look for. For each of the Test modules,
    # Look at the used modules and add the variables used by those modules.
    variables = {}
    intrinsic_types = ["real", "integer", "logical", "character"]
    for mod in test_modules.values():
        for used_modname, only_clause in mod.modules.items():
            # Check if only certain objects are specified
            if only_clause != "all":
                for ptrobj in only_clause:
                    if isinstance(ptrobj.obj, Variable):
                        # This is a variable, need to check if used in
                        # our specific subroutines
                        var = ptrobj.obj
                        if var.type in intrinsic_types:
                            if ptrobj.ptr:
                                variables[ptrobj.ptr] = var
                            else:
                                variables[var.name] = var
            else:
                # Get full information of used modules
                used_mod = mod_dict[used_modname]
                for gv in used_mod.global_vars:
                    if gv.type in intrinsic_types:
                        variables[gv.name] = gv

    # Create regex from the possible variables
    var_string = "|".join(variables.keys())
    regex_variables = re.compile(r"\b({})\b".format(var_string), re.IGNORECASE)

    # Loop through the subroutines and check for variables used within.
    # `check_global_vars` loops through each sub and looks for any matches
    for sub in all_subs.values():
        active_vars = check_global_vars(regex_variables, sub)
        if active_vars:
            for var in active_vars:
                variables[var].active = True
                sub.active_global_vars[var] = variables[var]

    return variables
