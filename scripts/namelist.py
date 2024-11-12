import linecache
import mmap
import re
import subprocess
from os.path import join

from scripts.mod_config import E3SM_SRCROOT, ELM_SRC
from scripts.utilityFunctions import insert_header_for_unittest, line_unwrapper

n = join(ELM_SRC, "biogeochem", "AllocationMod.F90")


def mapcount(filename):
    with open(filename, "r+") as f:
        buf = mmap.mmap(f.fileno(), 0)
        lines = 0
        readline = buf.readline
        while readline():
            lines += 1
        return lines


def single_line_unwrapper(filename, ct, verbose=False):
    """
    Function that takes code segment that has line continuations
    and returns it all on one line.
    """

    full_line = ""
    while True:
        current_line = linecache.getline(filename, ct)
        if bool(re.search(r"^\s*!", current_line)):
            ct += 1
            continue

        current_line = current_line.split("!")[0]
        current_line = current_line.rstrip("\n")
        # continuation = current_line.endswith("&")
        continuation = bool(re.search(r"&", current_line))
        current_line = re.sub(r"&", " ", current_line)

        if current_line.isspace() or not current_line:
            ct += 1
            continue
        current_line = current_line.strip()
        full_line += current_line
        if not continuation:
            break
        ct += 1
    return full_line, ct


class NameList:
    def __init__(self) -> None:
        """
        Class to hold infomation on namelist variables:
        * self.name : namelist name
        * self.group : the group the namelist variable belongs to
        * self.if_blocks : list of number lines that if statments where the namelist variable is present in
        * self.variable : a pointer to a Variable class
        * self.filepath : file where namelist variable was found
        """
        self.name: str = ""
        self.group: str = ""
        self.if_blocks: list[Ifs] = []
        self.variable: str = ""
        self.filepath: str = ""


def find_all_namelist():
    output = subprocess.getoutput(
        f'grep -rin --include=*.F90 --exclude-dir=external_modules/ "namelist\s*\/" {ELM_SRC}'
    )
    namelist_dict = {}
    for line in output.split("\n"):
        line = line.split(":")
        filename = line[0]
        line_number = int(line[1]) - 1
        info = line[2]
        full_line, _ = single_line_unwrapper(filename, line_number)

        group = re.findall(r"namelist\s*\/\s*(\w+)\s*\/", info, re.IGNORECASE)[0]
        flags = full_line.split("/")[-1].split(",")
        for flag in flags:
            f = NameList()
            f.name = flag.strip()
            f.group = group
            f.file = filename
            f.name_declaration_line_number = line_number

            namelist_dict[flag.strip()] = f
    return namelist_dict


"""
FINSISH
"""


class Ifs:
    def __init__(self):
        self.start: int = -1
        self.end: int = -1
        self.file = None
        self.condition: str = ""
        self.parent: Ifs = None
        self.children = []
        self.elseif = []
        self.elses: Ifs = None
        self.depth = 0
        self.calls = []
        self.default = -1
        self.relative_end = 0
        self.kind: int = -1
        self.assigned_as_child = False
        self.child_conditions = set()


def binary_search(iterable: list[Ifs], ln):
    left, right = 0, len(iterable) - 1

    while left <= right:
        mid = (left + right) // 2
        if iterable[mid].start <= ln and ln <= iterable[mid].end:
            return mid
        elif iterable[mid].start < ln:
            left = mid + 1
        else:
            right = mid - 1
    # if left > 0 and iterable[left - 1].start <= ln:
    #     return left - 1
    else:
        return -1


def find_elm(node: Ifs, e, add, found, s):
    if node.start <= e.ln and e.ln <= node.end:
        found = True

        if node.default:
            if node.start <= e.ln and e.ln <= node.relative_end:
                if (binary_search(node.children, e.ln) == -1 and node.children) or (
                    not node.children
                ):
                    s.add((e, node.start))
                    add = True
                    return add, found
                else:
                    child_node = node.children[binary_search(node.children, e.ln)]
                    add, found = find_elm(child_node, e, add, found, s)

        elif node.elseif:
            node_2 = node.elseif[binary_search(node.elseif, e.ln)]
            if node_2.default:
                if node_2.start <= e.ln and e.ln < node_2.end:
                    add, found = find_elm(node_2, e, add, found, s)
                    print(node_2.start, node_2.end, node_2.relative_end, add, found)
        elif node.elses:
            node_3 = node.elses
            if node_3.start <= e.ln and e.ln < node_3.end:
                add, found = find_elm(node_3, e, add, found, s)

        # else:
        #     for child in node.children:
        #         # Recursively search in child nodes
        #         child_add, child_found = find_elm(child, e, add, found, s)
        #         add = add or child_add  # Combine add values from recursive calls
        #         found = (
        #             found or child_found
        #         )  # Combine found values from recursive calls

    # If no range was found, set `found` to False
    if not found:
        s.add(e)
        add = True

    return add, found


