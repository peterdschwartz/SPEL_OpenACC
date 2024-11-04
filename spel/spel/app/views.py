from django.db import connection, models
from django.shortcuts import HttpResponse, render
from django.views.decorators.http import require_http_methods

from .calltree import get_module_calltree, get_subroutine_calltree
from .models import (
    ModuleDependency,
    Modules,
    SubroutineCalltree,
    Subroutines,
    TypeDefinitions,
    UserTypeInstances,
)

# import module_calltree
TYPE_DEFAULT_DICT = {
    "id": "",
    "module": "",
    "type_name": "",
    "member": "",
    "member_type": "",
    "dim": "",
    "bounds": "",
    "active": "",
}

MODS_DEFAULT_DICT = {
    "id": "",
    "subroutine": "",
    "variable_name": "",
    "status": "",
}

MOD_DEPENDENCY_DEFAULT_DICT = {
    "id": "",
    "module_name": "",
    "dependency": "",
    "object_used": "",
}

VARS_DEFAULT_DICT = {
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
    "variables": VARS_DEFAULT_DICT,
}

VIEWS_TABLE_DICT = {
    "modules": {
        "name": Modules,
        "html": "modules.html",
    },
    "subroutine_calltree": {
        "name": SubroutineCalltree,
        "html": "subroutine_calltree.html",
    },
    "types": {
        "name": TypeDefinitions,
        "html": "types.html",
    },
    "dependency": {
        "name": ModuleDependency,
        "html": "dep.html",
    },
    "instances": {
        "name": UserTypeInstances,
        "html": "instances.html",
    },
}


def query_statement(table_name, **parm_list):

    table = TABLE_NAME_LOOKUP[table_name]

    for parm in parm_list:
        table[parm] = parm_list[parm]

    statement = f"SELECT * FROM {table_name} where "

    for key in table.keys():

        statement += f"{key} like '%'" if not table[key] else f"{key}='{table[key]}'"

        if key != list(table.keys())[-1]:
            statement += " and "

    return statement


def execute(statement):
    with connection.cursor() as cur:
        cur.execute(statement)


def modules_calltree(request):
    if request.method == "POST":
        data = request.POST.get("mod")

        tree = get_module_calltree(data)

    else:
        return render(request, "modules_calltree.html", {})

    return render(request, "modules_calltree.html", {"tree": tree})


def subroutine_calltree(request):
    if request.method == "POST":
        variable = request.POST.get("Variable")
        instance, member = variable.split("%")
        tree, all = get_subroutine_calltree(instance, member)
    else:
        return render(request, "subroutine_calltree.html", {})
    return render(request, "subroutine_calltree.html", {"tree": tree, "all": all})


@require_http_methods(["GET", "POST"])
def view_table(request, table):

    table = VIEWS_TABLE_DICT[table]
    if not table:
        return HttpResponse(b"Table not found", status=404)
    model = table["name"]
    if request.method == "POST":
        print(request.headers)
        sort_by = request.POST.get("sort_by", None)
    else:
        sort_by = None

    foreign_keys = [
        field.name
        for field in model._meta.get_fields()
        if isinstance(field, models.ForeignKey)
    ]
    all_objects = model.objects.select_related(*foreign_keys).all()

    if sort_by in [field.name for field in model._meta.get_fields()]:
        all_objects = all_objects.order_by(sort_by)

        # Check if the request is coming from HTMX (for partial table response)
        if request.headers.get("HX-Request"):
            # Render only the table rows template for HTMX requests
            return render(request, "partial_table.html", {"all_objects": all_objects})

    return render(request, table["html"], {"all_objects": all_objects})


def home(request):
    return render(request, "home.html")


def query(request):
    return render(request, "query.html", {})


def fake(request, table):
    table = VIEWS_TABLE_DICT[table]
    # print(table["name"])
    return render(request, "query_variables.html", {"table": table["dict"]})
