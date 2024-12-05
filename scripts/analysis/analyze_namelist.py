from mod_config import ELM_SRC
import re
import subprocess

from .analyze_ifs import set_default
from .analyze_elm import binary_search, flatten
from .analyze_elm import single_line_unwrapper


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
        self.if_blocks = []
        self.variable: str = ""
        self.filepath: str = ""


def find_all_namelist():
    """
    Find all namelist variables across ELM
    """

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


def generate_namelist_dict(mod_dict, namelist_dict, ifs, subroutine_calls):
    """
    Find used namelists variables within the if-condition
    Attach variable objects to each namelist
    """
    for mod in mod_dict.values():
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

                    for index, call in enumerate(pair.calls):
                        ln = call[0]
                        name = call[1]
                        if isinstance(name, tuple):
                            continue

                        if subroutine_calls.get(name) != None:
                            for s in subroutine_calls[name]:
                                if ln == s.ln:
                                    pair.calls[index] = (name, s)

                current_namelist_var.if_blocks.extend(if_blocks)
                current_namelist_var.variable = var


def change_default(if_block, namelist, namelist_variable, value):
    """
    Change namelist_variable's default to value
    if_block is parent ifblocks
    """
    namelist[namelist_variable].variable.default_value = value
    set_default(if_block, namelist)



