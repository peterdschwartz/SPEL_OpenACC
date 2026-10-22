"""
Database schema of the ELM explorer.

Every exported table belongs to a Snapshot (one analysis of one E3SM checkout);
tables that hang off a Subroutine, UserTypes, ... inherit it through their
parent, the hot tables carry their own `snapshot` FK for cheap filtering.
Line numbers are 0-based, as in SPEL. Rows are loaded from `spel export`'s
CSVs by `manage.py update_all_data <dir>` (management/loaders.py).
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

from .utils.helper import compute_config_hash

NAME = 128
PATH = 255

CATEGORIES = [
    ("prognostic", "prognostic"),
    ("diagnostic", "diagnostic"),
    ("intermediate", "intermediate"),
    ("input", "input"),
    ("unused", "unused"),
]


class Snapshot(models.Model):
    """One exported analysis: an E3SM checkout at a commit, analyzed by a SPEL commit."""

    objects = models.Manager()
    snapshot_id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=NAME, unique=True)
    srcroot = models.CharField(max_length=PATH, blank=True, default="")
    e3sm_commit = models.CharField(max_length=64, blank=True, default="")
    e3sm_branch = models.CharField(max_length=NAME, blank=True, default="")
    elm_diff = models.CharField(max_length=64, blank=True, default="")
    spel_commit = models.CharField(max_length=64, blank=True, default="")
    spel_branch = models.CharField(max_length=NAME, blank=True, default="")
    analysis_created_at = models.DateTimeField(null=True, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    loaded_at = models.DateTimeField(null=True, blank=True)
    case = models.CharField(max_length=NAME, blank=True, default="")
    roots = models.JSONField(default=list)
    trace_roots = models.JSONField(default=list)
    failures = models.JSONField(default=dict)
    incomplete = models.JSONField(default=dict)
    stats = models.JSONField(default=dict)

    class Meta:
        db_table = "snapshots"
        ordering = ["-loaded_at"]

    def __str__(self):
        return self.label


class Modules(models.Model):
    objects = models.Manager()
    module_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="modules")
    module_name = models.CharField(max_length=NAME)
    filepath = models.CharField(max_length=PATH, blank=True, default="")
    ln = models.IntegerField(default=0)
    end_of_head_ln = models.IntegerField(default=0)
    default_private = models.BooleanField(default=False)

    class Meta:
        db_table = "modules"
        constraints = [UniqueConstraint(fields=("snapshot", "module_name"), name="unique_module")]

    def __str__(self):
        return f"Module(name={self.module_name})"


class Subroutines(models.Model):
    objects = models.Manager()
    subroutine_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="subroutines")
    subroutine_name = models.CharField(max_length=NAME)
    # "module::name"; library stubs (no source) are "lib::name" with module NULL
    sub_id = models.CharField(max_length=PATH)
    module = models.ForeignKey(
        Modules, on_delete=models.CASCADE, related_name="subroutine_module", null=True, blank=True
    )
    is_function = models.BooleanField(default=False)
    return_type = models.CharField(max_length=NAME, blank=True, default="")
    result_name = models.CharField(max_length=NAME, blank=True, default="")
    filepath = models.CharField(max_length=PATH, blank=True, default="")
    startline = models.IntegerField(default=-1)
    endline = models.IntegerField(default=-1)
    end_stmt_ln = models.IntegerField(default=-1)
    library = models.BooleanField(default=False)
    is_internal = models.BooleanField(default=False)
    host = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="internal_subs", null=True, blank=True
    )
    analyzed = models.BooleanField(default=False)
    failure = models.TextField(blank=True, default="")
    incomplete = models.TextField(blank=True, default="")

    class Meta:
        db_table = "subroutines"
        constraints = [UniqueConstraint(fields=("snapshot", "sub_id"), name="unique_subs")]
        indexes = [models.Index(fields=["snapshot", "subroutine_name"])]

    def __str__(self):
        return f"{self.subroutine_name}"


class SubroutineCode(models.Model):
    """The routine's source text (original file lines startline..end_stmt_ln)."""

    objects = models.Manager()
    subroutine = models.OneToOneField(Subroutines, on_delete=models.CASCADE, related_name="code")
    startline = models.IntegerField()
    n_lines = models.IntegerField()
    text = models.TextField()

    class Meta:
        db_table = "subroutine_code"

    def line(self, ln: int) -> str:
        lines = self.text.split("\n")
        i = ln - self.startline
        return lines[i] if 0 <= i < len(lines) else ""


