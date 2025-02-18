import re
import subprocess as sp
import sys
from typing import Dict, Optional

import scripts.write_routines as wr
from scripts.fortran_modules import get_module_name_from_file
from scripts.mod_config import ELM_SRC, _bc, _no_colors
from scripts.utilityFunctions import (Variable, line_unwrapper,
                                      parse_line_for_variables)

## arrow and tab are strings for writing files or printing readable output
arrow = "|--->"
tab = " " * 2


def get_derived_type_definition(ifile, modname, lines, ln, type_name, verbose=False):
    """
    Function to retrieve the definition (i.e., members) of user derived types.
    1) The type definition is parsed and a list of the Variable members is stored.
    2) Pass list of members to _add_components where arrays/pointers are further processed.
    3) Find any instances of derived type.
    """
    func_name = "get_derived_type_definition"
    type_start_line = ln
    type_end_line = 0
    user_derived_type = DerivedType(type_name, vmod=modname, fpath=ifile)

    regex_contains = re.compile(r"\b(contains)\b")
    regex_end_type = re.compile(r"^(end\s+type)")

    member_list = []
    ct = ln
    while ct < len(lines):
        full_line, ct = line_unwrapper(lines, ct)
        full_line = full_line.strip().lower()
        # test to see if we exceeded type definition
        _end = regex_end_type.search(full_line)
        _contains = regex_contains.search(full_line)
        if _contains:
            ct = user_derived_type.get_type_procedures(regex_end_type, lines, ct)
            type_end_line = ct
            break

        if not _end:
            data_type = re.compile(r"^\s*(real|integer|logical|character)")
            m = data_type.search(full_line)
            if m:
                datatype = m.group()
                match_pointer = re.search(r"\b(pointer)\b", full_line)
                if match_pointer:
                    pot_ptr = True
                else:
                    pot_ptr = False
                lprime = re.sub(r"(?<={})(.+)(?=::)".format(datatype), "", full_line)
                lprime = re.sub(r"(\s*=>\s*null\(\))", "", lprime)
                variable_list = parse_line_for_variables(
                    ifile=ifile, l=lprime, ln=ct, ptr=pot_ptr, verbose=verbose,
                )
                if verbose:
                    print(f"variable list : {variable_list}")
                member_list.extend(variable_list)
        else:
            type_end_line = ct
            break
        ct += 1

    user_derived_type._add_components(member_list, lines, type_end_line, verbose)
    # Sanity check
    if type_end_line == 0:
        print("Error couldn't analyze type ", type_name)
        print(f"File: {ifile}, start line {ln}")
        sys.exit(1)

    # Find all instances of the derived type:
    grep = "grep -rin --exclude-dir=external_models/"
    cmd = (
        f'{grep} "type\s*(\s*{type_name}\s*)" {ELM_SRC}* | grep "::" | grep -v "intent"'
    )
    output = sp.getoutput(cmd)

    regex_paren = re.compile(r"\((.+)\)")
    #
    # Each element in output should have the format:
    # <filepath> : <ln> : type(<type_name>) :: <instance_name>
    instance_list = {}
    if output:
        output = output.split("\n")
        for el in output:
            inst_name = el.split("::")[-1]
            inst_name = inst_name.split("!")[0].strip().lower()

            filepath = el.split(":")[0].strip()
            ln = int(el.split(":")[1].strip())
            mod_ln, module_name = get_module_name_from_file(filepath)

            dim = inst_name.count(":")
            inst_name = regex_paren.sub("", inst_name)

            inst_var = Variable(
                type=type_name,
                name=inst_name,
                subgrid="?",
                ln=ln,
                dim=dim,
                declaration=module_name,
            )
            if inst_var.name not in instance_list:
                instance_list[inst_var.name] = inst_var
                if verbose:
                    print(f"Adding instance {type_name} {inst_name},{dim}")

    user_derived_type.instances = instance_list.copy()

    return user_derived_type, ct


