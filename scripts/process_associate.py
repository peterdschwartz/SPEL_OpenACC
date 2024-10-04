import re
import sys

from utilityFunctions import line_unwrapper


def getAssociateClauseVars(sub, verbose=False):
    """
    Funtion to extract the associated variables in a subroutine
    """
    func_name = "getAssociateClauseVars"

    subroutine_name = sub.name
    if sub.cpp_startline:
        subroutine_start_line = sub.cpp_startline
        subroutine_end_line = sub.cpp_endline
        fn = sub.cpp_filepath
    else:
        subroutine_start_line = sub.startline
        subroutine_end_line = sub.endline
        fn = sub.filepath

    ifile = open(fn, "r")
    lines = ifile.readlines()
    ifile.close()
    associate_vars = {}
    associate_start = 0
    associate_end = 0
    ct = subroutine_start_line
    while ct < subroutine_end_line:
        line = lines[ct]
        line = line.strip().split("!")[0]
        match = re.search(r"\b(associate)\b(?=\()", line)  # find start of assoicate(
        if match and ct < subroutine_end_line:
            if verbose:
                print(f"{func_name}::matched associate start {match}\n{line}")
            associate_start = ct
            break
        ct = ct + 1

    if verbose:
        print(f"{func_name}::associate start {associate_start} {sub.cpp_startline}")

    if associate_start != 0:
        line, ct = line_unwrapper(lines, ct)
        line = line.strip()
        associate_end = ct
        regex_str = re.compile(r"(?<=\()(.+)(?=\))")
        associate_string = regex_str.search(line).group(0)

        if verbose:
            print(f"{func_name}::{associate_string}")
        regex_remove_index = re.compile(r"(\()(.+)(\))")
        for pair in associate_string.split(","):
            parsed = pair.split("=>")
            # find_ex = the ptr name to find in routine
            # repl_ex = the variable to replace it with
            find_ex = parsed[0].strip()
            repl_ex = parsed[1].strip()
            repl_ex = regex_remove_index.sub("", repl_ex)
            find_ex = find_ex.lower().strip()
            repl_ex = repl_ex.lower().strip()
            if find_ex in associate_vars:
                print(
                    f"{func_name}::Error! Multiple associations for {find_ex} in {subroutine_name}"
                )
                sys.exit(1)
            associate_vars[find_ex] = repl_ex

        if verbose:
            print(f"{func_name}:: Found associate variables for {subroutine_name}")
            for key in associate_vars:
                print(f"{key} => {associate_vars[key]}")

        if verbose:
            sys.exit(1)
    return associate_vars, associate_start, associate_end
