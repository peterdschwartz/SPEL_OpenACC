from __future__ import annotations

import re
import subprocess as sp
import sys

from scripts.analyze_subroutines import Subroutine
from scripts.check_sections import (check_function_start, check_if_block,
                                    create_function)
from scripts.DerivedType import get_derived_type_definition
from scripts.fortran_modules import (FortranModule, get_filename_from_module,
                                     get_module_name_from_file,
                                     parse_only_clause)
from scripts.mod_config import E3SM_SRCROOT, spel_output_dir
from scripts.profiler_context import profile_ctx
from scripts.types import PreProcTuple
from scripts.utilityFunctions import (check_cpp_line, comment_line,
                                      find_variables, get_interface_list,
                                      line_unwrapper, parse_line_for_variables)

# Compile list of lower-case module names to remove
# SPEL expects these all to be lower-case currently
bad_modules = [
    "abortutils",
    "shr_log_mod",
    "elm_time_manager",
    "shr_infnan_mod",
    "clm_time_manager",
    "pio",
    "shr_sys_mod",
    "perf_mod",
    "shr_assert_mod",
    "spmdmod",
    "restutilmod",
    "histfilemod",
    "accumulmod",
    "ncdio_pio",
    "shr_strdata_mod",
    "fileutils",
    "elm_nlutilsmod",
    "shr_mpi_mod",
    "shr_nl_mod",
    "shr_str_mod",
    "controlmod",
    "getglobalvaluesmod",
    "organicfilemod",
    "elmfatesinterfacemod",
    "externalmodelconstants",
    "externalmodelinterfacemod",
    "waterstatetype",
    "seq_drydep_mod",
    "temperaturetype",
    "waterfluxtype",
    "shr_file_mod",
    "mct_mod",
    "elm_instmod",
    "spmdgathscatmod",
    "perfmod_gpu",
]

fates_mod = ["elmfatesinterfacemod"]
betr_mods = ["betrsimulationalm"]

bad_subroutines = [
    "endrun",
    "restartvar",
    "hist_addfld1d",
    "hist_addfld2d",
    "init_accum_field",
    "extract_accum_field",
    "hist_addfld_decomp",
    "ncd_pio_openfile",
    "ncd_io",
    "ncd_pio_closefile",
    "alm_fates",
    "elm_fates",
    "ncd_inqdlen",
    "t_start_lnd",
    "t_stop_lnd",
]

remove_subs = [
    "restartvar",
    "hist_addfld1d",
    "hist_addfld2d",
    "init_accum_field",
    "extract_accum_field",
    "prepare_data_for_em_ptm_driver",
    "prepare_data_for_em_vsfm_driver",
    "decompinit_lnd_using_gp",
]
#
# Macros that we want to process. Any not in the list will be
# skipped.
macros = ["MODAL_AER"]
#    gfortran -D<FLAGS> -I{E3SM_SRCROOT}/share/include -cpp -E <file> > <output>
# will generate the preprocessed file with Macros processed.
# But what to do about line numbers?
# The preprocessed file will have a '# <line_number>' indicating
# the line number immediately after the #endif in the original file.


def remove_subroutine(og_lines, cpp_lines, start):
    """Function to comment out an entire subroutine"""
    func_name = "remove_subroutine"
    end_sub = False

    og_ln = start.ln
    endline = 0
    while not end_sub:
        if og_ln > len(og_lines):
            print(f"{func_name}::ERROR didn't find end of subroutine")
            sys.exit(1)
        match_end = re.search(r"^(\s*end subroutine)", og_lines[og_ln].lower())
        if match_end:
            end_sub = True
            endline = og_ln
        og_lines[og_ln] = "!#py " + og_lines[og_ln]
        og_ln += 1

    if start.cpp_ln:
        # Manually find the end of the subroutine in the preprocessed file
        # Since the subroutine is not of interest, just find the end
        end_sub = False
        cpp_endline = 0
        cpp_ln = start.cpp_ln
        while not end_sub:
            match_end = re.search(r"^(\s*end subroutine)", cpp_lines[cpp_ln].lower())
            if match_end:
                end_sub = True
                cpp_endline = cpp_ln
            cpp_ln += 1
    else:
        cpp_endline = None

    out_ln_pair = PreProcTuple(cpp_ln=cpp_endline, ln=endline)

    return og_lines, out_ln_pair


