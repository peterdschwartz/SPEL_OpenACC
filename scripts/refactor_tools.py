import os
import re
import sys

from scripts.analyze_subroutines import Subroutine
from scripts.mod_config import _bc, spel_dir


def compress_on_filter(sub: Subroutine):
    """
    Function that analyzes a subroutine's local variables for the filters being used.
    If all the same filter, then allocation of local variable is reduced to the num_filter
    """
    sub_lines = sub.sub_lines
    return


def adjust_array_access_and_allocation(local_arrs, sub, dargs=False, verbose=False):
    """
    Function edits ELM FORTRAN files to reduce memory.
    Replaces statements like "arr(bounds%begc:bounds%endc)" -> "arr(1:num_filterc)"
    and accesses like "arr(c)" -> "arr(fc)"

    * local_arrs    : list of local array Variables
    * sub           : Subroutine that calls this function and declares the local_arrs
    * sub.VariablesPassedToSub : dictionary that matches "arr" to subroutines that take them as arguments
    """
    import os.path
    import re

    from scripts.mod_config import _bc, spel_dir

    # Get lines of this file:
    ifile = open(sub.filepath, "r")
    lines = ifile.readlines()  # read entire file
    ifile.close()

    track_changes = []
    arg_list = [v for v in sub.Arguments]
    scalar_list = [v.name for v in sub.LocalVariables["scalars"].values()]

    print(_bc.BOLD + _bc.FAIL + f"arguments for {sub.name} are", arg_list, _bc.ENDC)
    print(_bc.BOLD + _bc.FAIL + f"scalars for {sub.name} are", scalar_list, _bc.ENDC)

    # replace declarations first
    if not dargs:
        for arr in local_arrs:
            var = arr
            filter_used = arr.filter_used
            ln = var.ln
            # line number of declaration
            subgrid = var.subgrid  # subgrid index

            print(_bc.BOLD + _bc.WARNING + f"Adjusting {var.name}" + _bc.ENDC)
            filter_used = filter_used + subgrid

            # Check that the corresponding num_filter exists
            num_filter = "num_" + filter_used.replace("filter_", "")
            if num_filter in arg_list:
                print(num_filter, "is passed as an argument!")
            elif num_filter in scalar_list:
                print(f"{num_filter} is new local filter")
            else:
                sys.exit(f"utilityFunctions:: {num_filter} doesn't exit")
            lold = lines[ln]
            print(_bc.FAIL + lold.strip("\n") + _bc.ENDC)
            _str = f"bounds%beg{subgrid}:bounds%end{subgrid}"

            replace_str = f"1:{num_filter}"
            lnew = lines[ln].replace(_str, replace_str)
            print(_bc.OKGREEN + lnew.strip("\n") + _bc.ENDC)
            lines[ln] = lnew
            track_changes.append(lnew)

    # Go through all loops and make replacements for filter index
    ng_regex_array = re.compile(r"\w+\s*\([,\w+\*-]+\)", re.IGNORECASE)
    regex_var = re.compile(r"\w+")
    regex_indices = re.compile(r"(?<=\()(.+)(?=\))")
    print("Going through loops")
    # Make list for quick check if var should be adjusted.
    list_of_var_names = [v.name for v in local_arrs]

    for loop in sub.DoLoops:
        lstart = loop.start[0]
        lend = loop.end[0]
        if loop.subcall.name != sub.name:
            continue

        for n in range(lstart, lend):
            l = lines[n].split("!")[0]
            l = l.strip()
            if not l:
                continue
            m_arr = ng_regex_array.findall(lines[n])
            lold = lines[n]
            lnew = lines[n]

            replaced = False
            temp_line = lold

            removing = True
            while removing:
                # set removing to be False unless there is a match
                removing = False

                for arr in m_arr:
                    v = regex_var.search(arr).group()

                    # min and max functions are special cases since they take two argumnets (fix?)
                    if v in ["min", "max"]:
                        temp_line = temp_line.replace(arr, v)
                        removing = True
                        continue

                    # Check if var is
                    if v in list_of_var_names:
                        loc_ = list_of_var_names.index(v)
                        local_var = local_arrs[loc_]
                        var = local_var
                        subgrid = var.subgrid
                        filter_used = var.filter_used + var.subgrid

                        # Consistency check for filter.
                        # TODO: allow scripts to insert reverse filter (eg., "fc = col_to_filter(c)" )
                        loop_filter = loop.filter[0]
                        same_filter_type = bool(filter_used[:-1] == loop_filter[:-1])
                        if filter_used != loop_filter and not same_filter_type:
                            print(
                                f"Filter Mismatch: loops uses {loop.filter[0]}, {var.name} needs {filter_used}"
                            )
                            sys.exit()
                        elif same_filter_type and filter_used != loop_filter:
                            print(
                                _bc.WARNING
                                + _bc.BOLD
                                + f"{var.name} needs reverse filter!"
                            )

                        # Make replacement in line: (assumes subgrid is first index!!)
                        # lnew = lnew.replace(f"{v}({subgrid}",f"{v}(f{subgrid}")
                        lnew = re.sub(
                            r"{}\s*\({}".format(v, subgrid),
                            r"{}(f{}".format(v, subgrid),
                            lnew,
                        )
                        replaced = True

                    regex_check_index = re.compile(
                        r"\w+\([,a-z0-9*-]*(({})\(.\))[,a-z+0-9-]*\)".format(v),
                        re.IGNORECASE,
                    )
                    match = regex_check_index.search(temp_line)
                    if match:  # array {v} is being used as an index
                        # substitute from the entire line
                        i = regex_indices.search(arr).group()
                        i = r"\({}\)".format(i)
                        temp_line = re.sub(r"{}{}".format(v, i), v, temp_line)
                        removing = True
                m_arr = ng_regex_array.findall(temp_line)

            if replaced and verbose:
                print(_bc.FAIL + lold.strip("\n") + _bc.ENDC)
                print(_bc.OKGREEN + lnew.strip("\n") + _bc.ENDC)
                print("\n")
                lines[n] = lnew
                track_changes.append(lnew)

    # Check if subroutine calls need to be adjusted
    # First filter out sub arguments that aren't local
    # variables only accessed by a filter
    # Adjust Subroutine calls

    # Note that these subroutines have specific versions for
    # using filter or not using a filter.
    dont_adjust = ["c2g", "p2c", "p2g", "p2c", "c2l", "l2g"]
    dont_adjust_string = "|".join(dont_adjust)
    regex_skip_string = re.compile(f"({dont_adjust_string})", re.IGNORECASE)

    vars_to_check = {s: [] for s in sub.VariablesPassedToSubs}
    for subname, arg in sub.VariablesPassedToSubs.items():
        m_skip = regex_skip_string.search(subname)
        if m_skip:
            print(_bc.FAIL + f"{subname} must be manually altered !" + _bc.ENDC)
            continue
        for v in arg:
            if v.name in list_of_var_names:
                print(f"Need to check {v.name} for mem adjustment called in {subname}.")
                vars_to_check[subname].append(v)

    for sname, vars in vars_to_check.items():
        for v in vars:
            print(f"{sname} :: {v.name}")

    for subname, args in sub.VariablesPassedToSubs.items():
        m_skip = regex_skip_string.search(subname)
        if m_skip:
            print(_bc.FAIL + f"{subname} must be manually altered !" + _bc.ENDC)
            continue
        regex_subcall = re.compile(r"\s+(call)\s+({})".format(subname), re.IGNORECASE)

        for arg in args:
            # If index fails, then there is an inconsistency
            # in examineLoops
            if arg.name not in list_of_var_names:
                continue
            loc_ = list_of_var_names.index(arg.name)
            local_var = local_arrs[loc_]
            filter_used = local_var.filter_used + arg.subgrid
            # bounds string:
            bounds_string = r"(\s*bounds%beg{}\s*:\s*bounds%end{}\s*|\s*beg{}\s*:\s*end{}\s*)".format(
                arg.subgrid, arg.subgrid, arg.subgrid, arg.subgrid
            )
            # string to replace bounds with
            num_filter = "num_" + filter_used.replace("filter_", "")
            num_filter = f"1:{num_filter}"
            regex_array_arg = re.compile(r"{}\s*\({}".format(arg.name, bounds_string))

            for ln in range(sub.startline, sub.endline):
                line = lines[ln]
                match_call = regex_subcall.search(line)
                if match_call:
                    replaced = False
                    # create regex to match variables needed
                    l = line[:]
                    m_var = regex_array_arg.search(l)
                    if m_var:
                        lold = lines[ln].rstrip("\n")
                        lnew = regex_array_arg.sub(
                            f"{arg.name}({num_filter}", lines[ln]
                        )
                        lines[ln] = lnew
                        replaced = True
                        track_changes.append(lnew)

                    while l.rstrip("\n").strip().endswith("&") and not replaced:
                        ln += 1
                        l = lines[ln]
                        m_var = regex_array_arg.search(l)
                        if m_var:
                            lold = lines[ln].rstrip("\n")
                            lnew = regex_array_arg.sub(
                                f"{arg.name}({num_filter}", lines[ln]
                            )
                            lines[ln] = lnew
                            replaced = True
                            track_changes.append(lnew)

                    if replaced:
                        print(_bc.FAIL + lold.rstrip("\n") + _bc.ENDC)
                        print(_bc.OKGREEN + lnew.rstrip("\n") + _bc.ENDC)
                        print("\n")
                        break
                    else:
                        print(
                            _bc.FAIL
                            + f"Couldn't replace {arg.name} in {subname} subroutine call"
                            + _bc.ENDC
                        )
                        sys.exit()

    # Save changes:
    if track_changes:
        if not os.path.exists(spel_dir + f"modified-files/{sub.filepath}"):
            print(
                _bc.BOLD + _bc.WARNING + "Writing to file ",
                spel_dir + f"modified-files/{sub.filepath}" + _bc.ENDC,
            )
            ofile = open(spel_dir + f"modified-files/{sub.filepath}", "w")
            ofile.writelines(lines)
            ofile.close()
        else:
            print(
                _bc.BOLD + _bc.WARNING + "Writing to file ",
                elm_files + sub.filepath + _bc.ENDC,
            )
            ofile = open(elm_files + sub.filepath, "w")
            ofile.writelines(lines)
            ofile.close()

    for subname, args in sub.VariablesPassedToSubs.items():
        # Modify dummy arguments for child subs if needed
        # may be redundant to find file here?
        #
        m_skip = regex_skip_string.search(subname)
        if m_skip:
            print(_bc.FAIL + f"{subname} must be manually altered !" + _bc.ENDC)
            continue
        print(_bc.WARNING + f"Modifying dummy args for {subname}")
        file, startline, endline = find_file_for_subroutine(subname)
        childsub = sub.child_Subroutine[subname]
        adjust_child_sub_arguments(childsub, file, startline, endline, args)


