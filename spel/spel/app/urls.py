from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("modules_calltree", views.modules_calltree, name="modules_calltree"),
    path("subroutine_calltree", views.subroutine_calltree, name="subroutine_calltree"),
    path("table/<str:table_name>", views.view_table, name="view_table"),
    path("query/<str:table_name>", views.fake, name="spec"),
    path("query", views.query, name="query"),
]