def parse_local_mods(lines, start):
    """This function is called to determine if
    a subroutine uses ncdio_pio. and remove it if it does
    """
    past_mods = False
    remove = False
    ct = start
    while not past_mods and not remove and ct < len(lines):
        line = lines[ct]
        l = line.split("!")[0]
        if not l.strip():
            ct += 1
            continue
            # line is just a commment
        lline = line.strip().lower()
        if "ncdio_pio" in lline or "histfilemod" in lline or "spmdmod" in lline:
            remove = True
            break
        match_var = re.search(
            r"^(type|integer|real|logical|implicit)", l.strip().lower()
        )
        if match_var:
            past_mods = True
            break
        ct += 1

    return remove


def process_fates_or_betr(lines, mode):
    """
    This function goes back through the file and comments out lines
    that require FATES/BeTR variables/functions
    """

    ct = 0
    if mode == "fates":
        type_name = "hlm_fates_interface_type"
        var = "alm_fates"
    elif mode == "betr":
        type_name = "betr_simulation_alm_type"
        var = "ep_betr"
    else:
        sys.exit("Error wrong mode!")

    if mode == "fates":
        comment_ = "!#fates_py "
    if mode == "betr":
        comment_ = "!#betr_py "

    while ct < len(lines):
        line = lines[ct]
        l = line.split("!")[0]  # don't search comments
        if not l.strip():
            ct += 1
            continue

        match_type = re.search(rf"\({type_name}\)", l.lower())
        if match_type:
            lines, ct = comment_line(lines=lines, ct=ct, mode=mode)
            ct += 1
            continue

        match_call = re.search(rf"[\s]+(call)[\s]+({var})", l.lower())
        if match_call:
            lines, ct = comment_line(lines=lines, ct=ct, mode=mode)
            ct += 1
            continue

        match_var = re.search(f"{var}", l.lower())
        if match_var:
            # could be a function or argument to fucntions?
            lines, ct = comment_line(lines=lines, ct=ct, mode=mode)
            ct += 1
            continue
        ct += 1

    return lines