def adjust_child_sub_arguments(sub, file, lstart, lend, args):
    """
    Function that checks and modifies bounds accesses
    for subroutine arguments
        * childsub : Subroutine instance for child subroutine
        * arg : Variable instance for dummy arg name
    """

    if os.path.exists(spel_dir + f"modified-files/{file}"):
        print(file, "has already been modified")
        file = f"../modified-files/{file}"

    print(f"Opening {sub.filepath}")
    ifile = open(sub.filepath, "r")
    lines = ifile.readlines()
    ifile.close()

    for arg in args:
        # Use keyword instead of arg name.
        # If keyword is missing then we need to determine the name!
        kw = arg.keyword
        if not kw:
            sys.exit(f"Error keyword for {arg.name} in {sub.name} is missing")

        regex_arg_type = re.compile(f"{arg.type}", re.IGNORECASE)
        regex_arg_name = re.compile(r"{}\s*\(".format(kw), re.IGNORECASE)
        regex_bounds_full = re.compile(
            r"({}\s*\()(bounds%beg{})\s*(:)\s*(bounds%end{})\s*(\))".format(
                kw, arg.subgrid, arg.subgrid
            ),
            re.IGNORECASE,
        )
        regex_bounds = re.compile(
            r"({}\s*\(\s*bounds%beg{}[\s:]+\))".format(kw, arg.subgrid), re.IGNORECASE
        )
        for ct in range(lstart - 1, lend):
            #
            line = lines[ct]
            lold = line
            line = line.split("!")[0]
            line = line.strip()

            replaced = False
            # Match type and name for arg
            match_type = regex_arg_type.search(line)
            match_name = regex_arg_name.search(line)

            if match_type and match_name:
                match_bounds = regex_bounds.search(line)
                match_full_bounds = regex_bounds_full.search(line)
                if match_bounds and not match_full_bounds:
                    lnew = regex_bounds.sub(f"{kw}(1:)", lold)
                    lines[ct] = lnew
                    replaced = True
                else:
                    print(f"{line} -- No Action Needed")
                    sys.exit()

    # Write to file
    with open(sub.filepath, "w") as ofile:
        ofile.writelines(lines)

    # re-run access adjustment for the dummy args only!
    sub.filepath = file
    dargs = []
    for arg in args:
        v = arg
        v.name = v.keyword
        v.keyword = ""

    adjust_array_access_and_allocation(
        local_arrs=args, sub=sub, verbose=True, dargs=True
    )


