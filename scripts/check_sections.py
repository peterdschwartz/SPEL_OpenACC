import re

import scripts.dynamic_globals as dg
from scripts.analyze_subroutines import Subroutine
from scripts.fortran_parser.evaluate import parse_subroutine_call
from scripts.mod_config import spel_output_dir
from scripts.types import FunctionReturn, PreProcTuple
from scripts.utilityFunctions import (
    check_cpp_line,
    comment_line,
    intrinsic_type,
    line_unwrapper,
    split_func_line,
)


def AdjustLine(a, b, c):
    """
    Function to convert adjust cpp ln number after commenting out lines
    in the original file (ie, for line continuations)
    """
    return a + (b - c)


def check_function_start(
    line: str,
    ln_pair: PreProcTuple,
    verbose: bool = False,
):
    """
    Function to parse function start for result type and name
    """

    func_name = "check_function_start::"

    split_line = split_func_line(line)
    regex = re.compile(r"(?<=\()[\w\s,]+(?=\))")

    func_type, func_keyword, func_rest = split_line
    if func_type:
        # Definition:  <function type> function <name>(<args>)
        if "type" in func_type:
            func_type = regex.search(func_type).group()
        else:
            func_type = intrinsic_type.search(func_type).group()
        func_name = func_rest.split("(")[0].strip()
        func_result = func_name
    else:
        # is it worth getting this here or after local variables are parsed?
        func_type = ""
        func_name = func_rest.split("(")[0].strip()
        # Definition: function <name>(<args>) result(<result>) || function <name>(<args>)
        args_and_res = regex.findall(func_rest)
        args_and_res = [v.strip() for v in args_and_res]
        if len(args_and_res) == 2:
            args, func_result = args_and_res
        else:
            func_result = func_name.strip()

    return FunctionReturn(
        return_type=func_type,
        name=func_name,
        result=func_result,
        start_ln=ln_pair.ln,
        cpp_start=ln_pair.cpp_ln,
    )


def create_function(
    fn: str,
    ln_pair: PreProcTuple,
    func_init: FunctionReturn,
    sub_dict: dict[str, Subroutine],
    verbose: bool = False,
):
    """
    Function to instantiate function if not in sub_dict
    """
    func_name = "create_function::"
    if ln_pair.cpp_ln:
        base_fn = fn.split("/")[-1]
        new_fn = f"{spel_output_dir}cpp_{base_fn}"
    else:
        new_fn = None
    if func_init.name not in sub_dict:
        if verbose:
            print(f"{func_name}Adding Function {func_init.name}:")
            print(f"{' '*len(func_name)} fn: {fn} ")
            print(f"{' '*len(func_name)} ln: L{func_init.start_ln}-{ln_pair.ln}")
        sub = Subroutine(
            func_init.name,
            fn,
            [""],
            start=func_init.start_ln,
            end=ln_pair.ln,
            cpp_start=func_init.cpp_start,
            cpp_end=ln_pair.cpp_ln,
            cpp_fn=new_fn,
            function=func_init,
        )

        sub_dict[func_init.name] = sub

    return None


def check_if_block(
    ln_pair: PreProcTuple,
    lines,
    cpp_lines,
    base_fn,
    verbose=False,
):
    """
    Function that analyzes an if-block for variables that need to be removed
    Arguments:
        ct : linenumber that is the same as og_ln if not cpp_file
        lines : lines of module
        og_ln : linenumber of ELM sourcefile
        cpp_lines : lines of cpp module
        base_fn : name of file
    """
    if ln_pair.cpp_ln:
        ct = ln_pair.cpp_ln
    else:
        ct = ln_pair.ln

    og_ln = ln_pair.ln
    regex_endif = re.compile(r"^(end\s*if)", re.IGNORECASE)
    regex_ifthen = re.compile(r"^(if)(.+)(then)$", re.IGNORECASE)

    # Get a new line adjusted for continuation lines
    # So that we can match 'if() then' versus just a 'if()'
    l_cont, newct = line_unwrapper(lines=lines, ct=og_ln)
    l_cont = l_cont.strip().lower()

    match_ifthen = regex_ifthen.search(l_cont)
    if match_ifthen:
        if_counter = 1
        match_end_if = regex_endif.search(l_cont)
        lines, newct = comment_line(lines=lines, ct=og_ln, verbose=verbose)
        ct = AdjustLine(ct, newct, og_ln)
        og_ln = newct
        while if_counter > 0:
            ct += 1
            og_ln += 1

            if ln_pair.cpp_ln:
                # Function to check if the line is a cpp comment
                # and adjust the line numbers accordingly
                newct, og_ln, lines = check_cpp_line(
                    base_fn=base_fn,
                    og_lines=lines,
                    cpp_lines=cpp_lines,
                    cpp_ln=ct,
                    og_ln=og_ln,
                    verbose=verbose,
                )
                # If cpp_line was a comment, increment and analyze next line
                if newct > ct:
                    ct = newct
                    continue
            else:
                # not cpp file
                og_ln = ct

            # Get another complete line to check for nested if statements
            l_cont, newct = line_unwrapper(lines=lines, ct=og_ln)
            l_cont = l_cont.strip().lower()
            if not l_cont:
                continue

            match_nested_ifthen = regex_ifthen.search(l_cont)
            match_end_if = regex_endif.search(l_cont)
            if match_nested_ifthen:
                if_counter += 1
            elif match_end_if:
                if_counter -= 1

            lines, newct = comment_line(lines=lines, ct=og_ln, verbose=verbose)
            ct = AdjustLine(ct, newct, og_ln)
            og_ln = newct

    else:  # not match_ifthen
        lines, newct = comment_line(lines=lines, ct=og_ln, verbose=verbose)
        ct = AdjustLine(ct, newct, og_ln)
        og_ln = newct

    return ct, og_ln