def get_used_mods(
        ifile: str, # fpath
        mods: list[str], # list[fpath]
        singlefile: bool,
        mod_dict: dict[str, FortranModule],
        verbose: bool=False,
):
    """
    Checks to see what mods are needed to compile the file
    """
    func_name = "get_used_mods"

    # Keep track of nested level
    linenumber, module_name = get_module_name_from_file(fpath=ifile)
    fort_mod = FortranModule(fname=ifile, name=module_name, ln=linenumber)

    # Return if this module was aleady added for another subroutine
    if fort_mod.name in mod_dict:
        return mods, mod_dict

    # Read file
    needed_mods = []
    ct = 0
    fn = ifile
    file = open(fn, "r")
    lines = file.readlines()
    file.close()

    fort_mod.num_lines = len(lines)

    # Define regular expressions for catching variables declared in the module
    regex_contains = re.compile(r"^(contains)", re.IGNORECASE)
    user_defined_types = {}  # dictionary to store user-defined types in module

    module_head = True
    while ct < len(lines):
        l, ct = line_unwrapper(lines=lines, ct=ct)
        l = l.strip().lower()
        match_contains = regex_contains.search(l)
        if match_contains:
            module_head = False
            fort_mod.end_of_head_ln = ct
            # Nothing else to check in this line
            ct += 1
            continue

        if module_head:
            # First check if a user-derived type is being defined
            # create new l to simplify regex needed.
            lprime = l.replace("public", "").replace("private", "").replace(",", "")
            match_type_def1 = re.search(r"^(type\s*::)", lprime)  # type :: type_name
            match_type_def2 = re.search(r"^(type\s+)(?!\()", lprime)  # type type_name
            type_name = None
            if match_type_def1:
                # Get type name
                type_name = lprime.split("::")[1].strip()
            elif match_type_def2:
                # Get type name
                matched_expr = match_type_def2.group()
                type_name = lprime.replace(matched_expr, "").strip()
            if type_name:
                # Analyze the type definition
                user_dtype, ct = get_derived_type_definition(
                    ifile=ifile,
                    modname=module_name,
                    lines=lines,
                    ln=ct,
                    type_name=type_name,
                    verbose=verbose,
                )
                user_defined_types[type_name] = user_dtype

            # Check for variable declarations
            variable_list = parse_line_for_variables(
                ifile=ifile, l=l, ln=ct, verbose=verbose,
            )
            # Store variable as Variable Class object and add to Module object
            if variable_list:
                for v in variable_list:
                    v.declaration = module_name
                    fort_mod.global_vars[v.name] = v

        match_use = re.search(r"^(use)[\s]+", l)
        if match_use:
            # Get rid of comma if no space
            templ = l.replace(",", " ")
            mod = templ.split()[1]
            mod = mod.strip()
            mod = mod.lower()
            if mod not in bad_modules:
                fort_mod.add_dependency(mod=mod,line=l,ln=ct)
                lower_mods = [get_module_name_from_file(m)[1] for m in mods] 
                if (
                    mod not in needed_mods
                    and mod not in lower_mods
                    and mod not in ["elm_instmod", "cudafor", "verificationmod"]
                ):
                    needed_mods.append(mod)
        ct += 1

    # Done with first pass through the file.
    # Check against already used Mods
    files_to_parse = []
    for m in needed_mods:
        if m in bad_modules:
            continue
        needed_modfile = get_filename_from_module(m, verbose=verbose)
        if needed_modfile is None:
            if verbose:
                print(
                    f"Couldn't find {m} in ELM or shared source -- adding to removal list"
                )
            bad_modules.append(m)
            regex_modkey = re.compile(rf"{m}@\d+")
            keys_to_remove = [key for key in fort_mod.modules_by_ln if regex_modkey.search(key)]
            for key in keys_to_remove:
                fort_mod.modules_by_ln.pop(key)
        elif needed_modfile not in mods:
            files_to_parse.append(needed_modfile)
            mods.append(needed_modfile)

    # Store user-defined types in the module object
    # and find any global variables that have the user-defined type

    list_type_names = [key for key in user_defined_types.keys()]
    for gvar in fort_mod.global_vars.values():
        if gvar.type in list_type_names:
            if gvar.name not in user_defined_types[gvar.type].instances:
                user_defined_types[gvar.type].instances[gvar.name] = gvar

    fort_mod.defined_types = user_defined_types
    mod_dict[fort_mod.name] = fort_mod
    if ifile not in mods:
        mods.append(ifile)

    # Recursive call to the mods that need to be processed
    if files_to_parse and not singlefile:
        for f in files_to_parse:
            mods, mod_dict = get_used_mods(
                ifile=f,
                mods=mods,
                verbose=verbose,
                singlefile=singlefile,
                mod_dict=mod_dict,
            )

    return mods, mod_dict


def AdjustLine(a, b, c):
    """
    Function to convert adjust cpp ln number after commenting out lines
    in the original file (ie, for line continuations)
    """
    return a + (b - c)