def elmtypes(sub_dict, ifs, subroutine) -> dict:
    """
    ["Allocation1_PlantNPDemand",
     "Allocation2_ResolveNPLimit",
     "Allocation3_PlantCNPAlloc",]:

    """

    res = {}
    for elm in sub_dict[subroutine].elmtype_access_by_ln.keys():
        res[elm] = set()
        for e in sub_dict[subroutine].elmtype_access_by_ln[elm]:
            found = False
            add = False
            parent = ifs[binary_search(ifs, e.ln)]
            add, found = find_elm(parent, e, add, found, res[elm])

            if not found:
                res[elm].add(e)
                add = True
            if not add:
                print("removed", elm, e)

    res = {k: list(v) for k, v in res.items()}
    return res


def get_if_condition(string):
    condition = re.findall(r"if\s*\(\s*(.*)\s*\)", string)
    return condition[0] if condition else ""


def operands(op):
    op = op.strip()
    match op:
        case ".true.":
            return "True"
        case ".false.":
            return "False"
        case "+":
            return "+"
        case "-":
            return "-"
        case "*":
            return "*"
        case "/":
            return "//"
        case "**":
            return "**"
        case "==" | ".eq." | ".eqv.":
            return "=="
        case "/=" | ".ne." | ".neqv":
            return "!="
        case ">" | ".gt.":
            return ">"
        case "<" | ".lt.":
            return "<"
        case ">=" | ".ge.":
            return ">="
        case "<=" | ".le.":
            return "<="
        case ".and.":
            return "and"
        case ".or.":
            return "or"
        case ".not.":
            return "not"
        case _:
            return op


def evaluate(string, namelist_dict):
    """
    Evaluate the if-condition
    """
    res = ""
    string = re.sub(r"(\.\w*\.)", r" \1 ", string)
    string = string.strip(" ()")
    res = string.split()

    for w in range(len(res)):
        res[w] = res[w].strip()
        if res[w] in namelist_dict:
            n = namelist_dict[res[w]]
            if n.variable:
                res[w] = f"'{n.variable.default_value}'"
        res[w] = operands(res[w])

    res = " ".join(res)
    p = None
    try:
        p = eval(res)
    except:
        p = f"Error: {res}"
    return p


def get_default_value(filename, line_number):
    line, _ = single_line_unwrapper(filename, line_number)
    default = re.findall(r".*=\s*(.*)", line)
    return default[0] if default else ""


def insert_default(mod_dict):
    """
    Insert default values of for each variable
    """
    for mod in mod_dict.values():
        filename = mod.filepath
        for gv in mod.global_vars:
            gv.default_value = get_default_value(filename, gv.ln)


def generate_namelist_dict(mod_dict, namelist_dict, ifs):
    """
    Find used namelists variables within the if-condition
    Attach variable objects to each namelist
    """
    for mod in mod_dict.values():
        #  filename = get_filename_from_module(mod.name)
        for namelist in namelist_dict.keys():
            current_namelist_var = namelist_dict[namelist]

            matching_var = [v for v in mod.global_vars if v.name == namelist]
            if matching_var:
                var = matching_var[0]
                if_blocks = []
                for pair in ifs:
                    if re.search(
                        r"\b\s*{}\b\s*".format(re.escape(namelist)), pair.condition
                    ):
                        if_blocks.append(pair)

                current_namelist_var.if_blocks.extend(if_blocks)
                current_namelist_var.variable = var


def set_default_helper(node, namelist_dict):
    if node:
        node.default = False if not evaluate(node.condition, namelist_dict) else True

        for child in node.children:
            set_default_helper(child, namelist_dict)
        for elseif in node.elseif:
            set_default_helper(elseif, namelist_dict)
        if node.elses:
            set_default_helper(node.elses, namelist_dict)


def set_default(ifs, namelist_dict):
    for node in ifs:
        set_default_helper(node, namelist_dict)


