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

    # def print_tree(self, level: int = 0):
    #     """Recursively prints the tree in a hierarchical format."""
    #     if level == 0:
    #         print("CallTree for ", self.node.subname)
    #     indent = "|--" * level
    #     print(f"{indent}>{self.node.subname}")
    #
    #     for child in self.children:
    #         child.print_tree(level + 1)


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
    return results


def build_calltree(root_subroutine_name, active_subs=None):
    """
    Build a call tree starting from the subroutine with name root_subroutine_name.
    If active_subs is provided (a set or list of subroutine names),
    only include children whose names are in active_subs.
    """
    from app.models import SubroutineCalltree, Subroutines

    try:
        root_sub = Subroutines.objects.get(subroutine_name=root_subroutine_name)
    except Subroutines.DoesNotExist:
        return None

    # Create a mapping: parent_subroutine_id -> list of child Subroutines
    # Instead of doing many queries, we fetch all edges in one go.
    edges = SubroutineCalltree.objects.select_related(
        "parent_subroutine", "child_subroutine"
    ).all()
    calltree_map = {}
    for edge in edges:
        parent_id = edge.parent_subroutine.subroutine_name
        calltree_map.setdefault(parent_id, []).append(edge.child_subroutine)

    # Build the tree using a queue (BFS) to avoid recursion.
    root_node = Node(root_sub.subroutine_name)
    queue = [(root_sub, root_node)]
    visited = set()

    while queue:
        current_sub, current_node = queue.pop(0)
        # Avoid cycles:
        if current_sub.subroutine_name in visited:
            continue
        visited.add(current_sub.subroutine_name)
        children = calltree_map.get(current_sub.subroutine_name, [])
        for child in children:
            child_node = Node(child.subroutine_name)
            current_node.children.append(child_node)
            queue.append((child, child_node))

    def prune_tree(node):
        # If active_subs is None, we don't filter.
        if active_subs is None:
            return True
        # Check if the current node is active.
        contains_active = node.name in active_subs
        pruned_children = []
        for child in node.children:
            # Recursively prune children.
            if prune_tree(child):
                pruned_children.append(child)
                contains_active = True
        node.children = pruned_children
        return contains_active

    prune_tree(root_node)
    return root_node


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
        root = build_calltree(sub_name, active_subs)
        tree.append(root)

    return tree, active_vars_table
