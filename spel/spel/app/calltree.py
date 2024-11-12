import json

from django.conf import settings
from django.db import connection

DB_NAME = settings.DATABASES["default"]["NAME"]

modules = {}
subroutines = {}


class Node:
    def __init__(self, name, dependency=None):
        if dependency is None:
            dependency = []
        self.name = name
        self.dependency = dependency


def modules_dfs(mod_id, node):
    if mod_id == 0 or mod_id == 2:
        return

    visited = []
    m = None
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT * FROM module_dependency WHERE module_id={mod_id} order by dependency_id"
        )
        m = cur.fetchall()
    for i in m:
        dep = i[2]
        if dep not in visited:
            n = Node(modules[dep])
            node.dependency.append(n)
            modules_dfs(dep, n)

        visited.append(dep)


def jsonify(node, d):
    d["node"] = {"name": node.name, "children": []}
    for child in node.dependency:
        if child.name != "shr_kind_mod" and child.name != "NULL":
            child_dict = {}
            jsonify(child, child_dict)
            d["node"]["children"].append(child_dict)


def module_calltree_helper():
    root = Node("")
    m = None
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM modules")
        m = cur.fetchall()
    for i in m:
        modules[i[0]] = i[1]

    return root, modules


def get_module_calltree(mod_name):
    root, modules = module_calltree_helper()
    root.name = mod_name
    key = None
    try:
        key = list(modules.keys())[list(modules.values()).index(mod_name)]

    except ValueError as e:
        return "n/a"
    modules_dfs(key, root)
    r = {}
    jsonify(root, r)
    return json.dumps(r)


def subroutine_active_table(instance, member):
    s = None
    with connection.cursor() as cur:
        cur.execute(
            f"""
            SELECT 
                m1.subroutine_name, 
                m2.instance_name, 
                m4.member_name, 
                m3.status 
            FROM 
                subroutines m1 
            JOIN 
                user_type_instances m2 
            JOIN 
                subroutine_active_global_vars m3 
            JOIN 
                type_definitions m4 
            WHERE 
                m3.subroutine_id = m1.subroutine_id 
            AND 
                m3.instance_id = m2.instance_id 
            AND 
                m3.member_id = m4.define_id 
            AND 
                m1.subroutine_id NOT IN (SELECT child_subroutine_id FROM {DB_NAME}.subroutine_calltree)
            AND 
                m2.instance_name = '{instance}'
            AND
                m4.member_name = '{member}' 
            """
        )
        s = cur.fetchall()
    return [i[0] for i in s]


def subroutine_active_table_ALL(instance, member):
    s = None
    with connection.cursor() as cur:
        cur.execute(
            f"""
            SELECT 
                m1.subroutine_name, 
                m2.instance_name, 
                m4.member_name, 
                m3.status 
            FROM 
                subroutines m1 
            JOIN 
                user_type_instances m2 
            JOIN 
                subroutine_active_global_vars m3 
            JOIN 
                type_definitions m4 
            WHERE 
                m3.subroutine_id = m1.subroutine_id 
            AND 
                m3.instance_id = m2.instance_id 
            AND 
                m3.member_id = m4.define_id 
            AND 
                m2.instance_name = '{instance}'
            AND
                m4.member_name = '{member}' 
            
            """
        )
        s = cur.fetchall()
    return s


def subroutine_dfs(sub_id, node):
    if sub_id == 0:
        return
    visited = []
    s = None
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT * FROM subroutine_calltree WHERE parent_subroutine_id={sub_id} order by parent_id"
        )
        s = cur.fetchall()

    for i in s:
        dep = i[2]
        if subroutines[dep] == "Null":
            continue
        if dep not in visited:
            n = Node(subroutines[dep])
            node.dependency.append(n)
            subroutine_dfs(dep, n)

        visited.append(dep)


def subroutine_calltree_helper():
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM subroutines")
        s = cur.fetchall()
    for i in s:
        subroutines[i[0]] = i[1]

    return subroutines


def get_subroutine_calltree(instance, member):
    res = []
    if instance != "" and member != "":
        subs = subroutine_active_table(instance, member)
        all = subroutine_active_table_ALL(instance, member)
    else:
        all = []
    for sub_name in subs:
        if sub_name == "Null":
            continue
        root = Node("")
        subroutines = subroutine_calltree_helper()
        root.name = sub_name
        key = None

        try:
            key = list(subroutines.keys())[list(subroutines.values()).index(sub_name)]
        except ValueError as e:
            return "n/a"

        subroutine_dfs(key, root)
        r = {}
        jsonify(root, r)
        res.append(json.dumps(r))
    return res, all
