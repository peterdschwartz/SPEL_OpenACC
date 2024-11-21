# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = "auth_group"


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey("AuthPermission", models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "auth_group_permissions"
        unique_together = (("group", "permission"),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey("DjangoContentType", models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = "auth_permission"
        unique_together = (("content_type", "codename"),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "auth_user"


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "auth_user_groups"
        unique_together = (("user", "group"),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "auth_user_user_permissions"
        unique_together = (("user", "permission"),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey(
        "DjangoContentType", models.DO_NOTHING, blank=True, null=True
    )
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = "django_admin_log"


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = "django_content_type"
        unique_together = (("app_label", "model"),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "django_migrations"


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "django_session"


class ModuleDependency(models.Model):
    dependency_id = models.AutoField(primary_key=True, default=1)
    module = models.ForeignKey("Modules", on_delete=models.CASCADE, default=1)
    dep_module = models.ForeignKey(
        "Modules",
        on_delete=models.CASCADE,
        related_name="moduledependency_dep_module_set",
        default=1,
    )
    object_used = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "module_dependency"


class Modules(models.Model):
    module_id = models.AutoField(primary_key=True)
    module_name = models.CharField(unique=True, max_length=100)

    class Meta:
        db_table = "modules"


class SubroutineActiveGlobalVars(models.Model):
    objects = models.Manager()
    variable_id = models.AutoField(primary_key=True, default=1)
    subroutine = models.ForeignKey("Subroutines", on_delete=models.CASCADE, default=1)
    instance = models.ForeignKey(
        "UserTypeInstances", models.DO_NOTHING, blank=True, null=True
    )
    member = models.ForeignKey("TypeDefinitions", models.DO_NOTHING, default=1)
    status = models.CharField(max_length=2, default="xx")

    class Meta:
        db_table = "subroutine_active_global_vars"
        unique_together = (("instance", "member", "subroutine"),)


class SubroutineArgs(models.Model):
    arg_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey("Subroutines", models.CASCADE, default=1)
    arg_type = models.CharField(max_length=100)
    arg_name = models.CharField(max_length=100)
    dim = models.IntegerField()

    class Meta:
        db_table = "subroutine_args"


class SubroutineCalltree(models.Model):
    objects = models.Manager()
    parent_id = models.AutoField(primary_key=True)
    parent_subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        default=1,
    )
    child_subroutine = models.ForeignKey(
        "Subroutines",
        on_delete=models.CASCADE,
        related_name="subroutinecalltree_child_subroutine_set",
        default=1,
    )

    class Meta:
        db_table = "subroutine_calltree"


class SubroutineLocalArrays(models.Model):
    local_arry_id = models.AutoField(primary_key=True)
    subroutine = models.ForeignKey("Subroutines", on_delete=models.CASCADE, default=1)
    array_name = models.CharField(max_length=100)
    dim = models.IntegerField()

    class Meta:
        db_table = "subroutine_local_arrays"


class Subroutines(models.Model):
    subroutine_id = models.AutoField(primary_key=True)
    subroutine_name = models.CharField(unique=True, max_length=100)
    module = models.ForeignKey(Modules, on_delete=models.CASCADE, default=1)

    class Meta:
        db_table = "subroutines"

    def __str__(self):
        return f"{self.subroutine_name}"


class TypeDefinitions(models.Model):
    define_id = models.AutoField(primary_key=True)
    module = models.ForeignKey(Modules, models.DO_NOTHING)
    user_type = models.ForeignKey("UserTypes", models.DO_NOTHING)
    member_type = models.CharField(max_length=100)
    member_name = models.CharField(max_length=100)
    dim = models.IntegerField()
    bounds = models.CharField(max_length=100)
    active = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "type_definitions"
        unique_together = (("user_type", "member_type", "member_name", "module"),)


class UserTypeInstances(models.Model):
    instance_id = models.AutoField(primary_key=True)
    instance_type = models.ForeignKey("UserTypes", models.DO_NOTHING)
    instance_name = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = "user_type_instances"


class UserTypes(models.Model):
    user_type_id = models.AutoField(primary_key=True)
    module = models.ForeignKey(Modules, models.DO_NOTHING)
    user_type_name = models.CharField(unique=True, max_length=100)

    class Meta:
        managed = False
        db_table = "user_types"
