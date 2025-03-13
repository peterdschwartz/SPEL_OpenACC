import linecache
import mmap
import re
import subprocess
from os.path import join

from scripts.mod_config import E3SM_SRCROOT, ELM_SRC

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
        continuation = current_line.endswith("&")
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


def find_if_starts(file):
    # output = subprocess.getoutput(
    #     f'grep -rin --include=*.F90 --exclude-dir=external_modules/ "\s*\w*\s*if\s*[(]" {file}'
    # )
    num_total_lines = mapcount(file)
    print(num_total_lines)
    res = []
    cur_line = 1
    ifs = []
    starts = []
    ends = []
    while cur_line <= num_total_lines:
        # line, cur_line = single_line_unwrapper(file, cur_line)
        line = linecache.getline(file, cur_line)
        if bool(re.search(r"\bif\s*[(]", line)):
            capture = line
            starts.append(cur_line)
            depth = 1
            cur_line += 1
            while depth > 0 and cur_line <= num_total_lines:
                # line, cur_line = single_line_unwrapper(file, cur_line)
                line = linecache.getline(file, cur_line)
                capture += line
                if bool(re.search(r"else\s*if\s*[(]", line)):
                    pass
                elif bool(re.search(r"else", line)):
                    pass

                elif bool(re.search(r"end\s*if", line)):
                    depth -= 1
                    x = starts.pop()
                    res.append((x, cur_line))
                    ends.append(cur_line)
                    # if depth <= 0:
                    #     break

                elif bool(re.search(r"\bif\s*[(]", line)):
                    starts.append(cur_line)
                    depth += 1
                cur_line += 1
            ifs.append(capture)
        else:
            cur_line += 1
    return res

    # with open(file, "r") as f:
    #     for idx, line in enumerate(f):
    #
    # return [line for line in output.split("\n")]


# ifs = find_if_starts(n)
# print(len(ifs))
# namelist = "nu_com"
# for i in ifs:
#     capture = ""
#     for j in range(i[0], i[1] + 1):
#         f = linecache.getline(n, j)
#         capture += f
#     if bool(re.search(namelist, capture)):
#         print(f"--line {i}--")
#         print(capture)


# #
# print(name_dict["use_modified_infil"])
# for i in name_dict.keys():
#     print(i, name_dict[i])
class NameList:
    def __init__(self) -> None:
        self.name = ""
        self.file = ""
        self.group = ""
        self.name_declaration_line_number = 0
        self.instances = []
        self.if_statements = []

    def find_if_statment_start(self):
        for line in output.split("\n"):
            line_number = int(line.split(":")[0])
            if self.name in line:
                p.if_statements.append(line_number)
                capture = ""
                while True:
                    cur = single_line_unwrapper(self.file, line_number)
                    capture += cur
                    line_number += 1
                    if "elseif" in cur:
                        pass
                    elif "end if" in cur:
                        start -= 1
                        if start == 0:
                            break
                    elif "if" in cur:
                        start += 1
                print("--")
                print(capture)

                print("--")


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


print(find_all_namelist().keys())

# p = NameList()
# p.name = "use_var_soil_thick"
# name_dict = find_all_namelist()
# p.file = n
# p.find_if_statment_start()
# print(single_line_unwrapper(p.file, p.if_statements[0]))