def modify_file(
        lines: list[str],
        fn: str,
        sub_dict: dict[str, Subroutine],
        mod_name: str,
        verbose: bool=False,
        overwrite: bool=False,
):
    """
    Function that modifies the source code of the file
    Occurs after parsing the file for subroutines and modules
    that need to be removed.
    """
    func_name = "modify_file::"

    # Test if the file in question contains any ifdef statements:
    cmd = f'grep -E "ifn?def"  {fn} | grep -v "_OPENACC"'
    output = sp.getoutput(cmd)
    base_fn = fn.split("/")[-1]

    if output:
        # For CPP files, regex operates on the cpp_lines, but only the original lines are commented
        cpp_file = True
        new_fn = f"{spel_output_dir}cpp_{base_fn}"

        # Set up cmd for preprocessing. Get macros used:
        macros_string = "-D" + " -D".join(macros)
        cmd = f"gfortran -I{E3SM_SRCROOT}/share/include {macros_string} -cpp -E {fn} > {new_fn}"
        ier = sp.getoutput(cmd)

        # read lines of preprocessed file
        file = open(new_fn, "r")
        cpp_lines = file.readlines()
        file.close()
    else:
        cpp_file = False
        cpp_lines = lines[:]

    # Flag to keep track if we are currently in a subroutine
    in_subroutine = False

    regex_if = re.compile(r"^(if)[\s]*(?=\()", re.IGNORECASE)
    regex_include_assert = re.compile(r"^(#include)\s+[\"\'](shr_assert.h)[\'\"]")
    regex_sub = re.compile(r"^\s*(subroutine)\s+")
    regex_shr_assert = re.compile(r"^\s*(shr_assert_all|shr_assert)\b")
    regex_end_sub = re.compile(r"^\s*(end subroutine)")

    regex_func = re.compile(r"\b(function)\b")
    regex_end_func = re.compile(r"\s*(end function)\b")

    subname = ""

    subs_removed = []

    # Note: can use grep to get sub_start faster, but
    #       some modules have multiple of the same subroutine
    #       based on ifdef statements.
    sub_start = 0
    if cpp_file:
        eof = len(cpp_lines)
    else:
        eof = len(lines)
    ct = 0
    linenum = 0
    while ct < eof:
        # Adjust if we are looping through compiler preprocessed file
        if cpp_file:
            line = cpp_lines[ct]
            # Function to check if the line is a cpp comment and adjust the line numbers accordingly
            newct, linenum, lines = check_cpp_line(
                base_fn=base_fn,
                og_lines=lines,
                cpp_lines=cpp_lines,
                cpp_ln=ct,
                og_ln=linenum,
                verbose=False,
            )
            # If cpp_line was a comment, increment and analyze next line
            if newct > ct:
                ct = newct
                continue
            cpp_ln = ct
        else:  # not cpp file
            cpp_ln = None
            linenum = ct
            line = lines[ct]

        # Save starting line number to check it comments were applied.
        start_ln_pair = PreProcTuple(cpp_ln=cpp_ln, ln=linenum)

        if not cpp_file:
            l_cont, cont_ct = line_unwrapper(lines=lines, ct=linenum)
        else:
            l_cont, cont_ct = line_unwrapper(lines=cpp_lines, ct=ct)

        l_cont = l_cont.strip().lower()
        if not l_cont:
            linenum += 1
            ct += 1
            continue

        # Perform consistency check, This is only done after checking
        # if the cpp_line is non-empty.  As, some empty cpp_lines are
        # generated by the preprocessor and the og lines are not empty
        if cpp_file:
            if verbose:
                print(f"cpp Ln: {ct} Original Ln: {linenum}")

        # Check for '#include "shr_assert.h"' lines. Note that they are removed for cpp files.
        match_include_assert = regex_include_assert.search(l_cont)
        if match_include_assert:
            lines, newct = comment_line(lines=lines, ct=linenum, verbose=verbose)
            ct = AdjustLine(ct, newct, linenum)
            linenum = newct

        # Match use statements
        bad_mod_string = "|".join(bad_modules)
        bad_mod_string = f"({bad_mod_string})"
        match_use = re.search(
            r"\s*(use)[\s]+{}".format(bad_mod_string), l_cont, re.IGNORECASE
        )

        # Join bad subroutines into single string with logical OR for regex. Commented out if matched.
        bad_sub_string = "|".join(bad_subroutines)
        bad_sub_string = f"({bad_sub_string})"

        # Test if subroutine has started
        match_sub = regex_sub.search(l_cont)

        # Test if a bad subroutine is being called.
        match_call = re.search(
            r"\s*(call)[\s]+{}".format(bad_sub_string), l_cont, re.IGNORECASE
        )
        match_bad_inst = re.search(r"\b({})\b".format(bad_sub_string), l_cont)

        match_assert = regex_shr_assert.search(l_cont)
        match_end = regex_end_sub.search(l_cont)

        match_func = regex_func.search(l_cont)
        match_end_func = regex_end_func.search(l_cont)

        match_gsmap = re.search(r"(gsmap)", l_cont.lower())

        if match_use:
            if ":" in l_cont:
                if cpp_file and verbose:
                    l_dbg, ct_dbg = line_unwrapper(lines=cpp_lines, ct=ct)

                subs = l_cont.split(":")[1]
                subs = subs.rstrip("\n")
                subs = re.sub(r"\b(assignment\(=\))\b", "", subs)
                # Add elements used from the module to be commented out
                subs = subs.split(",")
                for el in subs:
                    if "=>" in el:
                        match_nan = re.search(r"\b(nan)\b", el)
                        if match_nan:
                            el = re.sub(r"\b(nan)\s*(=>)\s*", "", el)
                        else:
                            el = re.sub(r"\s*(=>)\s*", "|", el)
                    el = el.strip().lower()
                    if el not in bad_subroutines:
                        if verbose:
                            print(f"Adding {el} to bad_subroutines")
                            print(f"from {fn} \nline: {l}")
                        bad_subroutines.append(el)
            lines, newct = comment_line(lines=lines, ct=linenum, verbose=verbose)
            ct = AdjustLine(ct, newct, linenum)
            linenum = newct

        elif match_sub:
            if in_subroutine:
                print(
                    f"{func_name}Error - entering subroutine before exiting previous one!"
                )
                print(ct, l_cont)
                if cpp_file:
                    print("og_line:", linenum, lines[linenum])
                sys.exit(1)

            in_subroutine = True
            subname = l_cont.split()[1].split("(")[0]
            interface_list = get_interface_list()
            if subname in interface_list or "_oacc" in subname:
                ct += 1
                linenum += 1
                continue
            if verbose:
                print(f"{func_name}::found subroutine {subname} at {ct+1}")

            if cpp_file:
                sub_start = linenum
                cpp_startline = ct
            else:
                sub_start = ct

            # Check if subroutine needs to be removed before processing
            match_remove = bool(subname.lower() in remove_subs)
            test_init = bool("init" not in subname.lower().replace("initcold", "cold"))

            # Remove if it's an IO routine
            test_nlgsmap = bool("readnl" in subname.lower() or match_gsmap)
            # TODO: Does decompinit_lnd_using_gp still need to be a special case?
            test_decompinit = bool(subname.lower() == "decompinit_lnd_using_gp")
            if (match_remove and test_init) or test_nlgsmap or test_decompinit:
                if verbose:
                    print(f"Removing subroutine {subname}")
                if cpp_file:
                    ln_pair = PreProcTuple(cpp_ln=ct, ln=linenum)
                else:
                    ln_pair = PreProcTuple(cpp_ln=None, ln=linenum)

                lines, endline_pair = remove_subroutine(
                    og_lines=lines, cpp_lines=cpp_lines, start=ln_pair
                )
                if endline_pair.ln == 0:
                    print("Error: subroutine has no end!")
                    sys.exit(1)
                if cpp_file:
                    ct = endline_pair.cpp_ln
                    linenum = endline_pair.ln
                else:
                    ct = endline_pair.ln
                    linenum = ct
                subs_removed.append(subname)
                in_subroutine = False
        elif match_call:
            # Subroutine is calling a subroutine that needs to be removed
            lines, newct = comment_line(lines=lines, ct=linenum, verbose=verbose)
            ct = AdjustLine(ct, newct, linenum)
            linenum = newct
            if verbose:
                print(f"{func_name}::Matched sub call to remove: {l}")

        elif match_bad_inst:
            # Found an instance of something used by a "bad" module
            if verbose:
                print(f"{func_name}::Removing usage of {match_bad_inst.group()}")
            # Check if any thing used from a module that is to be removed
            match_if = regex_if.search(l_cont)
            match_decl = find_variables.search(l_cont)
            if not match_use and not match_decl:
                # Check if the bad element is in an if statement. If so, need to remove the entire if statement.
                if match_if:
                    ct, linenum = check_if_block(
                        start_ln_pair,
                        lines,
                        cpp_lines,
                        base_fn,
                        verbose=verbose,
                    )

                else:
                    lines, newct = comment_line(
                        lines=lines, ct=linenum, verbose=verbose
                    )
                    ct = AdjustLine(ct, newct, linenum)
                    linenum = newct
            elif match_decl and not in_subroutine:
                lines, newct = comment_line(lines=lines, ct=linenum, verbose=verbose)
                ct = AdjustLine(ct, newct, linenum)
                linenum = newct
        elif match_gsmap:
            if verbose:
                print("Removing gsmap ")
            lines, newct = comment_line(lines=lines, ct=linenum, verbose=verbose)
            ct = AdjustLine(ct, newct, linenum)
            linenum = newct

        elif match_assert:
            lines, newct = comment_line(lines=lines, ct=ct)
            ct = AdjustLine(ct, newct, linenum)
            linenum = newct

        elif match_end:
            if not in_subroutine:
                print(
                    f"{func_name}::ERROR: Matched subroutine end without matching the start!"
                )
                print(cpp_file, f"@Line {ct}: {l_cont}")
                sys.exit(1)
            in_subroutine = False

            if subname not in sub_dict:
                if cpp_file:
                    endline = linenum
                    cpp_endline = ct
                else:
                    endline = ct
                    new_fn = None
                    cpp_startline = None
                    cpp_endline = None

                if verbose:
                    print(
                        f"{func_name}::Instantiating Subroutine {subname} at "
                        + f"L{sub_start}-{endline} in {base_fn}"
                    )


                mod_lines: list[str] = lines[:] if not cpp_file else cpp_lines[:]
                sub = Subroutine(
                    name=subname,
                    mod_name=mod_name,
                    file=fn,
                    calltree=[""],
                    mod_lines=mod_lines,
                    start=sub_start,
                    end=endline,
                    cpp_start=cpp_startline,
                    cpp_end=cpp_endline,
                    cpp_fn=new_fn,
                )

                sub_dict[subname] = sub

            else:
                if verbose:
                    print(f"{func_name}::Subroutine {subname} already in sub_dict")
        elif match_func and not match_end_func:
            if in_subroutine:
                print(f"{func_name}::Error-Encountered function decl in subroutine!")
                print(l_cont)
                sys.exit(1)
            in_subroutine = True
            if cpp_file:
                sub_start = linenum
                cpp_startline = ct
            else:
                sub_start = ct
            func_init = check_function_start(l_cont, start_ln_pair, verbose)

        elif match_end_func:
            if not in_subroutine:
                print(f"{func_name}::ERROR - Matched function end without the start!")
                print("cpp:", cpp_file, f"@Line {ct}: {l_cont}")
                sys.exit(1)
            in_subroutine = False

            mod_lines: list[str] = lines[:] if not cpp_file else cpp_lines[:]
            create_function(fn, start_ln_pair, func_init, sub_dict, mod_lines, mod_name, verbose,)

        # Check if anything was commented out:
        if "!#py" in lines[start_ln_pair.ln]:
            if verbose:
                print(f"{func_name}::Commented out: ")
                stop_ln = linenum
                for i in range(start_ln_pair.ln, stop_ln + 1):
                    print(i, lines[i].rstrip("\n"))
        else:
            # adjust for line continuation:
            ct = cont_ct
            if cpp_file:
                linenum = AdjustLine(linenum, cont_ct, start_ln_pair.cpp_ln)
            else:
                linenum = ct
        linenum += 1
        ct += 1

    return sub_dict


