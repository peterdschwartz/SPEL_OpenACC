from __future__ import annotations

import re
import sys
from pprint import pprint
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

import scripts.dynamic_globals as dg
from scripts.DerivedType import DerivedType
from scripts.fortran_parser.evaluate import parse_subroutine_call
from scripts.log_functions import list_print
from scripts.mod_config import _bc
from scripts.types import CallDesc, CallTree, CallTuple, ReadWrite, SubroutineCall


def determine_variable_status(
    matched_variables: list[str],
    line: str,
    ct: int,
    dtype_accessed: dict[str, list[ReadWrite]],
    verbose: bool = False,
):
    """
    Function that loops through each var in match_variables and
    determines the ReadWrite status.
    """
    func_name = "determine_variable_status::"
    match_assignment = re.search(r"(?<![><=/])=(?![><=])", line)
    match_doif = re.search(r"[\s]*(do |if[\s]*\(|else[\s]*if[\s]*\()", line)
    regex_indices = re.compile(r"(?<=\()(.+)(?=\))")

    find_variables = re.search(
        r"^(class\s*\(|type\s*\(|integer|real|logical|character)", line
    )
    vars_added = {}
    if verbose:
        print("line: ", line)
        print("vars: ", matched_variables)
        print("assignment:", match_assignment)
        print("doif:", match_doif)
    # Loop through each derived type and determine rw status.
    for dtype in matched_variables:
        if dtype in vars_added:
            continue
        rw_status = None
        if find_variables:
            rw_status = ReadWrite("r", ct)
            dtype_accessed.setdefault(dtype, []).append(rw_status)

        # if the variables are in an if or do statement, they are read
        if match_doif:
            rw_status = ReadWrite("r", ct)
            dtype_accessed.setdefault(dtype, []).append(rw_status)
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

        if not rw_status:
            print(f"{func_name}::ERROR Couldn't identify rw_status for {dtype}")
            print("line:", line)
            sys.exit(1)

        vars_added[dtype] = rw_status

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


def determine_argvar_status(
    vars_as_arguments: dict[str, str],
    subname: str,
    sub_dict: dict[str, Subroutine],
    linenum: int,
    verbose: bool = False,
):
    """
    Function goes through a subroutine to classify their arguments as read,write status
    Inputs:
        vars_as_arguments : { 'dummy_arg' : 'global variable'}
    """
    func_name = "determine_argvar_status"

    # First go through the child subroutines and analyze arguments if not already done.
    child_sub = sub_dict[subname]
    if not child_sub.arguments_read_write:
        child_sub.parse_arguments(sub_dict, verbose=verbose)

    # Filter out unused arguments:
    inactive_args_to_remove = [
        arg
        for arg in vars_as_arguments.keys()
        if arg not in child_sub.arguments_read_write
    ]
    vars_as_arguments = {
        darg: gv
        for darg, gv in vars_as_arguments.items()
        if darg not in inactive_args_to_remove
    }

    # Update the global variables with the status of their corresponding dummy args
    updated_var_status = {
        gv: child_sub.arguments_read_write[dummy_arg]
        for dummy_arg, gv in vars_as_arguments.items()
    }
    # Update the line number to be line child_sub is called in parent.
    updated_var_status = {
        gv: [ReadWrite(status=val.status, ln=linenum)]
        for gv, val in updated_var_status.items()
    }

    return updated_var_status


def summarize_read_write_status(var_access, map_names=[]):
    """
    Function that takes the raw ReadWrite status for given variables
    and returns a dict of variables with only one overall ReadWrite Status

    """
    summary = {}
    for varname, values in var_access.items():
        status_list = [v.status for v in values]
        num_uses = len(status_list)
        num_reads = status_list.count("r")
        num_writes = status_list.count("w")
        if num_uses == num_reads:
            summary[varname] = "r"
        elif num_uses == num_writes:
            summary[varname] = "w"
        else:
            summary[varname] = "rw"

    return summary


def trace_derived_type_arguments(
    parent_sub: Subroutine, child_sub: Subroutine, verbose: bool = False
):
    """
    Function will check if the parent passed it's own argument to the child.
        parent_sub : Subroutine, child_sub: Subroutine
    """
    func_name = "trace_derived_type_arguments"
    subcalls_by_parent: list[SubroutineCall] = [
        subcall
        for subcall in child_sub.subroutine_call
        if subcall.subname == parent_sub.name
    ]

    passed_args = {}
    intrinsic_types = ["real", "integer", "character", "logical", "complex"]
    for subcall in subcalls_by_parent:
        for ptrobj in subcall.args:
            dummy_arg = ptrobj.ptr
            arg = ptrobj.obj
            temp = {
                dummy_arg: var.name
                for var in parent_sub.Arguments.values()
                if var.name == arg and var.type not in intrinsic_types
            }
            passed_args.update(temp)

    child_sub.elmtype_r = replace_elmtype_arg(passed_args, child_sub.elmtype_r)
    child_sub.elmtype_w = replace_elmtype_arg(passed_args, child_sub.elmtype_w)
    child_sub.elmtype_rw = replace_elmtype_arg(passed_args, child_sub.elmtype_rw)

    return None


