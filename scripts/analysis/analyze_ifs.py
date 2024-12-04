import re
from utilityFunctions import line_unwrapper


class Ifs:
    """
    Class to hold infomation on if_blocks:
    * self.start : starting line number of particular block
    * self.end : absolute ending line number of particular block
    * self.relative_end : relative ending line number to entire block
        *  if (1) then       <- start of 1
        *     if (2) then    <- start of 2
        *         code
        *     else if (3)    <- start of 3, relative_end of 2
        *         code
        *     end if         <- end of 2 and 3, relative_end of 3
        *  else (4)          <- start of 4, relative_end of 1
        *     code
        *  end if            <- end of 1 and 4, relative_end of 4
    * self.condition : clause of if_block
    * self.default : True/False of condition based on default namelist values
                     Defaults to True if condition could not be evaluated
    * self.parent : pointer to parent if_block
    * self.children : list of nested if_blocks that are not within else_if/else blocks
    * self.elseif : list of else_if blocks within current block
    * self.elses : pointer to else_block
    * self.depth : layer of nested-ness
    * self.calls : list if subroutine calls in current if_block
    * self.kind : 1 for if, 2 for else_if, 3 for else
    * self.assigned_as_child : bookkeeping info
    * self.child_conditions : bookkeeping info

    """

    def __init__(self):
        self.start: int = -1
        self.end: int = -1
        self.relative_end = 0
        self.condition: str = ""
        self.default = -1
        self.parent: Ifs = None
        self.children = []
        self.elseif = []
        self.elses: Ifs = None
        self.depth = 0
        self.calls = []
        self.kind: int = -1
        self.assigned_as_child = False
        self.child_conditions = set()

    def print_if_structure(self, indent=0):
        idx = "->|" * indent
        print(
            f"{idx}start: {self.start}, end: {self.end}, depth: {self.depth}, relative: {self.relative_end}, type: {self.kind}"
        )
        if self.condition:
            print(f"{idx}condition: {self.condition}")
        if self.default != -1:
            print(f"{idx}default: {self.default}")
        if self.calls:
            print(f"{idx}calls: {self.calls}")
        if self.elseif:
            print(f"{idx}else if:")
        for elf in self.elseif:
            print_if_structure(elf, indent + 1)
        if self.elses:
            print(f"{idx}else:")
        print_if_structure(self.elses, indent + 1)
        if self.parent:
            print(f"{idx}parent: {self.parent.start}")

        if self.children:
            print(f"{idx}children: ")
        for child in self.children:
            print_if_structure(child, indent + 2)

    def evaluate(self, namelist_dict):
        """
        Evaluate the if-condition
        """
        string = self.condition
        res = ""
        string = re.sub(r"(\.\w*\.)", r" \1 ", string)
        isString = bool(re.search(r"'", string))
        string = string.strip(" ()")
        res = string.split()
        left = True
        for w in range(len(res)):
            left = False
            res[w] = res[w].strip()
            if res[w] in namelist_dict:
                n = namelist_dict[res[w]]
                if n.variable:
                    res[w] = f"{n.variable.default_value}"
                    left = True

            if "'" not in res[w]:
                res[w] = f"{operands(res[w])}"

            """ 
            bit sketchy
            testing if res[w] is a "true" string, 
            like a variable name and not bools/keywords
            """

        res = " ".join(res)
        p = None
        try:
            p = eval(res)
        except:
            p = f"Error: {res}"
            return True
        return p


def get_if_condition(string):
    """
    Returns the clause in if_condition
    """
    condition = re.findall(r"if\s*\(\s*(.*)\s*\)", string)
    return condition[0] if condition else ""


def operands(op):
    """
    Mapping of Fortran operators to Python
    """
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
            return f"'{op}'"


def set_default_helper(node, namelist_dict, stack):
    if not node:
        return

    if node.kind == 1:  # `if` block
        node.default = node.evaluate(namelist_dict)
        if node.default:
            stack.append(1)
            for child in node.children:
                set_default_helper(child, namelist_dict, stack)
            stack.pop()
        else:
            stack.append(-1)
            for elseif in node.elseif:
                set_default_helper(elseif, namelist_dict, stack)

                if stack and stack[-1] > 0:
                    return
            if node.elses and stack[-1] == -1:
                set_default_helper(node.elses, namelist_dict, stack)
                stack.pop()

    elif node.kind == 2:
        node.default = node.evaluate(namelist_dict)
        stack.append(2)
        if node.default:
            for child in node.children:
                set_default_helper(child, namelist_dict, stack)
        else:
            stack.pop()

    elif node.kind == 3:
        node.default = True
        for child in node.children:
            set_default_helper(child, namelist_dict, stack)


