from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("autocomplete/", views.autocomplete, name="autocomplete"),
    path("modules_calltree", views.modules_calltree, name="modules_calltree"),
    path("subroutine_calltree", views.view_table, name="subroutine_calltree"),
    path("subcall/", views.subcall, name="subcall"),
    path("table/<str:table_name>", views.view_table, name="view_table"),
    path("query/<str:table_name>", views.fake, name="spec"),
    path("query", views.query, name="query"),
    path(
        "subroutine-details/<str:subroutine_name>/",
        views.subroutine_details,
        name="subroutine_details",
    ),
    path(
        "type-details/<str:type_name>/",
        views.type_details,
        name="type_details",
    ),
]
