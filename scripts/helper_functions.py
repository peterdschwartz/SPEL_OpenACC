import re
from collections import namedtuple

# Declare namedtuple for readwrite status of variables:
ReadWrite = namedtuple("ReadWrite", ["status", "ln"])


# namedtuple to log the subroutines called and their arguments
# to properly match read/write status of variables.
# SubroutineCall = namedtuple('SubroutineCall',['subname','args'])
# subclass namedtuple to allow overriding equality.
class SubroutineCall(namedtuple("SubroutineCall", ["subname", "args"])):
    def __eq__(self, other):
        return (self.subname == other.subname) and (self.args == other.args)

    def __str__(self):
        return f"{self.subname} ({self.args})"


def determine_variable_status(
    matched_variables, line, ct, dtype_accessed, verbose=False
):
    """
    Function that loops through each var in match_variables and
    determines the ReadWrite status.

    Move to utilityFunctions.py?  Use for loop variable analysis as well?
    """
    func_name = "determine_variable_status"
    # match assignment
    match_assignment = re.search(r"(?<![><=/])=(?![><=])", line)
    # match do and if statements
    match_doif = re.search(r"[\s]*(do |if[\s]*\(|else[\s]*if[\s]*\()", line)
    regex_indices = re.compile(r"(?<=\()(.+)(?=\))")

    # Loop through each derived type and determine rw status.
    for dtype in matched_variables:
        # if the variables are in an if or do statement, they are read
        if match_doif:
            rw_status = ReadWrite("r", ct)
            dtype_accessed.setdefault(dtype, []).append(rw_status)
        # Split line into rhs and lhs of assignment.
        # What if there is no assignment:
        #   1) subroutine call, 2) i/o statement
        # which I think we can safely skip over here
        elif match_assignment:
            m_start = match_assignment.start()
            m_end = match_assignment.end()
            lhs = line[:m_start]
            rhs = line[m_end:]
            # Check if variable is on lhs or rhs of assignment
            # Note: don't use f-strings as they will not work with regex
            regex_var = re.compile(r"\b({})\b".format(dtype), re.IGNORECASE)
            match_rhs = regex_var.search(rhs)
            # For LHS, remove any indices and check if variable is still present
            # if present in indices, store as read-only
            indices = regex_indices.search(lhs)
            if indices:
                match_index = regex_var.search(indices.group())
            else:
                match_index = None
            match_lhs = regex_var.search(lhs)

            # May be overkill to check each combination,
            # but better to capture all information and
            # simplify in a separate function based on use case.
            if match_lhs and not match_rhs:
                if match_index:
                    rw_status = ReadWrite("r", ct)
                else:
                    rw_status = ReadWrite("w", ct)
                dtype_accessed.setdefault(dtype, []).append(rw_status)
            elif match_rhs and not match_lhs:
                rw_status = ReadWrite("r", ct)
                dtype_accessed.setdefault(dtype, []).append(rw_status)
            elif match_lhs and match_rhs:
                rw_status = ReadWrite("rw", ct)
                dtype_accessed.setdefault(dtype, []).append(rw_status)

    return dtype_accessed


def determine_level_in_tree(branch, tree_to_write):
    """
    Will be called recursively
    branch is a list containing names of subroutines
    ordered by level in call_tree
    """
    for j in range(0, len(branch)):
        sub_el = branch[j]
        islist = bool(type(sub_el) is list)
        if not islist:
            if j + 1 == len(branch):
                tree_to_write.append([sub_el, j - 1])
            elif type(branch[j + 1]) is list:
                tree_to_write.append([sub_el, j - 1])
        if islist:
            tree_to_write = determine_level_in_tree(sub_el, tree_to_write)
    return tree_to_write


def add_acc_routine_info(sub):
    """
    This function will add the !$acc routine directive to subroutine
    """
    filename = sub.filepath

    file = open(filename, "r")
    lines = file.readlines()  # read entire file
    file.close()

    first_use = 0
    ct = sub.startline
    while ct < sub.endline:
        line = lines[ct]
        l = line.split("!")[0]
        if not l.strip():
            ct += 1
            continue
            # line is just a commment

        if first_use == 0:
            m = re.search(r"[\s]+(use)", line)
            if m:
                first_use = ct

            match_implicit_none = re.search(r"[\s]+(implicit none)", line)
            if match_implicit_none:
                first_use = ct
            match_type = re.search(r"[\s]+(type|real|integer|logical|character)", line)
            if match_type:
                first_use = ct

        ct += 1
    print(f"first_use = {first_use}")
    lines.insert(first_use, "      !$acc routine seq\n")
    print(f"Added !$acc to {sub.name} in {filename}")
    with open(filename, "w") as ofile:
        ofile.writelines(lines)


def determine_argvar_status(vars_as_arguments, sub_dict):
    """
    go through a subroutine to classify their argument read,write status
    """
    return None
