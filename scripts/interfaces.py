import re
import subprocess as sp
import sys

from scripts.fortran_modules import PointerAlias
from scripts.mod_config import ELM_SRC, _bc
from scripts.utilityFunctions import Variable


def resolve_interface(sub, iname, args, dtype_dict, sub_dict, verbose=False):
    """
    Determines which subroutine in an interface is being called.
    Argument details:
        sub: Subroutine object of parent subroutine
        iname : name of interface
        args : list of arguments passed to interface
        dtype_dict : dictionary of derived types with instances as keys
        sub_dict : dictionary of subroutines -- used to match child subroutines
    """
    func_name = "resolve_interface"
    if verbose:
        print(_bc.FAIL + f"Resolving interface for {iname}\n with args: {args}")
    cmd = f'grep -rin --exclude-dir={ELM_SRC}external_models/ -E "^[[:space:]]+(interface {iname})" {ELM_SRC}*'
    output = sp.getoutput(cmd)

    # Get file and line number for interface
    # list that goes:  [filename, linenumber, interface {iname}]
    output = output.split(":")
    if len(output) != 3:
        sys.exit(
            f"resolve_interface:: Couldn't find file with interface {iname}\n"
            f"cmd: {cmd}\noutput: {output}"
        )
    fn, ln, pattern = output

    ln = int(ln)

    # Read file:
    ifile = open(fn, "r")
    lines = ifile.readlines()
    ifile.close()

    # Get list of possible procedures within the interface

    regex_end = re.compile(r"^\s*(end)\s+(interface)", re.IGNORECASE)
    regex_procedure = re.compile(r"^\s*(module)\s+(procedure)\s+", re.IGNORECASE)

    interface_sub_names = []  # list of subroutine names in the interface
    ct = ln - 1
    in_interface = True
    while in_interface:
        m_end = regex_end.search(lines[ct])
        if m_end:
            in_interface = False
        else:
            m_proc = regex_procedure.search(lines[ct])
            if m_proc:
                subname = lines[ct].replace(m_proc.group(), "").strip().lower()
                interface_sub_names.extend([s.strip() for s in subname.split(",")])
        ct += 1

    # Go through each argument passed to interface and create an appropiate Variable instance for it
    # to be compared to the dummy arguments of each subroutine in the list above.
    special = "xx"  # Special data type used for arguments that are math expressions so either int or real
    l_args = []  # list to hold arguments as Variables

    for arg in args:
        found = False
        # Check global associate variables if arg is an associated global variable
        # then the type is already known
        if "%" in arg:
            vname, compname = arg.split("%")
            if vname in sub.Arguments:
                for field in dtype_dict[vname].components.values():
                    fieldname = field["var"].name
                    if compname == fieldname:
                        l_args.append(field["var"])
                        found = True
                        break

        if arg in sub.associate_vars:
            vname, compname = sub.associate_vars[arg].split("%")
            for field in dtype_dict[vname].components.values():
                fieldname = field["var"].name
                if compname == fieldname:
                    l_args.append(field["var"])
                    found = True
                    break
            continue
        # Check for keyword argument -- will be matched below
        if "=" in arg:
            l_args.append(
                Variable(type="?", name=arg, subgrid="?", ln="?", dim="?", keyword=True)
            )
            found = True
            continue
        # Check arguments of parent subroutine:
        if arg in sub.Arguments:
            l_args.append(sub.Arguments[arg])
            found = True
            continue

        # Check local variables, arrays :
        if arg in sub.LocalVariables["arrays"].keys():
            l_args.append(sub.LocalVariables["arrays"][arg])
            found = True
            continue
        # Check local variables, scalars:
        scalar_dict = sub.LocalVariables["scalars"].copy()
        if arg in scalar_dict.keys():
            l_args.append(scalar_dict[arg])
            found = True
            continue

        if not found:
            # Couldn't match so arg is assumed to be a math expression
            # Assuming it's equivalent to an integer or real then
            l_args.append(Variable(type=special, name=arg, subgrid="", ln=0, dim=0))
            if verbose:
                print(
                    f"Couldn't match {arg} to any known variable -- assuming {special} type"
                )

    num_input_args = len(l_args)
    resolved_sub_name = ""  # subroutine name that is returned by this function.
    # Instantiate subroutines for interface procedures
    for s in interface_sub_names:
        isub = sub_dict[s]
        child_sub = ""
        # Go through each argument and check if
        # it can be matched to this subroutine's allowed args
        matched = match_input_arguments(l_args, isub, special, verbose=verbose)

        # Check if this subroutine is a match or not
        if sum(matched) == num_input_args:
            if verbose:
                print(f"{func_name}::Subroutine is {s}" + _bc.ENDC)
            resolved_sub_name = s
            child_sub = isub
            break
    if not resolved_sub_name:
        print(
            _bc.FAIL + f"{func_name}::Couldn't resolve interface for {iname}" + _bc.ENDC
        )
        sys.exit(1)
    return resolved_sub_name, child_sub