def process_for_unit_test(
    fname: str,
    case_dir: str,
    mod_dict: dict[str, FortranModule],
    mods: list[str]=[],
    required_mods=[],
    main_sub_dict={},
    overwrite=False,
    verbose=False,
    singlefile=False,
):
    """
    This function looks at the whole .F90 file.
    Comments out functions that are cumbersome
    for unit testing purposes.
    Gets module dependencies of the module and
    process them recursively.

    Arguments:
        fname -> File path for .F90 file that with needed subroutine
        case_dir -> label of Unit Test
        mods     -> list of already known (if any) files that were previously processed
        required_mods -> list of modules that are required for the unit test (see mod_config.py)
        main_sub_dict -> dictionary of all subroutines encountered for the unit test.
        verbose  -> Print more info
        singlefile -> flag that disables recursive processing.
    """
    func_name = "process_for_unit_test"

    sub_dict = main_sub_dict.copy()

    initial_mods = mods.copy()
    # First, get complete list of module to be processed and removed.
    # and then add processed file to list of mods:
    if not mods:
        lower_mods = [m.lower() for m in mods]
        if fname.lower() not in lower_mods:
            mods.append(fname)
    else:
        lower_mods = []

    with profile_ctx(enabled=False, section="get_used_mods") as pc:
        # Find if this file has any not-processed mods
        if not singlefile:
            mods, mod_dict = get_used_mods(
                ifile=fname,
                mods=mods,
                verbose=verbose,
                singlefile=singlefile,
                mod_dict=mod_dict,
            )

    required_mod_paths = [get_filename_from_module(m) for m in required_mods]
    for rmod in required_mod_paths:
        if rmod not in mods:
            mods.append(rmod)
            mods, mod_dict = get_used_mods(
                ifile=rmod,
                mods=mods,
                verbose=verbose,
                singlefile=singlefile,
                mod_dict=mod_dict,
            )


    for fort_mod in mod_dict.values():
        fort_mod.modules = fort_mod.sort_module_deps(startln=0,endln=fort_mod.num_lines)
        fort_mod.head_modules = fort_mod.sort_module_deps(startln=0,endln=fort_mod.end_of_head_ln)

    # Sort the file dependencies
    with profile_ctx(enabled=False, section="sort_file_dependency") as pc:
        linenumber, unit_test_module = get_module_name_from_file(fpath=fname)
        file_list = sort_file_dependency(mod_dict, unit_test_module)
        if verbose:
            print("Newly added mods after processing required mods:")
            new_mods = [m.split("/")[-1] for m in mods if m not in initial_mods]
            print( new_mods)

    # Next, each needed module is parsed for subroutines and removal of
    # any dependencies that are not needed for an ELM unit test (eg., I/O libs,...)
    # Note:
    #    Modules are parsed starting with leaf nodes to decrease the likelihood of
    #    a child subroutine not having been instantiated
    with profile_ctx(enabled=False,section="modify_file") as pc:
        for mod_file in file_list:
            _, mod_name = get_module_name_from_file(mod_file)
            # Avoid preprocessing files over and over
            if mod_dict[mod_name].modified:
                continue
            file = open(mod_file, "r")
            lines = file.readlines()
            file.close()
            sub_dict = modify_file(
                lines,
                mod_file,
                sub_dict,
                mod_name,
                verbose=verbose,
                overwrite=overwrite,
            )
            mod_dict[mod_name].modified = True
            if overwrite:
                out_fn = mod_file
                if verbose:
                    print("Writing to file:", out_fn)
                with open(out_fn, "w") as ofile:
                    ofile.writelines(lines)

    # Transfer subroutines to main dictionary
    for subname, sub in sub_dict.items():
        if subname not in main_sub_dict:
            main_sub_dict[subname] = sub

    if verbose:
        print(f"File list for Unit Test: {case_dir}")
        for f in file_list:
            print(f)

    return mod_dict, file_list, main_sub_dict


