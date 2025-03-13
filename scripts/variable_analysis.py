from __future__ import annotations

import re
from pprint import pprint
from typing import TYPE_CHECKING, Dict

from scripts.types import LineTuple, ModUsage, PointerAlias

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

from scripts.fortran_modules import FortranModule, get_module_name_from_file
from scripts.utilityFunctions import Variable


def add_global_vars(
    dep_mod: FortranModule,
    vars: dict[str, Variable],
    mod_usage: ModUsage,
):
    """ """
    intrinsic_types = {"real", "integer", "logical", "character"}
    if mod_usage.all:
        vars.update(dep_mod.global_vars)
    else:
        for id in mod_usage.clause_vars:
            var = dep_mod.global_vars.get(id.obj)
            if var is None or var.type not in intrinsic_types:
                continue
            vars[id.obj] = var
    return


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
    sub: Subroutine,
    verbose=False,
) -> None:
    """
    Function that goes through the list of subroutines and returns the non-derived type
    global variables that are used inside those subroutines

    Arguments:
        * mod_dict : dictionary of unit test modules
        * subroutines : list of Subroutine objects
    """
    func_name = "determine_global_variables_status"

    fileinfo = sub.get_file_info(all=True)
    # temp mod dict for only those related to this Sub
    test_modules: Dict[str, FortranModule] = {}
    modname = sub.module
    sub_mod = mod_dict[modname]
    variables: dict[str, Variable] = {}
    for mod_name, musage in sub_mod.head_modules.items():
        add_global_vars(dep_mod=mod_dict[mod_name], vars=variables, mod_usage=musage)

    sub_dep = sub_mod.sort_module_deps(startln=fileinfo.startln, endln=fileinfo.endln)
    for mod_name, musage in sub_dep.items():
        add_global_vars(dep_mod=mod_dict[mod_name], vars=variables, mod_usage=musage)

    if not variables:
        return
    # Create regex from the possible variables
    var_string = "|".join(variables.keys())
    regex_variables = re.compile(r"\b({})\b".format(var_string), re.IGNORECASE)

    # Loop through the subroutines and check for variables used within.
    # `check_global_vars` loops through each sub and looks for any matches
    active_vars = check_global_vars(regex_variables, sub)
    if verbose:
        print(f"{func_name}::sub ", sub.name)
        print(f"{func_name}::test modules ", test_modules)
        print(f"{func_name}::active_vars :", active_vars)
    if active_vars:
        for var in active_vars:
            variables[var].active = True
            sub.active_global_vars[var] = variables[var].copy()

    return
