from django import template
from django.db import connection, models
from django.shortcuts import HttpResponse, render
from django.views.decorators.http import require_http_methods

from .calltree import get_module_calltree, get_subroutine_calltree
from .models import (
    ModuleDependency,
    Modules,
    SubroutineArgs,
    SubroutineCalltree,
    Subroutines,
    TypeDefinitions,
    UserTypeInstances,
)

register = template.Library()
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
    "subroutines": {
        "name": Subroutines,
        "html": "subroutines.html",
        "fields": {
            "Id": "subroutine_id",
            "Module": "module.module_name",
            "Subroutine": "subroutine_name",
        },
    },
    "modules": {
        "name": Modules,
        "html": "modules.html",
        "fields": {
            "Id": "module_id",
            "Module": "module_name",
        },
    },
    "subroutine_calltree": {
        "name": SubroutineCalltree,
        "html": "subroutine_calltree.html",
        "fields": {
            "Id": "parent_id",
            "Parent Sub": "parent_subroutine.subroutine_name",
            "Child Sub": "child_subroutine.subroutine_name",
        },
    },
    "types": {
        "name": TypeDefinitions,
        "html": "types.html",
        "fields": {
            "Id": "define_id",
            "Module": "module.module_name",
            "Type Name": "user_type.user_type_name",
            "Member Type": "member_type",
            "Member Name": "member_name",
            "Dim": "dim",
            "Bounds": "bounds",
        },
    },
    "dependency": {
        "name": ModuleDependency,
        "html": "dep.html",
        "fields": {
            "Id": "dependency_id",
            "Module": "module.module_name",
            "Dependent Mod": "dep_module.module_name",
            "Used object": "object_used",
        },
    },
    "instances": {
        "name": UserTypeInstances,
        "html": "instances.html",
        "fields": {
            "Id": "instance_id",
            "Module": "instance_type.module.module_name",
            "Type Name": "instance_type.user_type_name",
            "Instance Name": "instance_name",
        },
    },
    "subroutineargs": {
        "name": SubroutineArgs,
        "html": "subroutineargs.html",
        "fields": {
            "Id": "arg_id",
            "Subroutine": "subroutine.subroutine_name",
            "Arg Type": "arg_type",
            "Arg Name": "arg_name",
            "Dim": "dim",
        },
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


def subcall(request):
    if request.method == "POST":
        variable = request.POST.get("Variable")
        instance, member = variable.split("%")
    else:
        instance = "bounds"
        member = "begc"
    tree, all = get_subroutine_calltree(instance, member)
    print(f"CallTree with {instance}%{member}\n{tree}")

    context = {
        "tree": tree,
        "all": all,
    }
    if request.method == "POST":
        return render(request, "partials/table_subcall.html", context)
    return render(request, "partials/subcall_partial.html", context)


def subroutine_calltree(request):
    if request.method == "POST":
        variable = request.POST.get("Variable")
        instance, member = variable.split("%")
        tree, all = get_subroutine_calltree(instance, member)
    else:
        return render(request, "subroutine_calltree.html", {})
    return render(request, "subroutine_calltree.html", {"tree": tree, "all": all})


@require_http_methods(["GET", "POST"])
def view_table(request, table_name):
    """
    Generic Function for printing an SQL table, substituting
    the foreign keys with as specifcied in the table definiton
    """

    table = VIEWS_TABLE_DICT[table_name]
    if not table:
        return HttpResponse(b"Table not found", status=404)

    model = table["name"]
    display_fields = table["fields"]
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

    if sort_by:
        sort_field = display_fields[sort_by]
        all_objects = all_objects.order_by(sort_field.replace(".", "__"))

    rows = []
    for obj in all_objects:
        row = []
        for field_name in display_fields.values():
            parts = field_name.split(".")
            value = getattr(obj, parts[0], None)
            if len(parts) > 1:
                for attr in parts[1:]:
                    value = getattr(value, attr, None)

            row.append(value)
        rows.append(row)

    context = {
        "all_objects": rows,
        "field_names": display_fields,
        "table_name": table_name,
    }
    # Check if the request is coming from HTMX (for partial table response)
    if request.headers.get("HX-Request"):
        return render(request, "partials/dynamic_table.html", context)

    return render(request, table["html"], context)


def home(request):
    return render(request, "home.html")


def query(request):
    return render(request, "query.html", {})


def fake(request, table):
    table = VIEWS_TABLE_DICT[table]
    # print(table["name"])
    return render(request, "query_variables.html", {"table": table["dict"]})