def remove_reference_to_subroutine(lines, subnames):
    """
    Given list of subroutine names, this function goes back and
    comments out declarations and other references
    """
    sname_string = "|".join(subnames)
    sname_string = f"({sname_string})"
    print(f"remove reference to {sname_string}")
    ct = 0
    while ct < len(lines):
        line = lines[ct]
        l = line.split("!")[0]  # don't search comments
        if not l.strip():
            ct += 1
            continue
        match = re.search(sname_string.lower(), l.lower())
        if match:
            lines, ct = comment_line(lines=lines, ct=ct)
        ct += 1
    return lines


def sort_file_dependency(mod_dict, unittest_module, file_list=[], verbose=False):
    """
    Function that unravels a dictionary of all module files
    that were parsed in process_for_unit_test.

    Each element of the dictionary is a FortranModule object.
    """
    # Start with the module that we want to test
    main_fort_mod = mod_dict[unittest_module]

    for mod in main_fort_mod.modules.keys():
        if mod in bad_modules:
            continue

        # Get module instance from dictionary
        dependency_mod = mod_dict[mod]
        if dependency_mod.filepath in file_list:
            continue

        # This module has no other dependencies, add to list
        if not dependency_mod.modules and dependency_mod.filepath not in file_list:
            file_list.append(dependency_mod.filepath)
            continue

        # Test to see if all of its dependencies are in the file list
        for dep_mod in dependency_mod.modules:
            if mod in bad_modules:
                continue

            # Check if module dependencies are already in the file list
            if mod_dict[dep_mod].filepath not in file_list:
                if verbose:
                    print(f"Switching to {dep_mod} to get its dependencies")
                dep_file_list = sort_file_dependency(
                    mod_dict, unittest_module=dep_mod, file_list=file_list
                )

                if verbose:
                    print(f"New dependency list: {dep_file_list}")
                    print(f"Current list is:\n{file_list}")
        # Since all of its dependencies are in the file list, add the module to the list
        if dependency_mod.filepath not in file_list:
            file_list.append(dependency_mod.filepath)

    if main_fort_mod.filepath not in file_list:
        file_list.append(main_fort_mod.filepath)

    return file_list
