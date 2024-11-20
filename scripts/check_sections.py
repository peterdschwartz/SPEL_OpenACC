import re

from utilityFunctions import check_cpp_line, comment_line, line_unwrapper


def AdjustLine(a, b, c):
    """
    Function to convert adjust cpp ln number after commenting out lines
    in the original file (ie, for line continuations)
    """
    return a + (b - c)


def check_if_block(
    ct,
    lines,
    og_ln,
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

            if cpp_lines:
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
