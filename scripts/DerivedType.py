import re
import subprocess as sp
import sys

import write_routines as wr
from fortran_modules import get_module_name_from_file
from mod_config import ELM_SRC
from utilityFunctions import Variable, parse_line_for_variables

## arrow and tab are strings for writing files or printing readable output
arrow = "|--->"
tab = " " * 2


def get_derived_type_definition(ifile, modname, lines, ln, type_name, verbose=False):
    """
    Now find definition of type to find components
    """
    func_name = "get_derived_type_definition"
    type_start_line = ln
    type_end_line = 0
    user_derived_type = DerivedType(type_name, vmod=modname, fpath=ifile)
    for ct in range(ln, len(lines)):
        line = lines[ct]
        l = line.split("!")[0]
        l = l.strip()
        # test to see if we exceeded type definition
        _end = re.search(r"^(end\s+type)", l)
        if not _end:
            data_type = re.compile(r"^\s*(real|integer|logical|character)")
            m = data_type.search(l)
            if m:
                datatype = m.group()
                lprime = re.sub(r"(?<={})(.+)(?=::)".format(datatype), "", l)

                # remove => null()
                lprime = re.sub(r"(\s*=>\s*null\(\))", "", lprime)
                variable_list = parse_line_for_variables(ifile=ifile, l=lprime, ln=ct)
                if verbose:
                    print(f"vars : {[x.name for x in variable_list]}")
                for var in variable_list:
                    user_derived_type._add_components(
                        var_inst=var, lines=lines, ln=type_start_line, verbose=verbose
                    )
        else:
            type_end_line = ct
            break
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
    # Each element in output has the format:
    # <filepath> : <ln> : type(<type_name>) :: <instance_name>
    instance_list = []
    if output:
        output = output.split("\n")
        for el in output:
            inst_name = el.split("::")[-1]
            inst_name = inst_name.split("!")[0].strip().lower()

            filepath = el.split(":")[0].strip()
            ln = int(el.split(":")[1].strip())
            # Get module name
            mod_ln, module_name = get_module_name_from_file(filepath)

            dim = inst_name.count(":")
            inst_var = Variable(
                type=type_name,
                name=inst_name,
                subgrid="?",
                ln=ln,
                dim=dim,
                declaration=module_name,
            )
            if inst_var not in instance_list:
                instance_list.append(inst_var)
                if verbose:
                    print(f"Adding instance {type_name} {inst_name},{dim}")

    user_derived_type.instances = instance_list[:]

    return user_derived_type, ct


