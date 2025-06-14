import re
from pprint import pprint
from typing import NamedTuple

from scripts.analyze_subroutines import Subroutine
from scripts.DerivedType import DerivedType
from scripts.utilityFunctions import Variable


class DtypeVarTuple(NamedTuple):
    inst: str
    var: str
    dim: int


def aggregate_dtype_vars(
    sub_dict: dict[str, Subroutine],
    type_dict: dict[str, DerivedType],
    inst_to_dtype_map: dict[str, str],
):
    """
    Function aggregate_dtype_vars:
        Starting with a unit-test subroutine, traverse it's calltree and set elmtype vars to active
    """
    dtype_info_set: set[DtypeVarTuple] = set()

    unit_test_subs: list[Subroutine] = [
        sub for sub in sub_dict.values() if sub.unit_test_function
    ]

    for sub in unit_test_subs:
        if sub.abstract_call_tree:
            for node in sub.abstract_call_tree.traverse_postorder():
                sub_name = node.node.subname
                node_sub = sub_dict[sub_name]
                set_active_variables(
                    type_dict,
                    inst_to_dtype_map,
                    node_sub.elmtype_access_sum,
                    dtype_info_set,
                )
    check_inst_active_consistency(type_dict)
    set_bounds_active(type_dict, inst_to_dtype_map)
    return


def set_active_variables(
    type_dict: dict[str, DerivedType],
    type_lookup: dict[str, str],
    variable_list: dict[str, str],
    dtype_info_set: set[DtypeVarTuple],
):
    """
    This function sets the active status of the user defined types
    based on variable list
        * type_dict   : dictionary of all user-defined types found in the code
        * type_lookup : dictionary that maps an variable to it's user-defined type
        * variable_list   : list of variables that are used
        * dtype_info_list : list for saving to file (redundant?)
    """
    regex_paren = re.compile(r"\((.+)\)")
    instance_member_vars = [var for var in variable_list if "%" in var]
    for var in instance_member_vars:
        dtype, component = var.split("%")
        dtype = regex_paren.sub("", dtype)
        if "bounds" in dtype or "clumpfilter" in dtype:
            continue
        type_name = type_lookup[dtype]
        type_dict[type_name].active = True
        for field_var in type_dict[type_name].components.values():
            active = field_var.active
            if "%" in field_var.name:
                match = bool(field_var.name == var)
            else:
                match = bool(field_var.name == component)
            if match and not active:
                field_var.active = True
                dtype_info_set.add(
                    DtypeVarTuple(
                        inst=dtype,
                        var=field_var.name,
                        dim=field_var.dim,
                    )
                )

    # Set which instances of derived types are actually used.
    global_vars = {regex_paren.sub("", v.split("%")[0]) for v in instance_member_vars}
    global_vars = list(set(global_vars))
    for var in global_vars:
        if "bounds" == var:
            continue
        type_name = type_lookup[var]
        # Set which instances of the derived type are active
        for inst in type_dict[type_name].instances.values():
            if inst.name == var and not inst.active:
                inst.active = True

    return None


def check_inst_active_consistency(type_dict: dict[str, DerivedType]):
    """ """
    dtypes_with_active_fields = set()
    for dtype in type_dict.values():
        for field_var in dtype.components.values():
            if field_var.active:
                dtypes_with_active_fields.add(dtype.type_name)
    for dtype in type_dict.values():
        for inst in dtype.instances.values():
            if inst.active and dtype.type_name not in dtypes_with_active_fields:
                print(
                    f"WARNING -- {dtype.type_name}::{inst.name} active but no fields are!"
                )

    return


def set_bounds_active(type_dict: dict[str, DerivedType], inst_map: dict[str, str]):
    """
    Need to hard-code bounds info for subgrid initialization?
    """

    regex = re.compile(r"((beg|end)(g|l|t|c|p))\b")

    for field in type_dict["bounds_type"].components.values():
        if regex.match(field.name):
            field.active = True
    type_dict["bounds_type"].instances["bounds"] = Variable(
        type="bounds_type",
        name="bounds",
        dim=0,
        ln=0,
        declaration="decompmod",
        subgrid="?",
        active=True,
    )
    inst_map["bounds"] = "bounds_type"
    return
