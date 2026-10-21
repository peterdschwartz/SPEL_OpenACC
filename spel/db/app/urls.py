from django.contrib.auth import views as auth_views
from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.home, name="home"),
    # pickers (HTMX)
    path("snapshots/picker/", views.snapshot_picker, name="snapshot_picker"),
    path("snapshots/select/", views.select_snapshot, name="select_snapshot"),
    path("configs/picker/", views.config_picker, name="config_picker"),
    path("configs/select/", views.select_config_htmx, name="select_config_htmx"),
    path("configs/values/", views.nml_values, name="nml_values"),
    # search (HTMX)
    path("sub_search/", views.sub_active_search, name="sub_active_search"),
    path("var_search/", views.var_active_search, name="var_active_search"),
    # routines
    path("sub_view/<str:sub_name>", views.sub_view, name="sub_view"),
    path("calltree/<str:sub_name>", views.render_calltree, name="calltree"),
    path("subroutine-details/<str:sub_name>/", views.subroutine_details, name="subroutine_details"),
    # types, modules, variables
    path("types/", views.types_view, name="types"),
    path("types/<str:type_name>/", views.type_detail, name="type_detail"),
    path("modules/", views.modules_view, name="modules"),
    path("modules/graph/", views.modgraph_view, name="modgraph"),
    path("modules/<str:module_name>/", views.module_detail, name="module_detail"),
    path("variables/", views.variables_view, name="variables"),
    path("variables/<int:state_id>/override/", views.set_override, name="set_override"),
    # tracing and graphs
    path("trace_view/", views.trace_view, name="trace_view"),
    path("trace/", views.trace_vars, name="trace"),
    path("picker/", views.picker, name="picker"),
    path("types/<str:type_name>/members/", views.type_members, name="type_members"),
    path("calltree_view/", views.calltree_view, name="calltree_view"),
    path("diff/", views.diff_view, name="diff"),
    path("diff/<str:tab>/", views.diff_tab, name="diff_tab"),
    # JSON for d3
    path("api/timeline/", api.timeline, name="api_timeline"),
    path("api/calltree/", api.calltree, name="api_calltree"),
    path("api/modgraph/", api.modgraph, name="api_modgraph"),
    path("api/flag/<str:var_name>/", api.flag_impact, name="api_flag"),
    # namelist configurations
    path("configs/", views.config_start, name="config_start"),
    path("configs/new/", views.new_config, name="new_config"),
    path("configs/<int:config_id>/", views.config_editor, name="config_editor"),
    path("configs/<int:config_id>/set/<str:var_name>/", views.set_config_value, name="set_config_value"),
    # accounts
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.SignupView.as_view(), name="signup"),
]
