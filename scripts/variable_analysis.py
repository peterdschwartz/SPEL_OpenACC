import re

from fortran_modules import get_module_name_from_file


def check_global_vars(regex_variables, sub):
    """ """
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


def determine_global_variable_status(mod_dict, subroutines):
    """ """
    func_name = "determine_global_variables_status"
    all_subs = {}
    for sub in subroutines.values():
        all_subs[sub.name] = sub
        for child_sub in sub.child_Subroutine.values():
            if child_sub.name not in all_subs:
                all_subs[child_sub.name] = child_sub

    # Retrive all global (instrinsic type) variables
    modules = {}
    for sub in all_subs.values():
        modln, modname = get_module_name_from_file(sub.filepath)
        sub_mod = mod_dict[modname]
        for m in sub_mod.modules:
            modules[m] = mod_dict[m]

    # Create dict of all variables to look for
    variables = {}
    intrinsic_types = ["real", "integer", "logical", "character"]
    for mod in modules.values():
        for var in mod.global_vars:
            if var.type in intrinsic_types and not var.parameter:
                if var.name not in variables:
                    variables[var.name] = var
                    print(f"{var.name} from {mod.name}")
                else:
                    print(
                        f"{func_name}::WARNING: Attempted to add variable multiple times"
                    )

    # Create regex
    var_string = "|".join(variables.keys())
    regex_variables = re.compile(r"({})".format(var_string), re.IGNORECASE)

    # Loop through the subroutines and check for variables used:
    for sub in all_subs.values():
        active_vars = check_global_vars(regex_variables, sub)
        if active_vars:
            for var in active_vars:
                print(f"setting {var} active", variables[var])
                variables[var].active = True

    return None