class DerivedType(object):
    def __init__(
        self,
        type_name,
        vmod,  # name of type and module name
        fpath=None,  # path to mod file
        components=None,  # list of type and component name
        instances=[],  # list of global variables with this type
    ):
        self.type_name = type_name
        if fpath:
            self.mod = fpath
        else:
            self.mod = ""
            cmd = f'find {ELM_SRC}  \( -path "*external_models*" \) -prune -o  -name "{vmod}.F90" '
            output = sp.getoutput(cmd)
            if not output:
                sys.exit(f"Couldn't locate file {vmod}")
            else:
                output = output.split("\n")
                for el in output:
                    if "external_models" not in el:
                        self.mod = el
        if not self.mod:
            sys.exit(
                f"Couldn't find file for {type_name}\ncmd:{cmd}\n" f"output: {output}\n"
            )

        self.declaration = vmod
        self.components = []
        self.instances = []
        # Flag to see if Derived Type has been analyzed
        self.analyzed = False
        self.active = False

    def __repr__(self):
        return f"DerivedType({self.type_name})"

    def _add_components(self, var_inst, lines, ln, verbose=False):
        """
        Function to add components to the derived type.
        If it's an array, the function looks for allocation statements
        """
        name = var_inst.name
        if var_inst.dim > 0:
            array = True
        else:
            array = False
        name_component = "%" + name
        datatype = var_inst.type

        if verbose:
            print(f"Adding component {datatype} {name} to {self.type_name}")

        # Need to find the allocation of component
        # to get the bounds.  Necessary for duplicateMod.F90 creation
        if array:
            for ln in range(ln, len(lines)):
                line = lines[ln]
                # Get rid of comments
                line = line.split("!")[0].strip().lower()
                # Generate regex for allocate statments
                alloc = re.compile(
                    r"^(allocate)\s*(.+)({}\s*\()".format(name_component)
                )
                match_alloc = alloc.search(line)
                if match_alloc:
                    regex_b = re.compile(r"(?<=(%{}))\s*\((.+?)\)".format(name))
                    bounds = regex_b.search(line).group()
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

                    self.components.append(
                        {"active": False, "var": var_inst, "bounds": bounds}
                    )
                    break
        else:
            self.components.append({"active": False, "var": var_inst, "bounds": None})
        return

    def print_derived_type(self, ofile=sys.stdout, long=False):
        """
        Function to print info on the user derived type
        """
        ofile.write("Derived Type:" + self.type_name + "\n")
        ofile.write("from Mod:" + self.mod + "\n")
        for v in self.instances:
            ofile.write(f"{v.type} {v.name} {v.declaration}\n")
        if long:
            ofile.write("w/ components:")
            for c in self.components:
                status = c["active"]
                var = c["var"]
                if var.dim > 0:
                    bounds = c["bounds"]
                else:
                    bounds = ""
                str_ = f"  {status} {var.type} {var.name} {bounds} {str(var.dim)}-D"
                ofile.write(str_ + "\n")

    # def analyzeDerivedType(self, verbose=False):
    #     #
    #     # This function will open each mod file, find the variable type
    #     # and fill out the components of the variable
    #     #
    #     import subprocess as sp
    #     import sys

    #     found_declaration = False
    #     # First need to check if declaration is in elm_instMod
    #     name = self.name
    #     cmd = f'grep -in -E "::[[:space:]]*({name})" {ELM_SRC}/main/elm_instMod.F90'
    #     cmd2 = f'grep -in -E "::[[:space:]]*({name})" {ELM_SRC}/dyn_subgrid/dynSubgridDriverMod.F90'
    #     output1 = sp.getoutput(cmd)
    #     output2 = sp.getoutput(cmd2)
    #     output = ""
    #     if output1:
    #         output = output1
    #         self.declaration = "elm_instMod"
    #     if output2 and not (output1) and "intent" not in output2:
    #         output = output2
    #         self.declaration = "dynSubgridDriverMod"
    #     if output:
    #         output = output.replace(":", " ")
    #         output = output.split()
    #         dec_linenum = output[0]
    #         # find what's in the parentheses
    #         par = re.compile("(?<=\()(\w+)(?=\))")
    #         m = par.search(output[1])
    #         if not m:
    #             print(output)
    #         inner_str = m.group()
    #         self.dtype = inner_str
    #         found_declaration = True
    #         print(f"declaration in {self.declaration}")
    #     try:
    #         if verbose:
    #             print(f"{self.name} Opening file: {self.fpath}")
    #         ifile = open(self.fpath)
    #     except:
    #         print("ERROR: file ", self.fpath, "not found")
    #         exit(1)

    #     # Find declaration of variable
    #     lines = ifile.readlines()
    #     var = self.name
    #     if not found_declaration:
    #         for l in lines:
    #             line = l.split("!")[0]
    #             line = line.strip()
    #             m_type = re.search(f"^(type)", line)
    #             match = re.search(f"::\s*({var})", line)
    #             if match and m_type:
    #                 # find what's in the parentheses
    #                 par = re.compile("(?<=\()(\w+)(?=\))")
    #                 m = par.search(line)
    #                 if not m:
    #                     print("Error in analyzeDerivedType")
    #                     print(line)
    #                     print(f"var : {var} , file = {self.fpath} ")
    #                     sys.exit()
    #                 inner_str = m.group()
    #                 self.dtype = inner_str
    #                 if verbose:
    #                     print(f"{self.name} -- Found type {self.dtype}")
    #                 found_declaration = True
    #                 break

    #     if not found_declaration:
    #         print("ERROR:  Couldn't find declaration of", var)
    #         print("in file", self.mod)
    #         exit(1)

    #     # Now find definition of type to find components!
    #     get_derived_type_definition(ifile, modname, lines, ln, type_name, verbose=False)
    #     ifile.close()
    #     if type_start_line == 0:
    #         print(f"Error couldn't analyze type {self.name} {self.dtype}")
    #         sys.exit()
    #     self.analyzed = True

    def create_write_read_functions(self, rw, ofile, gpu=False):
        #
        # This function will write two .F90 functions
        # that write read and write statements for all
        # components of the derived type
        #
        # rw is a variable that holds either read or write mode
        #
        fates_list = ["veg_pp%is_veg", "veg_pp%is_bareground", "veg_pp%wt_ed"]
        for var in self.instances:
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

                # Any component of the derived type accessed by the Unit Test
                # should have been toggled active at this point.
                # Go through the instance of this derived type and write I/O
                # for any active components.
                vars = []
                for n, component in enumerate(self.components):
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

                # Any component of the derived type accessed by the Unit Test
                # should have been toggled active at this point.
                # Go through the instance of this derived type and write I/O
                # for any active components.
                for component in self.components:
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