def match_input_arguments(l_args, sub, special, verbose=False):
    """
    function that matches the args to the corresponding dummy args
    of the subroutine.
    Arguments:
        l_args : list of arguments passed to child subroutine
        sub : subroutine object of candidate child subroutine
        special : special data type used for math expressions
    """
    func_name = "match_input_arguments"

    test_args = [v for v in sub.Arguments.values()]

    num_input_args = len(l_args)

    # Get number of optional arguments
    num_optional_args = 0
    for arg in test_args:
        if arg.optional:
            num_optional_args += 1
    if verbose:
        print(f"{sub.name}:: {num_optional_args} Optional arguments found")

    # Keep track of which args can be matched.
    matched = [False] * num_input_args
    matching = True

    # Simple check regarding number of arguments first:
    num_dummy_args = len(test_args)
    if num_input_args > num_dummy_args:
        if verbose:
            print(f"Too many arguments for {sub.name}")
        return matched  # Too many arguments
    if num_input_args < num_dummy_args - num_optional_args:
        if verbose:
            print(f"Not enough arguments for {sub.name}")
            print(
                f"Num input args: {num_input_args} / Num dummy args: {num_dummy_args}"
            )
        return matched  # not enough arguments

    # get list of arg names for keyword comparsions
    test_arg_names = [k for k in sub.Arguments.keys()]

    argn = 0  # argument number
    skip = 0  # keep track of skipped optional arguments

    # Go through each input arg and see if it can be matched to a dummy arg
    while matching and argn < num_input_args and argn + skip < num_dummy_args:
        input_arg = l_args[argn]

        if "=" in input_arg.name:
            # Note this is not sufficient for subroutines
            # that are differentiated only by dummy arg type
            # but have same names
            test = input_arg.name
            keyword, varname = test.split("=")
            keyword = keyword.strip()
            varname = varname.strip()
            if keyword in test_arg_names:
                if verbose:
                    print(f"{sub.name} accepts {keyword} as keyword")
                matched[argn] = True
                argn += 1
                continue
            else:
                if verbose:
                    print(f"{sub.name} doesn't support {keyword} as keyword")
                matching = False
                continue

        dummy_arg = test_args[argn]
        # check type and dimension:
        same_type = bool(input_arg.type.strip() == dummy_arg.type.strip())
        if not same_type and input_arg.type == special:
            if dummy_arg.type.strip() in ["real", "integer"]:
                same_type = True

        same_dim = bool(input_arg.dim == dummy_arg.dim)
        if same_type and same_dim:
            # This variable should correspond
            # to this dummy argument
            if verbose:
                print(f"{input_arg.name} matches {dummy_arg.name}")
            matched[argn] = True
            argn += 1  # go to next argument
        else:
            if verbose:
                print(f"{input_arg.name} {input_arg.type} {input_arg.dim}")
            if verbose:
                print(
                    f" does not match \n{dummy_arg.name} {dummy_arg.type} {dummy_arg.dim}"
                )
            # Check to see if dummy_arg is optional
            # If it is optional, then cycle through the
            # rest of the variables (which should all be optional right?)
            # Assuming no keywords are used
            if dummy_arg.optional:
                if verbose:
                    print(
                        f"{dummy_arg.name} argument is optional and did not match -- Skipping"
                    )
                skip += 1
            else:
                # This subroutine is not a match
                matching = False
    # return matched array
    return matched


def determine_arg_name(matched_vars, child_sub, args, verbose=False) -> list:
    """
    Function that takes a list of vars passed as arguments to subroutine and
    checks if any correspond to any in 'matched_vars'
        * matched_vars : list of strings for variable names to match
        * child_sub : Subroutine obj
        * args : arguments passed to child_sub

        returns list of PointerAlias(ptr=argname,obj=varname)
            where `argname` is the dummy arg name in the subroutine
            and `varname` is the variable passed to it.
    """
    func_name = "determine_arg_name::"

    var_string = "|".join(matched_vars)
    var_string = f"({var_string})"
    if child_sub.name == "dynamic_plant_alloc":
        verbose = True

    if verbose:
        print(func_name, args)

    arg_vars_list = []
    # Make lists of matched expressions and their location in args.
    matches = [arg for arg in args if re.search(r"\b{}\b".format(var_string), arg)]
    match_locs = [args.index(m) for m in matches]
    for i, locs in enumerate(match_locs):
        # Check if keyword:
        matched_arg = matches[i]
        if "=" in matched_arg:
            keyword, m_var_name = matched_arg.split("=")
            keyword = keyword.strip()
            m_var_name = m_var_name.strip()
            actual_arg = child_sub.Arguments[keyword]
        else:
            # if not keyword we need to match by position.
            # Get argument position by converting to list of keys
            arg_key_list = [arg for arg in child_sub.Arguments.keys()]
            arg_key = arg_key_list[locs]
            actual_arg = child_sub.Arguments[arg_key]
            m_var_name = matched_arg
        arg_to_dtype = PointerAlias(actual_arg.name, m_var_name)
        if verbose:
            print(f"{func_name}{arg_to_dtype}")
        arg_vars_list.append(arg_to_dtype)

    return arg_vars_list
