from django import template
from django.db import connection, models
from django.db.models.query import Prefetch
from django.shortcuts import HttpResponse, render
from django.views.decorators.http import require_http_methods

from .calltree import Node, get_module_calltree, get_subroutine_calltree
from .models import (
    ModuleDependency,
    Modules,
    SubroutineActiveGlobalVars,
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
        "title": "Table of Subroutines",
    },
    "modules": {
        "name": Modules,
        "html": "modules.html",
        "fields": {
            "Id": "module_id",
            "Module": "module_name",
        },
        "title": "Table of Modules",
    },
    "subroutine_calltree": {
        "name": SubroutineCalltree,
        "html": "subroutine_calltree.html",
        "fields": {
            "Id": "parent_id",
            "Parent Sub": "parent_subroutine.subroutine_name",
            "Child Sub": "child_subroutine.subroutine_name",
        },
        "title": "Table of Subroutine Call Tree",
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
        "title": "Table of Type Definitions",
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
        "title": "Table of Module Dependencies",
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
        "title": "Table of User Type Instances",
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
        "title": "Table of Subroutine Arguments",
    },
    "activeglobalvars": {
        "name": SubroutineActiveGlobalVars,
        "html": "active_global_vars.html",
        "fields": {
            "Id": "variable_id",
            "Subroutine": "subroutine.subroutine_name",
            "Inst": "instance.instance_name",
            "Member": "member.member_name",
            "Status": "status",
        },
        "title": "Table of Global Vars by Subroutine",
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
        if "%" in variable:
            instance, member = variable.split("%")
        else:
            # Assume just an instance.
            instance = variable
            member = ""
    else:
        instance = "bounds"
        member = "begc"
    tree_list, all = get_subroutine_calltree(instance, member)

    html_tree = build_tree_html(tree_list)
    context = {
        "tree": html_tree,
        "all": all,
    }
    if request.method == "POST":
        # return render(request, "partials/table_subcall.html", context)
        return render(request, "partials/subcall_partial.html", context)
    return render(request, "partials/subcall_partial.html", context)


def build_tree_html(tree: list[Node]):
    """Recursive function to build HTML for a tree."""
    html = '<ul id="SubTree">'
    for node in tree:
        html += process_node(node)
    html += "</ul>"
    return html


def process_node(node: Node):
    """
    Function to tranlate Node("name":name,"children":[])
    to html
    """
    html = ""

    if node.children:
        html += f'<li><span class="box">{node.name}</span>'
        html += add_details_btn(node.name)
        html += '<ul class="child">'
        for child in node.children:
            html += process_node(child)
        html += "</ul>"
        html += "</li>"
    else:
        html += f'<li><span class="parent">{node.name}</span>'
        html += add_details_btn(node.name)
        html += "</li>"

    return html


def add_details_btn(name: str) -> str:
    """
    Adds html for button that sends requests via htmx
    """
    html = f'<button class="details-btn" aria-label="View Details" hx-get="/subroutine-details/{name}/" '
    html += 'hx-target="#modalContent" hx-trigger="click" hx-swap="innerHTML">'
    html += "</button>"
    return html


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
    title = table["title"]
    if request.method == "POST":
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
        "title": table["title"],
    }
    # Check if the request is coming from HTMX (for partial table response)
    if request.headers.get("HX-Request"):
        return render(request, "partials/dynamic_table.html", context)

    return render(request, "partials/table_view.html", context)


def type_details(request, type_name):

    context = {"type_name": type_name, "details": "Testing type details"}

    return render(
        request,
        "partials/type_details.html",
        context,
    )


def subroutine_details(request, subroutine_name):

    subroutine = (
        Subroutines.objects.filter(subroutine_name=subroutine_name)
        .select_related("module")
        .prefetch_related(
            Prefetch(
                "parent_subroutine",
                queryset=SubroutineCalltree.objects.filter(
                    parent_subroutine__subroutine_name=subroutine_name
                ),
            )
        )
        .first()
    )

    if subroutine:
        module = subroutine.module.module_name
        args = [
            (v.arg_type, v.arg_name, v.dim) for v in subroutine.subroutine_args.all()
        ]
        callees = {
            f"{s.child_subroutine.module.module_name}::{s.child_subroutine.subroutine_name}"
            for s in subroutine.parent_subroutine.all()
        }
        dtype_vars = [
            (
                v.instance.instance_type.user_type_name,
                f"{v.instance.instance_name}%{v.member.member_name}",
                v.status,
            )
            for v in subroutine.subroutine_dtype_vars.all()
        ]
        dtype_vars.sort(key=lambda x: x[1])

        context = {
            "subroutine": subroutine.subroutine_name,
            "module": module,
            "args": args,
            "callees": callees,
            "dtype_vars": dtype_vars,
        }

        return render(
            request,
            "partials/subroutine_details.html",
            context,
        )
    else:
        return HttpResponse(b"Subroutine not found.", status=404)


def home(request):
    return render(request, "home.html")


def query(request):
    return render(request, "query.html", {})


def fake(request, table):
    table = VIEWS_TABLE_DICT[table]
    # print(table["name"])
    return render(request, "query_variables.html", {"table": table["dict"]})


def autocomplete(request):
    query = request.GET.get("q", "")

    return render(request, "partials/autocomplete_results.html", context)
