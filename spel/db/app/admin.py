from django.contrib import admin

from .models import ConfigProfile, FieldState, PresetConfig, Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("label", "e3sm_branch", "e3sm_commit", "loaded_at", "case")
    readonly_fields = ("stats", "failures", "incomplete", "roots", "trace_roots")


@admin.register(PresetConfig)
class PresetAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_default", "preset_hash")


@admin.register(ConfigProfile)
class ConfigProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "user_hash", "created_at")


@admin.register(FieldState)
class FieldStateAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "instance", "member", "global_var", "category", "override")
    list_filter = ("snapshot", "category", "restart", "history")
    search_fields = ("member__member_name", "global_var__var_name", "instance__instance_name")
