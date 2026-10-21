"""CSV table names and columns shared by the exporter and the Django loader."""

SNAPSHOT_JSON = "snapshot.json"

# Booleans are written as 0/1, missing foreign keys as "", JSON columns as JSON text.
# Line numbers are 0-based (as everywhere in SPEL). A routine is identified by its
# `sub_id` ("module::name", library stubs "lib::name"); a module variable by
# (module, name); a type component by (user_type_name, member_name path).
TABLES: dict[str, list[str]] = {
    "modules": ["module", "filepath", "ln", "end_of_head_ln", "default_private"],
    "module_deps": [
        "module", "dep_module", "ln", "whole", "local_name", "object_used", "in_head", "subroutine",
    ],
    "user_types": ["module", "user_type_name", "parent"],
    "type_defs": [
        "user_type_name", "member_name", "member_type", "dim", "bounds", "subgrid",
        "pointer", "allocatable", "nested", "position", "component_type",
    ],
    "type_procedures": ["user_type_name", "binding", "subroutine"],
    "user_type_instances": ["module", "user_type_name", "instance_name", "public"],
    "intrinsic_globals": [
        "module", "var_name", "var_type", "dim", "bounds", "value", "parameter", "pointer",
        "public", "protected", "namelist_group", "namelist_kind",
    ],
    "subroutines": [
        "module", "subroutine", "sub_id", "is_function", "return_type", "result_name",
        "filepath", "startline", "endline", "end_stmt_ln", "library", "is_internal", "host",
        "analyzed", "failure", "incomplete",
    ],
    "subroutine_code": ["sub_id", "startline", "n_lines", "text"],
    "subroutine_args": [
        "sub_id", "position", "arg_name", "arg_type", "dim", "intent", "optional", "user_type",
    ],
    "subroutine_local_arrays": ["sub_id", "array_name", "type", "dim"],
    "subroutine_calltree": [
        "parent", "ln", "position", "callee_name", "kind", "passed_object", "child",
    ],
    "call_bindings": ["parent", "ln", "position", "argn", "dummy_arg", "actual", "origin", "keyword"],
    # SubroutineActiveGlobalVars: direct accesses to derived-type instance components
    "active_dtype_vars": ["sub_id", "path", "inst_module", "instance", "member", "status", "ln"],
    # SubroutineIntrinsicGlobals: direct accesses to other module variables
    "intrinsic_access": ["sub_id", "path", "var_module", "var_name", "status", "ln"],
    "arg_access": ["sub_id", "dummy_arg", "member_path", "status", "ln"],
    # PropagatedEffectByLn: callee accesses attributed to the caller's call line
    "propagated_access": [
        "sub_id", "ln", "position", "path", "kind", "inst_module", "instance", "member",
        "var_module", "var_name", "status",
    ],
    "nml_ifs": [
        "sub_id", "position", "start_ln", "end_ln", "kind", "condition", "condition_text", "nml_gated",
    ],
    "flat_if_vars": ["sub_id", "position", "role", "var_module", "var_name"],
    "cascades": ["cascade_var", "trigger_module", "trigger_name", "nml_val", "cascade_val"],
    "registrations": [
        "sub_id", "ln", "kind", "base", "field", "user_type", "inst_module", "instance", "member",
        "var_module", "var_name", "name", "long_name", "units", "guards", "inactive",
    ],
    "trace_nodes": [
        "order", "parent_order", "caller", "call_ln", "call_position", "subroutine", "depth",
        "size", "cut", "analyzed",
    ],
    "trace_access": [
        "node_order", "path", "inst_module", "instance", "member", "var_module", "var_name",
        "status", "ln", "order", "resolved_from", "conditional",
    ],
    "field_state": [
        "inst_module", "instance", "member", "var_module", "var_name", "restart", "history",
        "history_active", "first_status", "first_node_order", "first_ln", "read_in_step",
        "written_in_step", "n_reads", "n_writes", "n_routines", "category", "restart_unneeded",
        "restart_missing",
    ],
}

CATEGORIES = ("prognostic", "diagnostic", "intermediate", "input", "unused")