class ModuleDependency(models.Model):
    """One `use` statement item: `use dep_module, only: local_name => object_used`."""

    objects = models.Manager()
    dependency_id = models.AutoField(primary_key=True)
    module = models.ForeignKey(Modules, on_delete=models.CASCADE)
    dep_module = models.ForeignKey(
        Modules,
        on_delete=models.CASCADE,
        related_name="moduledependency_dep_module_set",
        null=True,
        blank=True,  # a module SPEL did not load (netcdf, mpi, ...)
    )
    dep_module_name = models.CharField(max_length=NAME)
    object_used = models.CharField(max_length=NAME, blank=True, default="")  # "" for a whole use
    local_name = models.CharField(max_length=NAME, blank=True, default="")
    ln = models.IntegerField(default=-1)
    whole = models.BooleanField(default=False)
    in_head = models.BooleanField(default=True)
    subroutine = models.ForeignKey(
        Subroutines, on_delete=models.CASCADE, related_name="uses", null=True, blank=True
    )

    class Meta:
        db_table = "module_dependency"
        indexes = [models.Index(fields=["module"]), models.Index(fields=["dep_module"])]


class UserTypes(models.Model):
    objects = models.Manager()
    user_type_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="user_types")
    module = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="user_type_module")
    user_type_name = models.CharField(max_length=NAME)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, related_name="extensions", null=True, blank=True
    )

    class Meta:
        db_table = "user_types"
        constraints = [UniqueConstraint(fields=("snapshot", "user_type_name"), name="unique_types")]

    def __str__(self):
        return f"UserType(mod={self.module.module_name},type={self.user_type_name})"


class TypeDefinitions(models.Model):
    """A component of a derived type; `member_name` is its path (`leaf`, `core%leaf`)."""

    objects = models.Manager()
    define_id = models.AutoField(primary_key=True)
    type_module = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="type_def_module")
    user_type = models.ForeignKey(UserTypes, on_delete=models.CASCADE, related_name="user_type_def")
    member_type = models.CharField(max_length=NAME)
    member_name = models.CharField(max_length=PATH)
    dim = models.IntegerField()
    bounds = models.CharField(max_length=PATH, blank=True, default="")
    subgrid = models.CharField(max_length=1, blank=True, default="")  # p c l t g
    pointer = models.BooleanField(default=False)
    allocatable = models.BooleanField(default=False)
    nested = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    component_type = models.ForeignKey(
        UserTypes, on_delete=models.SET_NULL, related_name="embedded_in", null=True, blank=True
    )

    class Meta:
        db_table = "type_definitions"
        constraints = [UniqueConstraint(fields=("user_type", "member_name"), name="unique_type_member")]

    def __str__(self):
        return f"{self.user_type.user_type_name}%{self.member_name}"


class TypeProcedure(models.Model):
    """A type-bound procedure (`procedure :: init => veg_cf_init`)."""

    objects = models.Manager()
    user_type = models.ForeignKey(UserTypes, on_delete=models.CASCADE, related_name="procedures")
    binding = models.CharField(max_length=NAME)
    subroutine = models.ForeignKey(
        Subroutines, on_delete=models.SET_NULL, related_name="bound_to", null=True, blank=True
    )

    class Meta:
        db_table = "type_procedures"
        constraints = [UniqueConstraint(fields=("user_type", "binding"), name="unique_type_procedure")]


class UserTypeInstances(models.Model):
    objects = models.Manager()
    instance_id = models.AutoField(primary_key=True)
    inst_module = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="instance_module")
    instance_type = models.ForeignKey(UserTypes, on_delete=models.CASCADE, related_name="instance_type")
    instance_name = models.CharField(max_length=NAME)
    public = models.BooleanField(default=True)

    class Meta:
        db_table = "user_type_instances"
        constraints = [
            UniqueConstraint(fields=("inst_module", "instance_type", "instance_name"), name="unique_instances")
        ]

    def __str__(self):
        return f"UserTypeInstance(mod={self.inst_module.module_name},type={self.instance_type.user_type_name},inst={self.instance_name})"


