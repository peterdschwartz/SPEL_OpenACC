from django.shortcuts import render, HttpResponse
from .models import Modules
from django.db import connection 

from .calltree import get_module_calltree, get_subroutine_calltree
# import module_calltree
TYPE_DEFAULT_DICT = {
    "id": "",
    "module": "",
    "type_name": "",
    "member": "",
    "member_type": "",
    "dim": "",
    "bounds": "",
    "active": ""
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
    "variables": VARS_DEFAULT_DICT
}
def query_statement(table_name, **parm_list):
    
    # table = TABLE_NAME_LOOKUP[parm_list[0]]
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
        cur.execute(
            # f"select * from {table} where id='{id}' and subroutine='{subroutine}' and variable_name='{var_name}'"
            statement
        )
        print(list(cur))
        
VIEWS_TABLE_DICT = {
    "modules": {
        "name": Modules,
        "html": "modules.html",
    }
}

def modules_calltree(request):
    
    # print(grr)
    if request.method == "POST":
        data = request.POST.get('mod')
        
        tree = get_module_calltree(data)

    else: 
        return render(request, 'modules_calltree.html', {})
    
    return render(request, 'modules_calltree.html', {"tree":tree})

def subroutine_calltree(request):
    if request.method == "POST":
        instance = request.POST.get('instance')
        member = request.POST.get('member')
        tree, all = get_subroutine_calltree(instance,member)
        # print(tree[0].split())
        print(all)
        print(tree)
        
    else:
        return render(request, 'subroutine_calltree.html', {})
    return render(request, 'subroutine_calltree.html', {"tree":tree, "all":all})


    
def view_table(request, table):
    table = VIEWS_TABLE_DICT[table]
    if request.method == "GET":
        all_objects = table["name"].objects.all()
        return render(request, table["html"], {"all_objects": all_objects})
    


def home(request):
    return render(request, "home.html")
    # if request.method == "GET":
    #     all_objects = SubroutineActiveGlobalVars.objects.all()
    #     print("-------")
    #     # print(all_objects)
    #     execute(query_statement("variables", id="5"))
    #     return render(request, 'subroutine_vars.html', {"all_objects": all_objects})

def query(request):
    return render(request, "query.html",{})

def fake(request, table):
    table = VIEWS_TABLE_DICT[table]
    # print(table["name"])
    return render(request, "query_variables.html", {"table":table["dict"]})