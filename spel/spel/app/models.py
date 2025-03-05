from django.db import models
from django.db.models import UniqueConstraint


class Modules(models.Model):
    objects = models.Manager()
    module_id = models.AutoField(primary_key=True)
    module_name = models.CharField(unique=True, max_length=100)

    class Meta:
        db_table = "modules"


class ModuleDependency(models.Model):
    objects = models.Manager()
    dependency_id = models.AutoField(primary_key=True)
    module = models.ForeignKey("Modules", on_delete=models.CASCADE)
    dep_module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="moduledependency_dep_module_set",
    )
    object_used = models.CharField(max_length=100)

    class Meta:
        db_table = "module_dependency"
        constraints = [
            UniqueConstraint(
                fields=("module", "dep_module", "object_used"), name="unique_mod_dep"
            ),
        ]


class UserTypes(models.Model):
    objects = models.Manager()
    user_type_id = models.AutoField(primary_key=True)
    module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="user_type_module",
    )
    user_type_name = models.CharField(unique=True, max_length=100)

    class Meta:
        db_table = "user_types"
        constraints = [
            UniqueConstraint(fields=("module", "user_type_name"), name="unique_types")
        ]


class TypeDefinitions(models.Model):
    objects = models.Manager()
    define_id = models.AutoField(primary_key=True)
    type_module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="type_def_module",
    )
    user_type = models.ForeignKey(
        "UserTypes",
        on_delete=models.CASCADE,
        related_name="user_type_def",
    )
    member_type = models.CharField(max_length=100)
    member_name = models.CharField(max_length=100)
    dim = models.IntegerField()
    bounds = models.CharField(max_length=100)

    class Meta:
        db_table = "type_definitions"
        unique_together = (("user_type", "member_type", "member_name", "type_module"),)


class UserTypeInstances(models.Model):
    objects = models.Manager()
    instance_id = models.AutoField(primary_key=True)
    inst_module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="instance_module",
    )
    instance_type = models.ForeignKey(
        "UserTypes",
        on_delete=models.CASCADE,
        related_name="instance_type",
    )
    instance_name = models.CharField(max_length=100)

    class Meta:
        db_table = "user_type_instances"
        constraints = [
            UniqueConstraint(
                fields=("inst_module", "instance_type", "instance_name"),
                name="unique_instances",
            )
        ]


class Subroutines(models.Model):
    objects = models.Manager()
    subroutine_id = models.AutoField(primary_key=True)
    subroutine_name = models.CharField(max_length=100)
    module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="subroutine_module",
    )

    class Meta:
        db_table = "subroutines"
        constraints = [
            UniqueConstraint(fields=("subroutine_name", "module"), name="unique_subs")
        ]

    def __str__(self):
        return f"{self.subroutine_name}"


class SubroutineArgs(models.Model):
    objects = models.Manager()
    arg_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(
        "Subroutines",
        models.CASCADE,
        related_name="subroutine_args",
    )
    arg_type = models.CharField(max_length=100)
    arg_name = models.CharField(max_length=100)
    dim = models.IntegerField()

    class Meta:
        db_table = "subroutine_args"
        constraints = [
            UniqueConstraint(
                fields=("subroutine", "arg_type", "arg_name", "dim"),
                name="unique_sub_args",
            ),
        ]


class SubroutineCalltree(models.Model):
    objects = models.Manager()
    parent_id = models.AutoField(primary_key=True)
    parent_subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        related_name="parent_subroutine",
    )
    child_subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        related_name="child_subroutine",
    )

    class Meta:
        db_table = "subroutine_calltree"
        constraints = [
            UniqueConstraint(
                fields=("parent_subroutine", "child_subroutine"), name="unique_calltree"
            ),
        ]


class SubroutineLocalArrays(models.Model):
    objects = models.Manager()
    local_arry_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        related_name="subroutine_locals",
    )
    array_name = models.CharField(max_length=100)
    dim = models.IntegerField()

    class Meta:
        db_table = "subroutine_local_arrays"
        constraints = [
            UniqueConstraint(
                fields=("subroutine", "array_name"), name="unique_sub_locals"
            ),
        ]


class SubroutineActiveGlobalVars(models.Model):
    objects = models.Manager()
    variable_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        related_name="subroutine_dtype_vars",
    )
    instance = models.ForeignKey(
        "UserTypeInstances",
        on_delete=models.CASCADE,
        related_name="active_instances",
    )
    member = models.ForeignKey(
        "TypeDefinitions",
        on_delete=models.CASCADE,
        related_name="active_member",
    )
    status = models.CharField(max_length=2)

    class Meta:
        db_table = "subroutine_active_global_vars"
        constraints = [
            UniqueConstraint(
                fields=("subroutine", "instance", "member", "status"),
                name="unique_sub_dtype",
            )
        ]