class DerivedType(object):
    """
    Class to represent Fortran user-derived type
    """
    def __init__(
        self,
        type_name,
        vmod,  # module name
        fpath=None,  # path to mod file
        components=None,  # list of type and component name
        instances={},
    ):
        self.type_name = type_name
        if fpath:
            self.filepath = fpath
        else:
            self.filepath = ""
            cmd = f'find {ELM_SRC}  \( -path "*external_models*" \) -prune -o  -name "{vmod}.F90" '
            output = sp.getoutput(cmd)
            if not output:
                sys.exit(f"Couldn't locate file {vmod}")
            else:
                output = output.split("\n")
                for el in output:
                    if "external_models" not in el:
                        self.filepath = el

        if not self.filepath:
            sys.exit(
                f"Couldn't find file for {type_name}\ncmd:{cmd}\n" f"output: {output}\n"
            )

        self.declaration = vmod
        self.components = {}
        self.instances: dict[str, Variable] = {}
        # Flag to see if Derived Type has been analyzed
        self.analyzed = False
        self.active = False
        self.init_sub = None
        self.procedures: dict[str,str] = {}

    def __repr__(self):
        return f"DerivedType({self.type_name})"

    def _add_components(
        self,
        member_list: list[Variable],
        lines,
        type_end,
        verbose=False,
    ):
        """
        Function to add components to the derived type.
        If it's an array, the function looks for allocation statements, storing the bounds.

        Arguments:
            var_inst : Variable representing component to add
            lines : lines of files containing type definition
            ln : line number to start with.
        """
        debug = False
        member_arr_or_ptr = {var.name: var for var in member_list if var.dim > 0}
        _arrptr_names = ["%" + varname for varname in member_arr_or_ptr.keys()]
        member_match_string = "|".join(_arrptr_names)

        regex_alloc = re.compile(
            r"^(allocate)\s*(.+)({})\b(\s*\()".format(member_match_string)
        )
        regex_ptr_init = re.compile(r"({})\b\s*(=>)(.+)".format(member_match_string))
        regex_member_name = re.compile(r"({})\b".format(member_match_string))

        member_scalars = {var.name: var for var in member_list if var.dim == 0}

        added_member_to_type = {var.name: False for var in member_arr_or_ptr.values()}
        if member_arr_or_ptr:
            init_sub = None
            subname = None
            ln = type_end
            while ln < len(lines):
                full_line, ln = line_unwrapper(lines, ln)
                full_line = full_line.strip().lower()
                match_sub = re.search(
                    r"(^\s*subroutine|function)\s+", full_line, re.IGNORECASE
                )
                if match_sub:
                    split_str = match_sub.group().strip()
                    subname = full_line.split(split_str)[1].split("(")[0]

                match_alloc = regex_alloc.findall(full_line)
                match_ptrinit = regex_ptr_init.search(full_line)
                if match_ptrinit:
                    if not subname:
                        print(self.type_name)
                        print(match_ptrinit)
                    init_sub = subname
                    member_name = match_ptrinit.groups()[0].replace("%", "")
                    target = match_ptrinit.groups()[2].strip()
                    if added_member_to_type[member_name]:
                        var_inst = self.components[member_name]["var"]
                        if target not in var_inst.pointer:
                            var_inst.pointer.append(target)
                            self.components[member_name]["var"] = var_inst
                        ln += 1
                        continue
                    else:
                        var_inst = member_arr_or_ptr[member_name]
                        if var_inst.pointer:
                            print("Error there should not be any targets yet!!")
                            print(full_line)
                            print("member: ", member_name, "target", target)
                            print(f"Exising targets: {var_inst.pointer}")
                            print(member_arr_or_ptr)
                            print(member_arr_or_ptr[member_name])
                            sys.exit(0)
                        var_inst.pointer.append(target)
                        member = {"active": False, "var": var_inst, "bounds": None}
                        self.components[var_inst.name] = member
                        added_member_to_type[member_name] = True

                elif match_alloc:
                    init_sub = subname
                    members_matched = regex_member_name.findall(full_line)
                    members_matched = list(set(members_matched))
                    if debug:
                        print("match_alloc:", match_alloc)
                        print("Member matched:", members_matched)
                    for varname in members_matched:
                        varname = varname.replace("%", "")
                        if added_member_to_type[varname]:
                            continue
                        var_inst = member_arr_or_ptr[varname]
                        regex_b = re.compile(r"(?<=(%{}))\s*\((.+?)\)".format(varname))
                        bounds = regex_b.search(full_line).group()
                        var_inst.bounds = bounds.strip()
                        beg_x = re.search(r"(?<=(beg))[a-z]", bounds, re.IGNORECASE)
                        if beg_x:
                            end_x = re.search(r"(?<=(end))[a-z]", bounds, re.IGNORECASE)
                            if beg_x.group() != end_x.group():
                                print(
                                    f"Error: subgrid differs {beg_x.group()} {end_x.group()}"
                                )
                                sys.exit(1)
                            else:
                                var_inst.subgrid = beg_x.group()

                        member = {"active": False, "var": var_inst, "bounds": bounds}
                        self.components[var_inst.name] = member
                        added_member_to_type[varname] = True
                ln += 1
            if not init_sub:
                print(
                    _bc.WARNING
                    + f"No initialization routine found for {self.type_name}"
                    + _bc.ENDC
                )
                print(member_arr_or_ptr)
            else:
                self.init_sub = init_sub

        for scalar in member_scalars.values():
            self.components[scalar.name] = {
                "active": False,
                "var": scalar,
                "bounds": None,
            }
        if debug:
            sys.exit()

        return None

    def print_derived_type(self, ofile=sys.stdout, long=False) -> None:
        """
        Function to print info on the user derived type
        """
        if ofile == sys.stdout:
            hl = _bc
        else:
            hl = _no_colors

        ofile.write(hl.HEADER + "Derived Type:" + self.type_name + "\n" + hl.ENDC)
        base_fn = "/".join(self.filepath.split("/")[-2:])
        ofile.write(hl.HEADER + "from Mod: " + base_fn + "\n" + hl.ENDC)
        for v in self.instances.values():
            ofile.write(hl.OKBLUE + f"{v.type} {v.name} {v.declaration}\n" + hl.ENDC)
        ofile.write(hl.WARNING + f"Initialized in {self.init_sub} \n" + hl.ENDC)
        if self.procedures:
            ofile.write(hl.OKGREEN + f"Type Procedures:\n")
            for alias, proc in self.procedures.items():
                if alias != proc:
                    ofile.write(f"{alias} => {proc}\n")
                else:
                    ofile.write(f"{alias}\n")
            ofile.write(hl.ENDC)
        if long:
            ofile.write("w/ components:\n")
            for c in self.components.values():
                status = c["active"]
                var = c["var"]
                if var.dim > 0:
                    bounds = c["bounds"]
                else:
                    bounds = ""
                if not var.pointer:
                    str_ = f"  {status} {var.type} {var.name} {bounds} {str(var.dim)}-D"
                else:
                    targets = "|".join(var.pointer)
                    str_ = f"  {status} {var.type} {var.name} => {var.pointer}"
                ofile.write(str_ + "\n")
        return None

    def create_write_read_functions(self, rw, ofile, gpu=False):
        """
        This function will write two .F90 functions that write read and write statements for all
        components of the derived type
        rw is a variable that holds either read or write mode
        """

        fates_list = ["veg_pp%is_veg", "veg_pp%is_bareground", "veg_pp%wt_ed"]
        for var in self.instances.values():
            if not var.active:
                continue
            if rw.lower() == "write" or rw.lower() == "w":
                ofile.write(tab + "\n")
                ofile.write(
                    tab
                    + "!====================== {} ======================!\n".format(
                        var.name
                    )
                )
                ofile.write(tab + "\n")
                if gpu:
                    ofile.write(tab + "!$acc update self(& \n")

                # Any component of the derived type accessed by the Unit Test should have been toggled active at this point.
                # Go through the instance of this derived type and write I/O for any active components.
                vars = []
                for component in self.components.values():
                    active = component["active"]
                    field_var = component["var"]
                    if not active:
                        continue

                    # Filter out C13/C14 duplicates and fates only variables.
                    c13c14 = bool("c13" in field_var.name or "c14" in field_var.name)
                    if c13c14:
                        continue
                    fname = var.name + "%" + field_var.name
                    if fname in fates_list:
                        continue
                    if gpu:
                        vars.append(fname)
                    else:
                        str1 = f'write (fid, "(A)") "{fname}" \n'
                        str2 = f"write (fid, *) {fname}\n"
                        ofile.write(tab + str1)
                        ofile.write(tab + str2)
                if gpu:
                    for n, v in enumerate(vars):
                        if n + 1 < len(vars):
                            ofile.write(tab + f"!$acc {v}, &\n")
                        else:
                            ofile.write(tab + f"!$acc {v} )\n")
            elif rw.lower() == "read" or rw.lower() == "r":
                ofile.write(tab + "\n")
                ofile.write(
                    tab
                    + "!====================== {} ======================!\n".format(
                        var.name
                    )
                )
                ofile.write(tab + "\n")

                # Any component of the derived type accessed by the Unit Test should have been toggled active at this point.
                # Go through the instance of this derived type and write I/O for any active components.
                for component in self.components.values():
                    active = component["active"]
                    field_var = component["var"]
                    bounds = component["bounds"]
                    if not active:
                        continue
                    c13c14 = bool("c13" in field_var.name or "c14" in field_var.name)
                    if c13c14:
                        continue
                    fname = var.name + "%" + field_var.name
                    if fname in fates_list:
                        continue
                    dim = bounds
                    dim1 = wr.get_delta_from_dim(dim, "y")
                    dim1 = dim1.replace("_all", "")
                    str1 = "call fio_read(18,'{}', {}{}, errcode=errcode)\n".format(
                        fname, fname, dim1
                    )
                    str2 = "if (errcode .ne. 0) stop\n"
                    ofile.write(tab + str1)
                    ofile.write(tab + str2)

    def manual_deep_copy(self, ofile=sys.stdout):
        """
        Function that generates pragmas for manual deepcopy of members
        """
        chunksize = 3
        tabs = " " * 3
        depth = 1
        for inst in self.instances.values():
            inst_name = inst.name
            ofile.write(tabs * depth + f"!$acc enter data copyin({inst_name})\n")
            if inst.dim == 1:
                ofile.write(tabs * depth + f"N = size({inst.name})\n")
                ofile.write(tabs * depth + "do i = 1, N\n")
                inst_name = inst.name + "(i)"
                depth += 1
            elif inst.dim > 1:
                print("Error: multi-dimensional Array of Structs found: ", inst)
                sys.exit(1)
            ofile.write(tabs * depth + "!$acc enter data copyin(&\n")
            for num, comp in enumerate(self.components.values()):
                member = comp["var"]
                dim_string = ""
                if member.dim > 0:
                    dim_li = [":" for i in range(0, member.dim)]
                    dim_string = ",".join(dim_li)
                    dim_string = f"({dim_string})"

                name = inst_name + "%" + member.name + dim_string
                ofile.write(tabs * depth + f"!$acc& {name}")
                final_num = bool(num == len(self.components.keys()) - 1)
                if not final_num:
                    ofile.write(",&\n")
                else:
                    ofile.write(")")
            ofile.write("\n")
            depth -= 1
            if inst.dim == 1:
                ofile.write(tabs * depth + "end do\n")

        return None

    def get_type_procedures(self, regex_end, lines, ln):
        """
        Function
        """
        func_name = "get_type_procedures::"
        regex_proc = re.compile(r"^(procedure)\b")

        ln += 1
        full_line, ln = line_unwrapper(lines, ln)
        m_end = regex_end.search(full_line)
        while not m_end:
            m_proc = regex_proc.search(full_line)
            if m_proc:
                if "::" not in full_line:
                    print(
                        f"{func_name}Error-type proc syntax unaccounted for\n{full_line}"
                    )
                    sys.exit(1)

                proc_string = full_line.split("::")[1]
                if "=>" in proc_string:
                    # There's an alias:
                    split_str = proc_string.split("=>")
                    alias = split_str[0].strip()
                    proc_name = split_str[1].strip()
                else:
                    alias = proc_string.strip()
                    proc_name = alias
                    if "," in proc_name:
                        print(
                            f"{func_name}Error - multiple procedures declared on same line?\n{full_line}"
                        )
                        sys.exit(1)
                self.procedures[alias] = proc_name
            ln += 1
            full_line, ln = line_unwrapper(lines, ln)
            m_end = regex_end.search(full_line)

        return ln