def set_default(ifs, namelist_dict):
    """
    set default T/F of based on the default values
    of namelist_variables
    """
    flat = flatten(ifs)
    for i in flat:
        i.default = False
    for node in ifs:
        set_default_helper(node, namelist_dict, [])


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
    """
    Returns all if/else_if/else blocks
    """
    total = []
    for block in blocks:
        total.extend(flatten_helper(node=block, depth=0, visited=[], res=[]))
    flattened_list = sorted(total, key=lambda x: x.start)
    return flattened_list


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
        if if_block.parent:
            print(f"{idx}parent: {if_block.parent.start}")

        if if_block.children:
            print(f"{idx}children: ")
        for child in if_block.children:
            print_if_structure(child, indent + 2)


def find_if_blocks(lines):
    """
    Returns all parent (outer-most) if_blocks
    """
    res = []
    index = 0
    depth = 0
    stack = []

    current = None
    root = Ifs()
    root.condition = "ROOT"
    last_elseif = None
    last_else = None

    while index < len(lines):
        ct = index
        line, index = line_unwrapper(lines, index)
        line = line.strip()

        ln = index if index == ct else ct
        subroutine_call = re.findall(r"\b\s*call\s*(\w*)\(", line)
        if subroutine_call and subroutine_call[0] != "endrun" and current:
            current.calls.append((ln, subroutine_call[0].lower()))
        # FOUND IF BLOCK
        if re.search(r"^if\s*\(", line) or re.findall(r"\w*\s*:\s*if\s*\(", line):
            depth += 1
            parent = Ifs()
            parent.start = ln
            parent.depth = depth
            parent.condition = get_if_condition(line)
            parent.kind = 1
            parent.parent = root

            # ONE LINER
            if not re.search(r"\bthen\s*($|\n)", line):
                if subroutine_call and subroutine_call[0] != "endrun":
                    parent.calls.append((ln, subroutine_call[0].lower()))
                parent.relative_end = index
                parent.end = index
                depth -= 1

                if parent.parent.condition == "ROOT":
                    res.append(parent)
                elif parent.start not in root.child_conditions:
                    root.children.append(parent)
                    root.child_conditions.add(parent.start)
                index = ln + 1
                continue

            if last_else and last_else.depth == depth - 1:
                if parent.start not in last_else.child_conditions:
                    last_else.children.append(parent)
                    last_else.child_conditions.add(parent.start)
                parent.assigned_as_child = True

            elif last_elseif and last_elseif.depth == depth - 1:
                if parent.start not in last_elseif.child_conditions:
                    last_elseif.children.append(parent)
                    last_elseif.child_conditions.add(parent.start)
                parent.assigned_as_child = True

            elif parent.start not in root.child_conditions:
                root.children.append(parent)
                root.child_conditions.add(parent.start)

            root = parent
            current = parent
            stack.append(parent)

        # FOUND ELSE_IF BLOCK
        elif re.search(r"\s*else\s*if\s*[(]", line):
            # UPDATE PREVIOUS IF/ELSE_IF ENDIND LINE NUMBER
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

            if root.kind == 1 and elf.start not in root.child_conditions:
                root.elseif.append(elf)
                root.child_conditions.add(elf.start)
                last_elseif = elf

            current = elf
            stack.append(elf)

        # FOUND ELSE BLOCK
        elif re.search(r"\s*else\s*", line):
            # UPDATE PREVIOUS IF/ELSE_IF ENDIND LINE NUMBER
            if root.elseif:
                root.elseif[-1].end = ln
                root.elseif[-1].relative_end = ln
            else:
                root.relative_end = ln
            elf = Ifs()
            elf.start = ln
            elf.depth = depth
            elf.default = False
            elf.kind = 3
            elf.parent = root

            if root.kind == 1:
                root.elses = elf
                last_else = elf
            current = elf
            stack.append(elf)

        # FOUND END OF IF_BLOCK
        elif re.search(r"\s*end\s*if", line) and not line.startswith("#"):
            node = None
            depth -= 1
            while True:
                node = stack.pop()
                if node.end == -1:
                    node.end = ln
                if node.relative_end == 0:
                    node.relative_end = ln
                if node.kind == 1 and node.depth > 1 and not node.assigned_as_child:
                    if node.start not in node.parent.child_conditions:
                        node.parent.children.append(node)
                        node.parent.child_conditions.add(node.start)
                if node.kind == 1:
                    break
            # APPEND PARENT (OUTER-MOST) IF BLOCK AND RESET
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


def set_parent_helper(node, parent):
    if node:
        node.parent = parent

        for child in node.children:
            set_parent_helper(child, node)
        for elseif in node.elseif:
            set_parent_helper(elseif, node)
        if node.elses:
            set_parent_helper(node.elses, node)


def set_parent(if_block_list):
    for node in if_block_list:
        set_parent_helper(node, None)


def run(filename):
    f = open(filename, "r")
    r = f.readlines()
    f.close()

    blocks = find_if_blocks(r)
    set_parent(blocks)
    flat = flatten(blocks)
    for i in flat:
        i.default = False

    for i in blocks:
        x = [i.end]

        if i.elses:
            x.append(i.elses.start)
        if i.elseif:
            x.append(i.elseif[0].start)
        i.relative_end = min(x)
    return blocks
