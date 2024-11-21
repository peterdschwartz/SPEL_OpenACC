import json

from django.conf import settings
from django.db import connection

from .models import SubroutineActiveGlobalVars, SubroutineCalltree

DB_NAME = settings.DATABASES["default"]["NAME"]

modules = {}


class Node:
    def __init__(self, name, dependency=None):
        if dependency is None:
            dependency = []
        self.name = name
        self.children = dependency

    def __repr__(self):
        return f"Node(name:{self.name},dep:{self.children})"


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
            node.children.append(n)
            modules_dfs(dep, n)

        visited.append(dep)


def jsonify(node, d):
    d["node"] = {"name": node.name, "children": []}
    for child in node.children:
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


def get_subroutine_details(instance, member, mode):
    from django.db.models import F

    """
    Function that queries database
    """
    # Filter subroutines not in the call tree
    if mode == "head":
        excluded_subroutines = SubroutineCalltree.objects.values_list(
            "child_subroutine", flat=True
        )
    else:
        excluded_subroutines = []

    if instance != "":
        if member != "":
            # Query the database with partial matches
            results = (
                SubroutineActiveGlobalVars.objects.filter(
                    instance__instance_name=instance,
                    member__member_name__contains=member,  # Partial match for member_name
                )
                .exclude(subroutine__in=list(excluded_subroutines))
                .values(
                    sub=F("subroutine__subroutine_name"),
                    inst=F("instance__instance_name"),
                    m=F("member__member_name"),
                    rw=F("status"),
                )
            )
        else:
            results = (
                SubroutineActiveGlobalVars.objects.filter(
                    instance__instance_name__contains=instance,
                )
                .exclude(subroutine__in=list(excluded_subroutines))
                .values(
                    sub=F("subroutine__subroutine_name"),
                    inst=F("instance__instance_name"),
                    m=F("member__member_name"),
                    rw=F("status"),
                )
            )
    elif instance == "" and member == "":
        results = SubroutineActiveGlobalVars.objects.all().values(
            sub=F("subroutine__subroutine_name"),
            inst=F("instance__instance_name"),
            m=F("member__member_name"),
            rw=F("status"),
        )
    # Extract the subroutine names
    return results


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


def subroutine_dfs(sub_id, node, id_to_sub, active_subs):
    """
    Function that performs a depth-first-search of subroutine call tree,
    to get the child subroutines.

    If active_sub is non-empty, only subroutines listed their are included
    """

    if active_subs:
        all_active = False
    else:
        all_active = True

    if sub_id == 0:
        return
    visited = []
    s = None
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT * FROM subroutine_calltree WHERE parent_subroutine_id={sub_id} order by parent_id"
        )
        s = cur.fetchall()

    # Note that each row of s is of the form:
    #   dep_id  parent_id child_id
    for i in s:
        dep = i[2]
        dep_name = id_to_sub[dep]
        if dep_name == "Null":
            continue
        if dep not in visited and (all_active or dep_name in active_subs):
            n = Node(id_to_sub[dep])
            node.children.append(n)
            subroutine_dfs(dep, n, id_to_sub, active_subs)

        visited.append(dep)


def subroutine_calltree_helper():
    subroutines = {}
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM subroutines")
        s = cur.fetchall()
    for i in s:
        subroutines[i[0]] = i[1]

    sub_to_id = {val: key for key, val in subroutines.items()}
    return subroutines, sub_to_id


def get_subroutine_calltree(instance, member):
    tree = []

    active_vars_query = get_subroutine_details(instance, member, mode="")
    parent_subs = get_subroutine_details(instance, member, mode="head")

    parent_sub_names = []
    [
        parent_sub_names.append(row["sub"])
        for row in parent_subs
        if row["sub"] not in parent_sub_names
    ]

    active_subs = []
    if active_vars_query:
        [
            active_subs.append(s["sub"])
            for s in active_vars_query
            if s["sub"] not in active_subs
        ]

    active_vars_table = []
    for item in active_vars_query:
        row = [
            item["sub"],
            f'{item["inst"]}%{item["m"]}',
            item["rw"],
        ]
        active_vars_table.append(row)

    for sub_name in parent_sub_names:
        root = Node("")
        id_to_sub, sub_to_id = subroutine_calltree_helper()
        root.name = sub_name

        key = sub_to_id[sub_name]

        subroutine_dfs(key, root, id_to_sub, active_subs)
        tree.append(root)

    return tree, active_vars_table