def find_ifs_2(lines):
    res = []
    index = 0
    depth = 0
    stack = []

    current = None
    root = Ifs()
    root.condition = "ROOT"
    last_elseif = None  # Track the last `else if` node
    last_else = None

    while index < len(lines):
        ct = index
        line, index = line_unwrapper(lines, index)
        line = line.strip()

        ln = index if index == ct else ct
        subroutine_call = re.findall(r"\b\s*call\s*(\w*)\(", line)
        if subroutine_call and current:
            current.calls.append((ln, subroutine_call[0]))

        if re.search(r"^if\s*\(", line) or re.findall(r"\w*\s*:\s*if\s*\(", line):
            depth += 1
            parent = Ifs()
            parent.start = ln
            parent.depth = depth
            parent.condition = get_if_condition(line)
            parent.kind = 1
            parent.parent = root
            if not re.search(r"\bthen\s*($|\n)", line):
                parent.relative_end = index
                parent.end = index
                depth -= 1

                if parent.parent.condition == "ROOT":
                    res.append(parent)
                elif parent.condition not in root.child_conditions:
                    root.children.append(parent)
                    root.child_conditions.add(parent.condition)
                index = ln + 1
                continue

            if last_else and last_else.depth == depth - 1:
                if parent.condition not in last_else.child_conditions:
                    last_else.children.append(parent)
                    last_else.child_conditions.add(parent.condition)
                parent.assigned_as_child = True

            elif last_elseif and last_elseif.depth == depth - 1:
                if parent.condition not in last_elseif.child_conditions:
                    last_elseif.children.append(parent)
                    last_elseif.child_conditions.add(parent.condition)
                parent.assigned_as_child = True
            elif parent.condition not in root.child_conditions:
                root.children.append(parent)
                root.child_conditions.add(parent.condition)

            root = parent
            current = parent
            stack.append(parent)

        elif re.search(r"\s*else\s*if\s*[(]", line):
            if root.elseif:
                root.elseif[-1].end = ln
                root.elseif[-1].relative_end = ln
            else:
                root.relative_end = ln
            elf = Ifs()
            elf.start = ln
            elf.depth = depth
            elf.condition = get_if_condition(line)
            elf.kind = 2
            elf.parent = root

            if root.kind == 1 and elf.condition not in root.child_conditions:
                root.elseif.append(elf)
                root.child_conditions.add(elf.condition)
                last_elseif = elf

            current = elf
            stack.append(elf)
        elif re.search(r"\s*else\s*", line):
            if root.elseif:
                root.elseif[-1].end = ln
                root.elseif[-1].relative_end = ln
            else:
                root.relative_end = ln
            elf = Ifs()
            elf.start = ln
            elf.depth = depth
            elf.default = True
            elf.kind = 3
            elf.parent = root

            if root.kind == 1:
                root.elses = elf
                last_else = elf
            current = elf
            stack.append(elf)

        elif re.search(r"\s*end\s*if", line):
            node = None
            depth -= 1
            while True:
                node = stack.pop()
                if node.end == -1:
                    node.end = ln
                if node.relative_end == 0:
                    node.relative_end = ln
                if node.kind == 1 and node.depth > 1 and not node.assigned_as_child:
                    if node.condition not in node.parent.child_conditions:
                        node.parent.children.append(node)
                        node.parent.child_conditions.add(node.condition)
                if node.kind == 1:
                    break
            if node.depth == 1:
                res.append(node)
                root = Ifs()
                root.condition = "ROOT"
                index = ln + 1
                last_elseif = None
                last_else = None
                continue
            root = node.parent
            last_elseif = None
            last_else = None

        index = ln + 1
    return res


def print_if_structure(if_block, indent=0):
    if if_block:
        idx = "->|" * indent
        print(
            f"{idx}start: {if_block.start}, end: {if_block.end}, depth: {if_block.depth}, relative: {if_block.relative_end}, type: {if_block.kind}"
        )
        if if_block.condition:
            print(f"{idx}condition: {if_block.condition}")
        if if_block.default != -1:
            print(f"{idx}default: {if_block.default}")
        if if_block.calls:
            print(f"{idx}calls: {if_block.calls}")
        if if_block.elseif:
            print(f"{idx}else if:")
        for elf in if_block.elseif:
            print_if_structure(elf, indent + 1)
        if if_block.elses:
            print(f"{idx}else:")
        print_if_structure(if_block.elses, indent + 1)
        print(f"{idx}parent: {if_block.parent.start}")

        if if_block.children:
            print(f"{idx}children: ")
        for child in if_block.children:
            print_if_structure(child, indent + 2)


def run(filename):
    f = open(filename, "r")
    r = f.readlines()

    return find_ifs_2(r)


def flatten_helper(node, depth, visited, res):
    if node:
        if node.start not in visited:
            res.append(node)
            visited.append(node.start)

        for i in node.elseif:
            flatten_helper(i, depth, visited, res)
        for i in node.children:
            flatten_helper(i, depth + 1, visited, res)

        if node.elses:
            flatten_helper(node.elses, depth, visited, res)

    return res


def flatten(blocks):
    total = []
    for block in blocks:
        total.extend(flatten_helper(node=block, depth=0, visited=[], res=[]))
    flattened_list = sorted(total, key=lambda x: x.start)
    return flattened_list