def replace_elmtype_arg(passed_args, elmtype):
    """
    Function replaces entries in elmtype that are dummy_args of the child
    with the variable passed by the parent.

    passed_args = { dummy_arg (in child_sub) : arg (in parent_sub) }
    elmtype = { "inst%member" : <status> }
    """
    func_name = "replace_elmtype_arg::"

    for global_var in list(elmtype.keys()):
        inst_var, member = global_var.split("%")
        if inst_var in passed_args.keys():
            new_var = passed_args[inst_var] + "%" + member
            elmtype[new_var] = elmtype.pop(global_var)

    return elmtype


def replace_ptr_with_targets(elmtype, type_dict, insts_to_type_dict, use_c13c14=False):
    """
    Function that replaces any pointers with their potential targets
    Arguments:
        * elmtype : dictionary of inst%member : status
        * type_dict : dictionary of type definitions
        * insts_to_type_dict : dict to map udt instance name to type
    """

    if not use_c13c14:
        c13c14 = re.compile(r"(c13|c14)")
    else:
        print("Warning need to double check c13/c14 consistency!")
        sys.exit(0)

    for gv in list(elmtype.keys()):
        if "%" not in gv:
            continue
        inst_name, member_name = gv.split("%")
        if "bounds" in inst_name:
            continue
        type_name = insts_to_type_dict[inst_name]
        dtype = type_dict[type_name]
        member = dtype.components[member_name]
        if member["var"].pointer:
            member["active"] = True
            status = elmtype.pop(gv)
            if not use_c13c14:
                targets_to_add = {
                    target: status
                    for target in member["var"].pointer
                    if not c13c14.search(target)
                }
                elmtype.update(targets_to_add)

    return elmtype


def find_child_subroutines(
    sub: Subroutine,
    sub_dict: dict[str, Subroutine],
    instance_dict: dict[str, DerivedType],
) -> None:
    """
    Function that populates Subroutine fields that require
    looking up in main dictionaries
    """
    lines = sub.sub_lines

    regex_call = re.compile(r"^\s*(call)\b")
    matches = [line for line in filter(lambda x: regex_call.search(x.line), lines)]

    for call_line in matches:
        call_desc = parse_subroutine_call(
            sub=sub,
            sub_dict=sub_dict,
            input=call_line,
            ilist=dg.interface_list,
            instance_dict=instance_dict,
        )
        if call_desc:
            key = f"{call_desc.alias}@L{call_desc.ln}"
            call_desc.aggregate_vars()
            sub.sub_call_desc[key] = call_desc
            if call_desc.alias == "tridiagonal":
                pprint(call_desc.to_dict(), sort_dicts=False)

    return


def construct_call_tree(
    sub: Subroutine,
    sub_dict: dict[str, Subroutine],
    dtype_dict: dict[str, DerivedType],
    nested: int,
) -> list[CallTuple]:
    """
    Function that constructs a CallTree for the input subroutine
    """

    for childsub in sub.child_subroutines.values():
        if childsub.preprocessed or childsub.library:
            continue
        childsub.collect_var_and_call_info(sub_dict, dtype_dict)

    flat_call_list: list[CallTuple] = [
        CallTuple(
            nested=nested,
            subname=sub.name,
        )
    ]

    for childsub in sub.child_subroutines.values():
        if childsub.library:
            continue
        child_list = construct_call_tree(
            childsub,
            sub_dict,
            dtype_dict,
            nested + 1,
        )
        flat_call_list.extend(child_list)
    sub.abstract_call_tree = make_call_tree(flat_call_list)

    return flat_call_list


def make_call_tree(flat_calls: list[CallTuple]) -> CallTree:
    """
    Build a subroutine call tree from a flat list of CallTuple
    Assumes the first tuple is the root.
    """
    root = CallTree(flat_calls[0])
    stack = [(flat_calls[0].nested, root)]

    for call in flat_calls[1:]:
        node_tree = CallTree(call)
        # Pop from stack until we find the parent
        while stack and stack[-1][0] >= call.nested:
            stack.pop()
        if stack:
            parent_tree = stack[-1][1]
            parent_tree.add_child(node_tree)
        stack.append((call.nested, node_tree))

    return root


def check_nested_and_unnested_global_args(call_desc: CallDesc):
    """
    Function that goes through the global variables passed into
    a subroutine call.
    If the variable is not nested, then the variable
    will inherit the rw status of the dummy arg.
    If the variable is nested, then the variable is read-only.
    """
    unnested = [v for v in call_desc.globals if v.node.nested_level == 0]
    return