class IntrinsicGlobals(models.Model):
    """A module variable that is not a derived-type instance."""

    objects = models.Manager()
    var_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="globals")
    gv_module = models.ForeignKey(Modules, on_delete=models.CASCADE, related_name="global_var")
    dim = models.IntegerField()
    var_type = models.CharField(max_length=NAME)
    var_name = models.CharField(max_length=NAME)
    bounds = models.CharField(max_length=PATH, blank=True, default="")
    value = models.TextField(blank=True, default="")
    parameter = models.BooleanField(default=False)
    pointer = models.BooleanField(default=False)
    public = models.BooleanField(default=True)
    protected = models.BooleanField(default=False)
    namelist_group = models.CharField(max_length=64, blank=True, default="")
    namelist_kind = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        db_table = "intrinsic_globals"
        constraints = [UniqueConstraint(fields=("gv_module", "var_name"), name="unique_globals")]
        indexes = [models.Index(fields=("snapshot", "var_name"))]

    def __str__(self):
        return f"{self.gv_module.module_name}::{self.var_name}"


class SubroutineArgs(models.Model):
    objects = models.Manager()
    arg_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, models.CASCADE, related_name="subroutine_args")
    position = models.IntegerField(default=0)
    arg_type = models.CharField(max_length=NAME)
    arg_name = models.CharField(max_length=NAME)
    dim = models.IntegerField()
    intent = models.CharField(max_length=5, blank=True, default="")  # in | out | inout
    optional = models.BooleanField(default=False)
    user_type = models.ForeignKey(
        UserTypes, on_delete=models.SET_NULL, related_name="dummy_args", null=True, blank=True
    )

    class Meta:
        db_table = "subroutine_args"
        constraints = [UniqueConstraint(fields=("subroutine", "arg_name"), name="unique_sub_args")]


class SubroutineLocalArrays(models.Model):
    objects = models.Manager()
    local_arry_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="subroutine_locals")
    array_name = models.CharField(max_length=NAME)
    type = models.CharField(max_length=NAME, blank=True, default="")
    dim = models.IntegerField()

    class Meta:
        db_table = "subroutine_local_arrays"
        constraints = [UniqueConstraint(fields=("subroutine", "array_name"), name="unique_sub_locals")]


class SubroutineCalltree(models.Model):
    """A call site: `parent_subroutine` calls `child_subroutine` at `lineno`."""

    objects = models.Manager()
    parent_id = models.AutoField(primary_key=True)
    parent_subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="parent_subroutine")
    child_subroutine = models.ForeignKey(
        Subroutines,
        on_delete=models.CASCADE,
        related_name="child_subroutine",
        null=True,
        blank=True,  # unresolved callee (unknown generic / type-bound target)
    )
    lineno = models.IntegerField()
    position = models.IntegerField(default=0)  # among the calls on that line
    callee_name = models.CharField(max_length=PATH, blank=True, default="")
    kind = models.CharField(max_length=16, default="call")  # call | function | type-bound
    passed_object = models.CharField(max_length=PATH, blank=True, default="")

    class Meta:
        db_table = "subroutine_calltree"
        constraints = [
            UniqueConstraint(fields=("parent_subroutine", "lineno", "position"), name="unique_calltree")
        ]
        indexes = [
            models.Index(fields=["parent_subroutine", "lineno"]),
            models.Index(fields=["child_subroutine"]),
        ]

    def __str__(self):
        child = self.child_subroutine.subroutine_name if self.child_subroutine else self.callee_name
        return f"{self.parent_subroutine.subroutine_name} -> {child} @L{self.lineno}"


class CallsiteBinding(models.Model):
    """An actual argument bound to a dummy at a call site."""

    objects = models.Manager()
    binding_id = models.AutoField(primary_key=True)
    parent_subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="as_binding_parent")
    call = models.ForeignKey(SubroutineCalltree, on_delete=models.CASCADE, related_name="bindings")
    argn = models.IntegerField(default=0)
    dummy_arg = models.ForeignKey(
        SubroutineArgs, on_delete=models.CASCADE, related_name="bindings", null=True, blank=True
    )
    dummy_name = models.CharField(max_length=NAME)
    actual = models.CharField(max_length=PATH)  # path of the actual, as written in the caller
    origin = models.CharField(max_length=16)  # global | dummy | local | associate | host | ...
    keyword = models.CharField(max_length=NAME, blank=True, default="")
    from_elmtype = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="bound_inst", null=True, blank=True
    )
    from_arg = models.ForeignKey(
        SubroutineArgs, on_delete=models.CASCADE, related_name="bound_arg", null=True, blank=True
    )
    from_local = models.ForeignKey(
        SubroutineLocalArrays, on_delete=models.CASCADE, related_name="bound_local", null=True, blank=True
    )

    class Meta:
        db_table = "callsite_binding"
        indexes = [
            models.Index(fields=["call"]),
            models.Index(fields=["dummy_arg"]),
            models.Index(fields=["parent_subroutine", "actual"]),
        ]

    def __str__(self):
        return f"{self.call} {self.dummy_name}={self.actual}"


