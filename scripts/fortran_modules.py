from __future__ import annotations

import subprocess as sp
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.analyze_subroutines import Subroutine

import scripts.dynamic_globals as dg
from scripts.mod_config import ELM_SRC, SHR_SRC, _bc
from scripts.types import PointerAlias


def get_module_name_from_file(fpath: str) -> tuple[int, str]:
    """
    Given a file path, returns the name of the module
    """
    if fpath not in dg.map_fpath_to_module_name:
        cmd = f'grep -rin -E "^[[:space:]]*module [[:space:]]*[[:alnum:]]+" {fpath}'
        # the module declaration will be the first one. Any others will be interfaces
        module_name = sp.getoutput(cmd).split("\n")[0]
        # grep will have pattern <line_number>:module <module_name>
        linenumber, module_name = module_name.split(":")
        module_name = module_name.split()[1].lower()
        linenumber = int(linenumber)
        dg.map_fpath_to_module_name[fpath] = (linenumber, module_name)
    else:
        linenumber, module_name = dg.map_fpath_to_module_name[fpath]

    return linenumber, module_name


def get_filename_from_module(module_name: str, verbose: bool = False):
    """
    Given a module name, returns the file path of the module
    """
    if module_name in dg.map_module_name_to_fpath:
        return dg.map_module_name_to_fpath[module_name]

    cmd = f'grep -rin --exclude-dir=external_models/ "module {module_name}" {ELM_SRC}*'
    elm_output = sp.getoutput(cmd)
    if not elm_output:
        if verbose:
            print("Checking shared modules...")
        #
        # If file is not an ELM file, may be a shared module in E3SM/share/util/
        #
        cmd = f'grep -rin --exclude-dir=external_models/ "module {module_name}" {SHR_SRC}*'
        shr_output = sp.getoutput(cmd)

        if not shr_output:
            if verbose:
                print(
                    f"Couldn't find {module_name} in ELM or shared source -- adding to removal list"
                )
            file_path = None
        else:
            file_path = shr_output.split("\n")[0].split(":")[0]
    else:
        file_path = elm_output.split("\n")[0].split(":")[0]

    dg.map_module_name_to_fpath[module_name] = file_path

    return file_path


def unravel_module_dependencies(modtree, mod_dict, mod, depth=0):
    """
    Recursively go through module dependencies and
    return an ordered list with the depth at which it is used.
    """
    depth += 1
    for m in mod.modules.keys():
        modtree.append({"module": m, "depth": depth})
        dep_mod = mod_dict[m]
        if dep_mod.modules:
            modtree = unravel_module_dependencies(
                modtree=modtree, mod_dict=mod_dict, mod=dep_mod, depth=depth
            )

    return modtree


def print_spel_module_dependencies(
    mod_dict: dict[str, FortranModule],
    subs: dict[str, Subroutine],
    depth=0,
):
    """
    Given a dictionary of modules needed for this unit-test
    this prints their dependencies with the modules containing
    subs being the parents
    """
    arrow = "-->"
    modtree = []

    for sub in subs.values():
        depth = 0
        module_name = sub.module
        sub_module = mod_dict[module_name]
        modtree.append({"module": module_name, "depth": depth})
        depth += 1
        for mod in sub_module.modules.keys():
            modtree.append({"module": mod, "depth": depth})
            dep_mod = mod_dict[mod]
            if dep_mod.modules.keys():
                modtree = unravel_module_dependencies(
                    modtree=modtree, mod_dict=mod_dict, mod=dep_mod, depth=depth
                )
    return modtree


def parse_only_clause(line: str):
    """
    Input a line of the form: `use modname, only: name1,name2,...`
    """
    # get items after only:
    only_l = line.split(":")[1]
    only_l = only_l.split(",")

    only_objs_list = []
    # Go through list of objects, determine '=>' usage.
    for ptrobj in only_l:
        if "=>" in ptrobj:
            ptr, obj = ptrobj.split("=>")
            ptr = ptr.strip()
            obj = obj.strip()
            only_objs_list.append(PointerAlias(ptr=ptr, obj=obj))
        else:
            obj = ptrobj.strip()
            only_objs_list.append(PointerAlias(ptr=None, obj=obj))

    return only_objs_list


class FortranModule:
    """
    A class to represent a Fortran module.
    Main purpose is to store other modules required to
    compile the given file. To be used to determine the
    order in which to compile the modules.
    """

    def __init__(self, name, fname, ln):
        self.name = name  # name of the module
        self.global_vars = []  # any variables declared in the module
        self.subroutines = []  # any subroutines declared in the module
        self.modules = {}  # any modules used in the module
        self.filepath = fname  # the file path of the module
        self.ln = ln  # line number of start module block
        self.defined_types = {}  # user types defined in the module
        self.modified = False  # if module has been through modify_file or not.
        self.variables_sorted = False
        self.end_of_head_ln: int = 99999999

    def __repr__(self):
        return f"FortranModule({self.name})"

    def print_module_info(self, ofile=sys.stdout):
        """
        Function to print summary of FortranModule object
        """
        base_fn = "/".join(self.filepath.split("/")[-2:])
        ofile.write(
            _bc.BOLD + _bc.HEADER + f"Module Name: {self.name} {base_fn}\n" + _bc.ENDC
        )
        ofile.write(_bc.WARNING + "Module Depedencies:\n" + _bc.ENDC)

        for module, onlyclause in self.modules.items():
            if ofile:
                ofile.write(
                    _bc.WARNING
                    + "use "
                    + _bc.ENDC
                    + _bc.OKCYAN
                    + f"{module}"
                    + _bc.ENDC
                )
                if onlyclause == "all":
                    ofile.write("-> all\n")
                else:
                    ofile.write("->")
                    for ptrobj in onlyclause:
                        ofile.write(_bc.OKGREEN + f" {ptrobj.obj}," + _bc.ENDC)
                    ofile.write("\n")

        ofile.write(_bc.BOLD + _bc.WARNING + "Variables:\n" + _bc.ENDC)
        for variable in self.global_vars:
            print(_bc.OKGREEN + f"{variable}" + _bc.ENDC)

        ofile.write(_bc.WARNING + "User Types:\n" + _bc.ENDC)
        for utype in self.defined_types:
            ofile.write(_bc.OKGREEN + f"{self.defined_types[utype]}\n" + _bc.ENDC)

        return None

    def sort_used_variables(self, mod_dict, verbose=False):
        """
        Go through the used modules, if any variables are used,
        replace their string name with their variable instance.
        """
        func_name = "sort_used_vars"
        # return early if already called
        if self.variables_sorted:
            return None

        for used_mod_name, only_clause in self.modules.items():
            used_mod = mod_dict[used_mod_name]
            # go through `only` clause and check if any are global vars
            if only_clause != "all":
                for ptrobj in only_clause:
                    objname = ptrobj.obj
                    for var in used_mod.global_vars:
                        if objname == var.name:
                            ptrobj.obj = var
                            break
                    if verbose:
                        if isinstance(ptrobj.obj, str):
                            print(
                                f"{func_name}::{objname} from {used_mod_name} -- not Variable"
                            )
        self.variables_sorted = True
        return None
