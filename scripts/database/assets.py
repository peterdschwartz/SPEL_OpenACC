
TYPE_DEFAULT_DICT = {
    "table": "user_types",
    "id": "",
    "module": "",
    "type_name": "",
    "member": "",
    "member_type": "",
    "dim": "",
    "bounds": "",
    "active": ""
}

MODS_DEFAULT_DICT = {
    "table": "subroutine_active_global_vars",
    "id": "",
    "subroutine": "",
    "variable_name": "",
    "status": "",
}

MOD_DEPENDENCY_DEFAULT_DICT = {
    "table": "module_dependency",
    "id": "",
    "module_name": "",
    "dependency": "",
    "object_used": "",
}

VARS_DEFAULT_DICT = {
    "table": "variables",
    "id": "",
    "module": "",
    "name": "",
    "type": "",
    "dim": "",
}

TABLE_NAME_LOOKUP = {
    "subroutine_active_global_vars": MODS_DEFAULT_DICT,
    "user_types": TYPE_DEFAULT_DICT,
    "module_dependency": MOD_DEPENDENCY_DEFAULT_DICT,
    "variables": VARS_DEFAULT_DICT
}