class SubroutineActiveGlobalVars(models.Model):
    """A direct access of a routine to a derived-type instance component."""

    objects = models.Manager()
    variable_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="subroutine_dtype_vars")
    instance = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="active_instances", null=True, blank=True
    )
    member = models.ForeignKey(
        TypeDefinitions, on_delete=models.CASCADE, related_name="active_member", null=True, blank=True
    )
    path = models.CharField(max_length=PATH)  # as written (local alias of the instance)
    status = models.CharField(max_length=2)
    ln = models.IntegerField(default=-1)

    class Meta:
        db_table = "subroutine_active_global_vars"
        # one line may reach several targets through a pointer component, hence instance/member in the key
        constraints = [UniqueConstraint(fields=("subroutine", "path", "instance", "member", "status", "ln"), name="unique_sub_dtype")]
        indexes = [models.Index(fields=["instance", "member"]), models.Index(fields=["subroutine", "ln"])]


class SubroutineIntrinsicGlobals(models.Model):
    """A direct access of a routine to a module variable."""

    objects = models.Manager()
    sub_gv_id = models.AutoField(primary_key=True)
    gv_id = models.ForeignKey(
        IntrinsicGlobals, on_delete=models.CASCADE, related_name="active_intrinsic", null=True, blank=True
    )
    sub_id = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="subroutine_global_vars")
    path = models.CharField(max_length=PATH, default="")
    status = models.CharField(max_length=2, default="")
    gv_ln = models.IntegerField(default=-1)

    class Meta:
        db_table = "subroutine_intrinsic_globals"
        constraints = [UniqueConstraint(fields=("sub_id", "path", "status", "gv_ln"), name="unique_sub_intrinsic")]
        indexes = [models.Index(fields=["gv_id"]), models.Index(fields=["sub_id", "gv_ln"])]


class ArgAccess(models.Model):
    objects = models.Manager()
    arg_access_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE)
    arg = models.ForeignKey(SubroutineArgs, on_delete=models.CASCADE)
    ln = models.IntegerField()
    status = models.CharField(max_length=2)
    member_path = models.CharField(max_length=PATH, blank=True, default="")  # field1%subfield%...

    class Meta:
        db_table = "arg_access"
        indexes = [
            models.Index(fields=["subroutine", "arg", "ln"]),
            models.Index(fields=["subroutine", "arg", "status"]),
        ]
        constraints = [
            UniqueConstraint(fields=("subroutine", "arg", "ln", "status", "member_path"), name="unique_arg_use_row")
        ]


class PropagatedEffectByLn(models.Model):
    """
    A module-variable access the callee (or its callees) makes, attributed to
    the caller's call line, with the callee's overall status.
    """

    objects = models.Manager()
    prop_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="propagated_effects")
    call_site = models.ForeignKey(
        SubroutineCalltree, on_delete=models.CASCADE, related_name="propagated_call_site", null=True, blank=True
    )
    lineno = models.IntegerField()  # call line in the caller
    kind = models.CharField(max_length=8)  # elmtype | global
    instance = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="propagated_inst", null=True, blank=True
    )
    member = models.ForeignKey(
        TypeDefinitions, on_delete=models.CASCADE, related_name="propagated_member", null=True, blank=True
    )
    global_var = models.ForeignKey(
        IntrinsicGlobals, on_delete=models.CASCADE, related_name="propagated_global", null=True, blank=True
    )
    path = models.CharField(max_length=PATH)  # canonical: module::name%member
    status = models.CharField(max_length=2)

    class Meta:
        db_table = "propagated_access_by_ln"
        indexes = [
            models.Index(fields=["call_site"]),
            models.Index(fields=["subroutine", "lineno"]),
            models.Index(fields=["instance", "member"]),
            models.Index(fields=["global_var"]),
        ]


