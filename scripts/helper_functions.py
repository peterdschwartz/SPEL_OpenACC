from __future__ import annotations

import re
import sys
from dataclasses import asdict
from pprint import pprint
from typing import TYPE_CHECKING, Optional

from scripts.mod_config import _bc
from scripts.utilityFunctions import Variable

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

import scripts.dynamic_globals as dg
from scripts.DerivedType import DerivedType, get_component
from scripts.fortran_parser.evaluate import (check_keyword,
                                             parse_subroutine_call)
from scripts.types import (ArgLabel, CallDesc, CallTree, CallTuple, LineTuple,
                           ReadWrite, SubroutineCall)

regex_paren = re.compile(r"\((.+)\)")  # for removing array of struct index
regex_bounds = re.compile(r"(?<=(\w|\s))\(.+?\)")
regex_in_paren = re.compile(r"(?<=\()(.+)(?=\))") # doesn't capture parentheses
regex_alloc = re.compile(r"allocate\s*")


def is_derived_type(var: Variable) -> bool:
    """
    Returns if var is a derived type or not
    """
    intrinsic_types = ["real", "integer", "character", "logical"]
    return var.type not in intrinsic_types


def sub_soa(name: str) -> str:
    inst, field = name.split("%")
    inst = regex_paren.sub("(index)", inst)
    return f"{inst}%{field}"


def check_field_access(
    var: Variable,
    line: str,
) -> list[str]:
    """
    Checks if var is used directly or one of its fields.
    Also if var is an array.
    """
    regex_field = re.compile(rf"{var.name}(?:\(\w+\))?%\w+")
    matches = set(regex_field.findall(line))

    return [sub_soa(m) for m in matches]

def check_allocate_stmt(line: str,varname: str,ln:int)-> ReadWrite:
    """
    determines if varname is var being allocated (output) or dimension var (input)
    Note: line has already subsituted out the allocate\\s* string
    """
    temp = regex_in_paren.search(line).group().strip()
    if not temp:
        print("Error -- couldn't check allocate stmt:",line)
        sys.exit(1)
    m_dim = regex_paren.search(temp)
    if m_dim:
        dim_str = m_dim.group()
        temp = temp.replace(dim_str,"")
    if varname in temp:
        return ReadWrite('w',ln)
    elif varname in dim_str:
        return ReadWrite('r',ln)
    else:
        print(f"Error -- couldn't assign status to {varname}\n",line)
        sys.exit(1)



def analyze_sub_variables(
    sub: Subroutine,
    sub_dict: dict[str, Subroutine],
    var_dict: dict[str, Variable],
    mode: ArgLabel,
    verbose: bool = False,
) -> dict[str, list[ReadWrite]]:
    """ """
    func_name = "analyze_sub_variables"

    vars_to_match: list[str] = [arg for arg in var_dict]

    var_match_string = "|".join(vars_to_match)
    regex_vars = re.compile(r"\b({})\b".format(var_match_string), re.IGNORECASE)

    fileinfo = sub.get_file_info()

    lines = sub.sub_lines[:]
    if fileinfo.startln == lines[0].ln:
        lines = lines[1:]
    else:
        lines = [ lpair for lpair in lines if lpair.ln >= fileinfo.startln ]

    matched_lines = [
        line for line in filter(lambda x: regex_vars.search(x.line), lines)
    ]

    args_accessed: dict[str, list[ReadWrite]] = {}
    for line in matched_lines:
        match_call: bool = line.ln in sub.sub_call_desc
        match_var_use: list[str] = regex_vars.findall(line.line)
        if not match_call:
            match_var_use = list(set(match_var_use))
            line_accessed = determine_variable_status(
                match_var_use,
                line,
                var_dict,
                verbose=verbose,
            )

            for arg, status in line_accessed.items():
                args_accessed.setdefault(arg, []).extend(status)
        else:
            # Check arguments of child subroutines for dummy args of parent (sub.
            call_desc = sub.sub_call_desc[line.ln]
            subname: str = call_desc.fn
            child_sub: Subroutine = sub_dict[subname]
            arg_status = check_arguments(call_desc, child_sub, mode=mode)
            for arg, status in arg_status.items():
                args_accessed.setdefault(arg, []).append(status)

    return args_accessed