def determine_filter_access(sub, verbose=False):
    """
    Function that will go through all the loops for
    local variables that are bounds accessed.
    """
    ok_to_replace = {}

    # List that accumulates all info necessary for memory adjustment
    local_vars = []  # [Variable]
    array_dict = sub.LocalVariables["arrays"]
    for vname, lcl_var in array_dict.items():
        if lcl_var.subgrid == "?":
            continue
        lcl_arr = lcl_var.name
        ok_to_replace[lcl_arr] = False
        filter_used = ""
        indx, ln = lcl_var.subgrid, lcl_var.ln
        for loop in sub.DoLoops:
            if loop.subcall.name != sub.name:
                continue
            if lcl_arr in loop.vars or lcl_arr in loop.reduce_vars:
                if not loop.filter:  # Loop doesn't use a filter?
                    filter_used = "None"
                    continue
                fvar, fidx, newidx = loop.filter
                # Case where no filter is used
                if not fvar:
                    if indx not in loop.index:
                        print(
                            f"{lcl_arr} {indx} used in {loop.subcall.name}:L{loop.start[0]} {fvar},{fidx}{loop.index}"
                        )
                if not filter_used:
                    # Get rid of the subgrid info
                    filter_used = fvar[:-1]
                elif filter_used != fvar[:-1] and filter_used != "Mixed":
                    filter_used = "Mixed"
                    break
        #
        if filter_used == "None":
            print(f"No filter being used -- won't adjust {lcl_arr}")
        elif filter_used == "Mixed":
            ok_to_replace[lcl_arr] = False
        elif filter_used and filter_used != "Mixed":
            ok_to_replace[lcl_arr] = True
            lcl_var.filter_used = filter_used
            local_vars.append(lcl_var)

    if local_vars:
        list_of_var_names = [v.name for v in local_vars]
        adjust_array_access_and_allocation(local_vars, sub=sub, verbose=True)