class NamelistVariable(models.Model):
    objects = models.Manager()
    nml_id = models.AutoField(primary_key=True)
    active_var_id = models.ForeignKey(IntrinsicGlobals, on_delete=models.CASCADE, related_name="namelist")

    class Meta:
        db_table = "namelist_variables"
        constraints = [UniqueConstraint(fields=("active_var_id",), name="unique_nml_var")]


class CascadeDependence(models.Model):
    """E.g. num_pcropp depends on use_crop."""

    objects = models.Manager()
    cascade_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="cascades")
    cascade_var = models.CharField(max_length=NAME)
    trigger_var = models.ForeignKey(NamelistVariable, on_delete=models.CASCADE, related_name="triggers")

    class Meta:
        constraints = [UniqueConstraint(fields=("cascade_var", "trigger_var"), name="unique_dependence")]


class CascadePair(models.Model):
    """A single mapping (nml_val -> cascade_val), e.g. (.false. -> 0), (.true. -> 10)."""

    objects = models.Manager()
    pair_id = models.AutoField(primary_key=True)
    dependence = models.ForeignKey(CascadeDependence, on_delete=models.CASCADE, related_name="pairs")
    nml_val = models.CharField(max_length=64)
    cascade_val = models.CharField(max_length=64)

    class Meta:
        constraints = [UniqueConstraint(fields=("dependence", "nml_val", "cascade_val"), name="unique_pair")]


class FlatIf(models.Model):
    """
    One branch of an if construct with its full path condition (enclosing
    guards and-ed in, earlier branches negated). `nml_gated` branches mention a
    namelist or cascade variable and are evaluated per configuration.
    """

    objects = models.Manager()
    flatif_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="flat_ifs")
    position = models.IntegerField(default=0)
    start_ln = models.IntegerField()
    end_ln = models.IntegerField()
    kind = models.CharField(max_length=8, default="IF")  # IF | ELSEIF | ELSE | SIMPLE
    condition = models.JSONField(null=True, blank=True)
    condition_text = models.TextField(blank=True, default="")
    nml_gated = models.BooleanField(default=False)

    class Meta:
        db_table = "flat_if_blocks"
        constraints = [UniqueConstraint(fields=("subroutine", "position"), name="unique_ifs")]
        indexes = [models.Index(fields=["subroutine", "start_ln", "end_ln"])]


class FlatIfNamelistVar(models.Model):
    objects = models.Manager()
    id = models.AutoField(primary_key=True)
    flatif = models.ForeignKey(FlatIf, on_delete=models.CASCADE)
    namelist_var = models.ForeignKey(NamelistVariable, on_delete=models.CASCADE)

    class Meta:
        db_table = "flat_if_namelist"
        constraints = [UniqueConstraint(fields=("flatif", "namelist_var"), name="unique_flatif_var")]


class FlatIFCascadeVar(models.Model):
    objects = models.Manager()
    cv_if_id = models.AutoField(primary_key=True)
    flatif_cv = models.ForeignKey(FlatIf, on_delete=models.CASCADE)
    cascade = models.ForeignKey(CascadeDependence, on_delete=models.CASCADE)

    class Meta:
        db_table = "flat_if_cascade"
        constraints = [UniqueConstraint(fields=("flatif_cv", "cascade"), name="uniq_flatif_cascade")]


class Registration(models.Model):
    """A `hist_addfld*` (kind hist) or `restartvar` (kind restart) call."""

    objects = models.Manager()
    registration_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="registrations")
    kind = models.CharField(max_length=8)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="registrations")
    ln = models.IntegerField()
    base = models.CharField(max_length=NAME)  # `this`, an instance or a bare variable
    field = models.CharField(max_length=PATH, blank=True, default="")
    user_type = models.ForeignKey(
        UserTypes, on_delete=models.CASCADE, related_name="registrations", null=True, blank=True
    )
    member = models.ForeignKey(
        TypeDefinitions, on_delete=models.CASCADE, related_name="registrations", null=True, blank=True
    )
    instance = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="registrations", null=True, blank=True
    )
    global_var = models.ForeignKey(
        IntrinsicGlobals, on_delete=models.CASCADE, related_name="registrations", null=True, blank=True
    )
    name = models.CharField(max_length=PATH, blank=True, default="")  # history field / restart varname
    long_name = models.CharField(max_length=PATH, blank=True, default="")
    units = models.CharField(max_length=NAME, blank=True, default="")
    guards = models.JSONField(default=list)
    inactive = models.BooleanField(default=False)

    class Meta:
        db_table = "registrations"
        indexes = [
            models.Index(fields=["member"]),
            models.Index(fields=["instance"]),
            models.Index(fields=["snapshot", "kind"]),
        ]