def determine_variable_status(
    matched_variables: list[str],
    lpair: LineTuple,
    var_dict: dict[str, Variable],
    verbose: bool = False,
) -> dict[str, list[ReadWrite]]:
    """
    Function that loops through each var in match_variables and
    determines the ReadWrite status.
    """
    func_name = "determine_variable_status::"
    line = lpair.line
    ln = lpair.ln
    match_assignment = re.search(r"(?<![><=/])=(?![><=])", line)
    match_doif = re.search(r"[\s]*(do |if[\s]*\(|else[\s]*if[\s]*\()", line)
    regex_indices = re.compile(r"(?<=\()(.+)(?=\))")
    match_alloc = regex_alloc.search(line)

    find_variables = re.search(
        r"^(class\s*\(|type\s*\(|integer|real|logical|character)", line
    )

    vars_access: dict[str, list[ReadWrite]] = {}
    if verbose:
        print("line: ", line)
        print("vars: ", matched_variables)
        print("assignment:", match_assignment)
        print("doif:", match_doif)

    for m_var in matched_variables[:]:
        var = var_dict[m_var]
        if is_derived_type(var):
            var_with_field = check_field_access(var, line)
            matched_variables.extend(var_with_field)

    for var_name in matched_variables:
        if var_name in vars_access:
            continue
        is_decl = False
        rw_status: Optional[ReadWrite] = None
        if find_variables:
            is_decl = True
            temp_line = line
            is_bounds = False
            m_bounds = regex_bounds.search(temp_line)
            while m_bounds:
                is_bounds = re.search(rf"\b{var_name}\b",m_bounds.group())
                if is_bounds:
                    rw_status = ReadWrite("r", ln)
                    vars_access.setdefault(var_name, []).append(rw_status)
                temp_line = temp_line.replace(m_bounds.group(), "")
                m_bounds = regex_bounds.search(temp_line)

        # if the variables are in an if or do statement, they are read
        if match_doif:
            rw_status = ReadWrite("r", ln)
            vars_access.setdefault(var_name, []).append(rw_status)
        elif match_alloc:
            temp = regex_alloc.sub("",line)
            rw_status = check_allocate_stmt(line=temp,ln=ln,varname=var_name)
            vars_access.setdefault(var_name,[]).append(rw_status)
        elif match_assignment:
            m_start = match_assignment.start()
            m_end = match_assignment.end()
            lhs = line[:m_start]
            rhs = line[m_end:]
            # Check if variable is on lhs or rhs of assignment
            # Note: don't use f-strings as they will not work with regex
            regex_var = re.compile(r"\b({})\b".format(var_name), re.IGNORECASE)
            match_rhs = regex_var.search(rhs)
            # For LHS, remove any indices and check if variable is still present
            # if present in indices, store as read-only
            indices = regex_indices.search(lhs)
            if indices:
                match_index = regex_var.search(indices.group())
            else:
                match_index = None
            match_lhs = regex_var.search(lhs)

            if match_lhs and not match_rhs:
                if match_index:
                    rw_status = ReadWrite("r", ln)
                else:
                    rw_status = ReadWrite("w", ln)
                vars_access.setdefault(var_name, []).append(rw_status)
            elif match_rhs and not match_lhs:
                rw_status = ReadWrite("r", ln)
                vars_access.setdefault(var_name, []).append(rw_status)
            elif match_lhs and match_rhs:
                rw_status = ReadWrite("rw", ln)
                vars_access.setdefault(var_name, []).append(rw_status)

        if not rw_status and not is_decl:
            print(f"{func_name}::ERROR Couldn't identify rw_status for {var_name}")
            print("line:", line)
            sys.exit(1)

    return vars_access



def check_arguments(
    call_desc: CallDesc,
    child_sub: Subroutine,
    mode: ArgLabel,
) -> dict[str, ReadWrite]:
    """
    Function check a subroutine call for given list of variables, and
    assigns a ReadWrite Status to them.
       * if an variable is apart of a nested expression: they are read-only
       * if variable is unnested, the inherit the read-write status of the corresponding
            dummy argument for the child subroutine
    """
    var_status: dict[str, ReadWrite] = {}
    call_ln = call_desc.ln

    match mode:
        case ArgLabel.dummy:
            vars_in_arguments = {v.var.name: v for v in call_desc.dummy_args}
        case ArgLabel.globals:
            vars_in_arguments = {v.var.name: v for v in call_desc.globals}
        case ArgLabel.locals:
            vars_in_arguments = {v.var.name: v for v in call_desc.locals}

    for argvar in vars_in_arguments.values():
        if argvar.node.nested_level > 0:
            var_status[argvar.var.name] = ReadWrite(status="r", ln=call_ln)
        else:
            keyword = check_keyword(argvar.node)
            if keyword:
                dummy_arg = argvar.node.node["Left"]
            else:
                argn = argvar.node.argn
                dummy_arg = child_sub.dummy_args_list[argn]
            dummy_status = child_sub.arguments_read_write[dummy_arg]
            var_status[argvar.var.name] = ReadWrite(dummy_status.status, ln=call_ln)

    return var_status


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

def combine_status(s1: str, s2: str) -> str:
    # Convert each status string to a set of permissions
    perms = set(s1) | set(s2)
    # Return 'rw' if both permissions are present; otherwise 'r' or 'w'
    return ''.join(sorted(perms))

def summarize_read_write_status(var_access:dict[str,list[ReadWrite]]):
    """
    Function that takes the raw ReadWrite status for given variables
    and returns a dict of variables with only one overall ReadWrite Status
    """
    summary = {}
    for varname, values in var_access.items():
        status_list = [v.status for v in values]
        if status_list[0] == 'w':
            summary[varname] = "w"
        elif status_list[0] == 'r':
            if ('w' in status_list[1:]
                    or 'rw' in status_list[1:]):
                summary[varname] = "rw"
            else:
                summary[varname] = 'r'
        elif status_list[0] == 'rw':
            summary[varname] = 'rw'

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
            call_desc.aggregate_vars()
            sub.sub_call_desc[call_desc.ln] = call_desc

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