def get_component(instance_dict: Dict[str, DerivedType], dtype_field: str)->Optional[Variable]:
    """
    Function that looks up inst%field in the instance dict.
    """
    regex_paren = re.compile(r"\((.+)\)") # for removing array of struct index
    inst_name, field = dtype_field.split('%')
    inst_name = regex_paren.sub("",inst_name)
    dtype = instance_dict[inst_name]
    if field in dtype.components:
        var: Variable = dtype.components[field]['var']
        return var
    else:
        if field not in dtype.procedures:
            print (f"Error- Couldn't categorize {dtype_field}")
        return None

def expand_dtype(dtype_vars: list[Variable], type_dict: dict[str, DerivedType])->dict[str,Variable]:

    """Function to take a dtype and create a dict with a key for each var%field"""
    def adj_var_name(var,inst_var):
        dim_str = "(index)" if inst_var.dim>0 else ""
        var.name = f"{ inst_var.name }{dim_str}%{var.name}"
        return var

    result: dict[str,Variable] = {}
    for dtype_var in dtype_vars:
        dtype = type_dict[dtype_var.type]
        fields = dtype.components.values()
        temp: dict[str,Variable] = {
          f"{dtype_var.name}%{field['var'].name}": adj_var_name(field['var'],dtype_var) for field in fields
        }
        result.update(temp)
    return result