class TraceNode(models.Model):
    """
    A node of the static call tree from elm_drv, flattened in execution
    (preorder) order; `[order, order+size)` is the node's subtree.
    """

    objects = models.Manager()
    node_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="trace_nodes")
    order = models.IntegerField()
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="children", null=True, blank=True)
    call_site = models.ForeignKey(
        SubroutineCalltree, on_delete=models.CASCADE, related_name="trace_nodes", null=True, blank=True
    )
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="trace_nodes")
    depth = models.IntegerField()
    size = models.IntegerField(default=1)
    cut = models.BooleanField(default=False)  # recursion: emitted, not expanded
    analyzed = models.BooleanField(default=True)

    class Meta:
        db_table = "trace_nodes"
        constraints = [UniqueConstraint(fields=("snapshot", "order"), name="unique_trace_order")]
        indexes = [models.Index(fields=["subroutine"]), models.Index(fields=["snapshot", "depth"])]


class TraceAccess(models.Model):
    """A read/write of a module variable (or instance field) along the step trace."""

    objects = models.Manager()
    access_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="trace_accesses")
    trace_node = models.ForeignKey(TraceNode, on_delete=models.CASCADE, related_name="accesses")
    instance = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="trace_accesses", null=True, blank=True
    )
    member = models.ForeignKey(
        TypeDefinitions, on_delete=models.CASCADE, related_name="trace_accesses", null=True, blank=True
    )
    global_var = models.ForeignKey(
        IntrinsicGlobals, on_delete=models.CASCADE, related_name="trace_accesses", null=True, blank=True
    )
    path = models.CharField(max_length=PATH)  # canonical module::name%member
    status = models.CharField(max_length=2)  # r | w | rw
    ln = models.IntegerField()
    order = models.IntegerField()  # sequence across the whole trace
    resolved_from = models.CharField(max_length=8, default="global")  # global | dummy | pointer
    conditional = models.BooleanField(default=False)  # inside a plain if block, or called from one
    index_kind = models.CharField(max_length=8, default="")  # form of the subgrid subscript: filter | whole | range | map | ...
    filter = models.CharField(max_length=128, default="")  # filter%lakec when indexed by an element of a resolved filter, else ""

    class Meta:
        db_table = "trace_access"
        indexes = [
            models.Index(fields=["snapshot", "order"]),
            models.Index(fields=["instance", "member", "order"]),
            models.Index(fields=["global_var", "order"]),
            models.Index(fields=["trace_node"]),
        ]


class FilterSet(models.Model):
    """A member of a `clumpfilter` instance the step fills: where, over what, and under which conditions."""

    objects = models.Manager()
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="filters")
    name = models.CharField(max_length=64)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="built_filters", null=True, blank=True)
    ln = models.IntegerField(default=0)
    level = models.CharField(max_length=8, default="")  # index variable assigned: c, p, l, ...
    parent = models.CharField(max_length=64, default="")  # filter the building loop runs over
    guards = models.TextField(default="")

    class Meta:
        db_table = "filters"
        constraints = [UniqueConstraint(fields=("snapshot", "name"), name="unique_filter_name")]


class FilterRelation(models.Model):
    """`filter_a` disjoint from / subset of `filter_b`, derived from the building sites (or curated)."""

    objects = models.Manager()
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="filter_relations")
    filter_a = models.CharField(max_length=64)
    filter_b = models.CharField(max_length=64)
    relation = models.CharField(max_length=8)  # disjoint | subset
    source = models.CharField(max_length=8)  # if/else | nested | parent | closure | curated
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, related_name="filter_relations", null=True, blank=True)
    condition = models.TextField(default="")

    class Meta:
        db_table = "filter_relations"
        indexes = [models.Index(fields=["snapshot", "relation"])]


