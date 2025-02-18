from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict

from scripts.types import LineTuple

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

from scripts.fortran_modules import FortranModule, get_module_name_from_file
from scripts.utilityFunctions import Variable


def check_global_vars(regex_variables, sub: Subroutine) -> set[str]:
    """
    Function that checks sub for usage of any variables matched by
    regex_variables.
    """
    func_name = "check_global_vars"
    sub_lines = sub.sub_lines
    fileinfo = sub.get_file_info()

    lines = [lpair for lpair in sub_lines if lpair.ln >= fileinfo.startln]

    matched_lines: list[LineTuple] = [
        lpair for lpair in filter(lambda x: regex_variables.search(x.line), lines)
    ]

    # Loop through subroutine line by line starting after the associate clause
    active_vars: set[str] = set()
    for lpair in matched_lines:
        match_var = regex_variables.findall(lpair.line)
        for var in match_var:
            if var not in active_vars:
                active_vars.add(var)
    return active_vars


def determine_global_variable_status(
    mod_dict: dict[str, FortranModule],
    subroutines: dict[str, Subroutine],
    verbose=False,
) -> dict[str, Variable]:
    """
    Function that goes through the list of subroutines and returns the non-derived type
    global variables that are used inside those subroutines

    Arguments:
        * mod_dict : dictionary of unit test modules
        * subroutines : list of Subroutine objects
    """
    func_name = "determine_global_variables_status"
    all_subs: Dict[str, Subroutine] = {}
    for sub in subroutines.values():
        all_subs[sub.name] = sub

    # Create dict of modules containing unit-test subroutines
    test_modules: Dict[str, FortranModule] = {}
    for sub in all_subs.values():
        modname = sub.module
        sub_mod = mod_dict[modname]
        if modname not in test_modules:
            sub_mod.sort_used_variables(mod_dict)
            test_modules[modname] = sub_mod

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
                used_mod = mod_dict[used_modname]
                for gv in used_mod.global_vars:
                    if gv.type in intrinsic_types:
                        variables[gv.name] = gv

    # Create regex from the possible variables
    var_string = "|".join(variables.keys())
    regex_variables = re.compile(r"\b({})\b".format(var_string), re.IGNORECASE)

    if verbose:
        print(f"{func_name}::all subs ", all_subs)
        print(f"{func_name}::test modules ", test_modules)
        print(f"{func_name}::variables found ", variables)

    # Loop through the subroutines and check for variables used within.
    # `check_global_vars` loops through each sub and looks for any matches
    for sub in all_subs.values():
        active_vars = check_global_vars(regex_variables, sub)
        if active_vars:
            for var in active_vars:
                variables[var].active = True
                sub.active_global_vars[var] = variables[var]

    return variables