class FieldState(models.Model):
    """
    Per instance field (or module variable): registration facts, first access
    in the step, and the derived category. `override` is a manual correction.
    """

    objects = models.Manager()
    state_id = models.AutoField(primary_key=True)
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="field_states")
    instance = models.ForeignKey(
        UserTypeInstances, on_delete=models.CASCADE, related_name="field_states", null=True, blank=True
    )
    member = models.ForeignKey(
        TypeDefinitions, on_delete=models.CASCADE, related_name="field_states", null=True, blank=True
    )
    global_var = models.ForeignKey(
        IntrinsicGlobals, on_delete=models.CASCADE, related_name="field_states", null=True, blank=True
    )
    restart = models.BooleanField(default=False)
    history = models.BooleanField(default=False)
    history_active = models.BooleanField(default=False)
    first_status = models.CharField(max_length=2, blank=True, default="")
    first_trace_node = models.ForeignKey(
        TraceNode, on_delete=models.SET_NULL, related_name="first_accesses", null=True, blank=True
    )
    first_ln = models.IntegerField(null=True, blank=True)
    read_in_step = models.BooleanField(default=False)
    written_in_step = models.BooleanField(default=False)
    n_reads = models.IntegerField(default=0)
    n_writes = models.IntegerField(default=0)
    n_routines = models.IntegerField(default=0)
    category = models.CharField(max_length=16, choices=CATEGORIES)
    restart_unneeded = models.BooleanField(default=False)
    restart_missing = models.BooleanField(default=False)
    override = models.CharField(max_length=16, choices=CATEGORIES, blank=True, default="")
    override_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "field_state"
        constraints = [
            UniqueConstraint(fields=("snapshot", "instance", "member"), name="unique_field_state_member"),
            UniqueConstraint(fields=("snapshot", "global_var"), name="unique_field_state_global"),
        ]
        indexes = [models.Index(fields=["snapshot", "category"])]

    @property
    def effective_category(self) -> str:
        return self.override or self.category

    @property
    def key(self) -> str:
        if self.instance_id:
            return f"{self.instance.instance_name}%{self.member.member_name}"
        return self.global_var.var_name


User = get_user_model()


class ConfigProfile(models.Model):
    """A user's namelist configuration: overrides keyed by namelist variable name."""

    objects = models.Manager()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="configs")
    name = models.CharField(max_length=NAME)
    data = models.JSONField(default=dict)
    user_hash = models.CharField(max_length=64, db_index=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "config_profile"
        indexes = [models.Index(fields=["owner", "user_hash"])]
        constraints = [UniqueConstraint(fields=["owner", "name"], name="uniq_configprofile_name_per_owner")]

    def save(self, *args, **kwargs):
        self.user_hash = compute_config_hash(self.data)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"user_hash"}
        super().save(*args, **kwargs)


class PresetConfig(models.Model):
    """A named namelist configuration (a COMPSET's `lnd_in` values), keyed by variable name."""

    objects = models.Manager()
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=NAME)
    data = models.JSONField(default=dict)
    preset_hash = models.CharField(max_length=64, db_index=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "preset_configs"
        indexes = [models.Index(fields=["preset_hash"])]

    def save(self, *args, **kwargs):
        self.preset_hash = compute_config_hash(self.data)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"preset_hash"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class IfEvaluationByHash(models.Model):
    """Whether a namelist-gated FlatIf is active under a configuration (by hash), per snapshot."""

    objects = models.Manager()
    snapshot = models.ForeignKey(Snapshot, on_delete=models.CASCADE, related_name="if_evaluations")
    config_hash = models.CharField(max_length=64, db_index=True)
    flatif = models.ForeignKey(FlatIf, on_delete=models.CASCADE)
    subroutine = models.ForeignKey(Subroutines, on_delete=models.CASCADE, db_index=True)
    start_ln = models.IntegerField()
    end_ln = models.IntegerField()
    is_active = models.BooleanField()
    last_used_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "if_eval_by_hash"
        constraints = [UniqueConstraint(fields=["config_hash", "flatif"], name="uniq_if_eval_hash_flatif")]
        indexes = [
            models.Index(fields=["snapshot", "config_hash", "subroutine", "is_active"]),
        ]
