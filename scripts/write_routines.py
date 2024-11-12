import re
import subprocess as sp
import sys
from collections import namedtuple

from analyze_subroutines import Subroutine
from fortran_modules import get_module_name_from_file
from mod_config import (ELM_SRC, PHYSICAL_PROP_TYPE_LIST, _bc, elm_dir_regex,
                        preproc_list, shr_dir_regex, spel_mods_dir,
                        spel_output_dir, unit_test_files)
from utilityFunctions import (comment_line, find_file_for_subroutine,
                              getArguments, line_unwrapper)

TAB_WIDTH = 2
indent = 1


def set_indent(mode):
    global indent
    global TAB_WIDTH
    match mode:
        case "shift":
            indent += 1
        case "unshift":
            indent -= 1
        case "reset":
            indent = 1
    return " " * TAB_WIDTH * indent


def get_delta_from_dim(dim, delta):
    """
    this function will parse the dimension string to find if it's
    a patch, col, land, topo, or grid index
    """
    newdim = []
    bool = False
    if not dim:
        newdim = ""
        return newdim

    dim = dim.replace("(", "")
    dim = dim.replace(")", "")
    dim_li = dim.split(",")

    if delta == "y":
        for el in dim_li:
            if "begp" in el and "endp" in el:
                newdim.append("begp:endp")  # newdim.append('nc*deltap+1:(nc+1)*deltap')
            elif "begc" in el and "endc" in el:
                newdim.append("begc:endc")
            elif "begl" in el and "endl" in el:
                newdim.append("begl:endl")
            elif "begg" in el and "endg" in el:
                newdim.append("begg:endg")
            elif "begt" in el and "endt" in el:
                newdim.append("begt:endt")
            else:
                newdim.append(":")

    if delta == "n":
        for el in dim_li:
            if "begp" in el and "endp" in el:
                newdim.append("begp_copy:endp_copy")
            elif "begc" in el and "endc" in el:
                newdim.append("begc_copy:endc_copy")
            elif "begl" in el and "endl" in el:
                newdim.append("begl_copy:endl_copy")
            elif "begg" in el and "endg" in el:
                newdim.append("begg_copy:endg_copy")
            elif "begt" in el and "endt" in el:
                newdim.append("begt_copy:endt_copy")
            else:
                newdim.append(":")

    newdim = ",".join(newdim)
    newdim = "(" + newdim + ")"

    return newdim


def generate_makefile(files, case_dir):
    """
    This function takes the list of needed files
    and generates a makefile and finally saves it in the case dir
    """
    from edit_files import macros

    noF90 = [elm_dir_regex.sub("", f) for f in files]
    noF90 = [shr_dir_regex.sub("", f) for f in noF90]
    object_list = [f.replace(".F90", ".o") for f in noF90]

    FC = "nvfortran"
    FC_FLAGS_ACC = " -gpu=deepcopy -Minfo=accel -acc -cuda\n"
    FC_FLAGS_DEBUG = " -g -O0 -Mbounds -Mchkptr -Mchkstk\n"
    # MODEL_FLAGS = " -DMODAL_AER "
    MODEL_FLAGS = "-D" + " -D".join(macros)

    # Get complete preproccesor flags:
    for f in noF90:
        if f in preproc_list:
            temp = f.upper()
            MODEL_FLAGS = MODEL_FLAGS + " -D" + temp

    MODEL_FLAGS = MODEL_FLAGS + "\n"

    ofile = open(f"{case_dir}/Makefile", "w")
    ofile.write("FC= " + FC + "\n")
    ofile.write("FC_FLAGS_ACC= " + FC_FLAGS_ACC)
    ofile.write("FC_FLAGS_DEBUG = " + FC_FLAGS_DEBUG)
    ofile.write("MODEL_FLAGS= " + MODEL_FLAGS)
    ofile.write('INCLUDE_DIR = "${CURDIR}"\n')
    ofile.write("FC_FLAGS = $(FC_FLAGS_DEBUG) $(MODEL_FLAGS)" + "\n")
    ofile.write("TEST = $(findstring acc,$(FC_FLAGS))\n")

    # Create string of ordered objct files.
    unit_test_objs = " ".join(unit_test_files)
    objs = " ".join(object_list)
    ofile.write("objects = " + objs + " " + unit_test_objs + "\n")

    ofile.write("elmtest.exe : $(objects)" + "\n")
    ofile.write("\t" + "$(FC) $(FC_FLAGS) -o elmtest.exe $(objects)" + "\n")
    ofile.write("\n\n")
    ofile.write("#.SUFFIXES: .o .F90" + "\n")
    # These files do not need to be compiled with ACC flags or optimizations
    # Can cause errors or very long compile times
    noopt_list = ["fileio_mod", "ReadConstantsMod", "readMod", "duplicateMod"]
    for f in noopt_list:
        ofile.write(f"{f}.o : {f}.F90" + "\n")
        ofile.write("\t" + "$(FC) -O0 -c $(MODEL_FLAGS) $<" + "\n")

    ofile.write("%.o : %.F90" + "\n")
    ofile.write("\t" + "$(FC) $(FC_FLAGS) -c -I $(INCLUDE_DIR) $<" + "\n")

    ofile.write("ifeq (,$(TEST))\n")
    ofile.write("verificationMod.o : verificationMod.F90\n")
    ofile.write("\t" + "$(FC) -O0 -c $<\n")
    ofile.write("else\n")
    ofile.write("verificationMod.o : verificationMod.F90\n")
    ofile.write("\t" + "$(FC) -O0 -gpu=deepcopy -acc -c $<\n")
    ofile.write("endif\n")

    ofile.write("\n\n" + ".PHONY: clean" + "\n")
    ofile.write("clean:" + "\n")
    ofile.write("\t" + "rm -f *.mod *.o *.exe" + "\n")
    ofile.close()


def write_elminstMod(typedict, case_dir):
    """
    Writes elm_instMod to contain only variable decalarations
    needed for this Unit Test
    """
    file = open(f"{case_dir}/elm_instMod.F90", "w")
    spaces = " " * 2
    file.write("module elm_instMod\n")
    # use statements
    for type_name, dtype in typedict.items():
        for gv in dtype.instances.values():
            if gv.declaration == "elm_instmod":
                file.write(spaces + f"use {dtype.declaration}, only : { type_name }\n")

    file.write(spaces + "implicit none\n")
    file.write(spaces + "save\n")
    file.write(spaces + "public\n")
    for type_name, dtype in typedict.items():
        for gv in dtype.instances.values():
            if gv.declaration == "elm_instmod":
                file.write(spaces + f"type({type_name}) :: {gv.name}\n")

    file.write("end module elm_instMod\n")
    file.close()


def clean_use_statements(mod_list, file, case_dir):
    from edit_files import comment_line

    """
     function that will clean both initializeParameters
     and readConstants
    """
    ifile = open(f"{spel_mods_dir}{file}.F90", "r")
    lines = ifile.readlines()
    ifile.close()

    noF90 = [elm_dir_regex.sub("", f) for f in mod_list]
    noF90 = [shr_dir_regex.sub("", f) for f in noF90]

    # Doesn't account for module names not being the same as file names
    noF90 = [f.replace(".F90", "") for f in noF90]

    start = "!#USE_START"
    end = "!#USE_END"
    analyze = False
    ct = 0
    while ct < len(lines):
        line = lines[ct]
        if line.strip() == start:
            analyze = True
            ct += 1
            continue
        if line.strip() == end:
            analyze = False
            break
        if analyze:
            l = line.split("!")[0]
            mod = l.split()[1]
            if mod not in noF90:
                lines, ct = comment_line(lines=lines, ct=ct, verbose=False)
        ct += 1
    with open(f"{case_dir}/{file}.F90", "w") as ofile:
        ofile.writelines(lines)


def insert_at_token(lines, token, lines_to_add):
    regex_token = re.compile(r"^\s*({})".format(token))
    ln = 0
    token_line = 0
    found_token = False
    ln = 0
    while not found_token:
        line = lines[ln]
        m_token = regex_token.search(line)
        if m_token:
            token_line = ln
            found_token = True
        else:
            ln += 1

    if token_line == 0:
        print("Error: could find '!#USE_START' in main.F90")
        sys.exit(1)

    for line_add in lines_to_add:
        lines.insert(token_line + 1, line_add)

    return lines


def find_parent_subroutine_call(
    subroutines: dict[str, Subroutine],
    type_dict,
    inst_to_type,
):
    """
    Function that for a list of Subroutines, finds a call signature to
    insert into main.F90

    Returns only one result, so if a function is used in several places,
    manual modification may be required
    """

    search_file = ELM_SRC
    mods_to_add = []
    var_decl_to_add = []
    calls = []

    for sub in subroutines.values():
        name = sub.name
        cmd = f'grep -rin -E "^[[:space:]]*(call[[:space:]]* {name})\\b" {search_file} | head -1'
        output = sp.getoutput(cmd)
        output = output.split(":")
        filename = output[0]
        call_ln = int(output[1]) - 1

        ifile = open(filename, "r")
        lines = ifile.readlines()
        ifile.close()

        ct = call_ln
        call_string, ct = line_unwrapper(lines, ct)
        delta_ln = ct - call_ln + 1
        calls.extend(lines[call_ln : call_ln + delta_ln])
        args = getArguments(call_string)

        # Search backwards from subroutine call to get the calling subroutine :
        subname = None
        for ln in range(call_ln, -1, -1):
            line = lines[ln]
            match_sub = re.search(r"^\s*(subroutine)\s+", line)
            if match_sub:
                full_line, _ = line_unwrapper(lines, ln)
                split_str = match_sub.group().strip()
                subname = full_line.split(split_str)[1].split("(")[0].strip()
                print("Found Subroutine:\n", subname)
                break

        if not subname:
            print(f"Error::Couldn't find calling subroutine for {sub.name}")
            sys.exit(1)
        fn, startl, endl = find_file_for_subroutine(name=subname, fn=filename)
        parent_sub = Subroutine(subname, fn, [""], start=startl, end=endl)

        args_as_vars = {}
        args_as_instances = {}
        for arg in args:
            argname = arg.split("%")[0]
            if argname in inst_to_type:
                type_name = inst_to_type[argname]
                dtype = type_dict[type_name]
                inst_var = dtype.instances[argname]
                args_as_instances[inst_var.name] = inst_var
                if not inst_var.active:
                    type_dict[type_name].instances[argname].active = True

        args_not_found = [
            arg for arg in args if arg.split("%")[0] not in args_as_instances
        ]
        args_to_search = args_not_found.copy()

        for arg in args_to_search:
            if arg in parent_sub.Arguments:
                argvar = parent_sub.Arguments[arg]
                if argvar.type in type_dict:
                    # Choose an instance?
                    inst_var = type_dict[argvar.type].instances[0]
                    args_as_instances[inst_var.name] = inst_var
                else:
                    args_as_vars[arg] = parent_sub.Arguments[arg]
            elif arg in parent_sub.LocalVariables["arrays"]:
                args_as_vars[arg] = parent_sub.LocalVariables["arrays"][arg]
            elif arg in parent_sub.LocalVariables["scalars"]:
                args_as_vars[arg] = parent_sub.LocalVariables["scalars"][arg]
            else:
                print(_bc.FAIL + "STILL CAN'T FIND ARGS (non-derived type global var?)")

        # Variables to have declarations added to main.F90
        if args_as_vars:
            for argvar in args_as_vars.values():
                type_string = argvar.type
                if type_string not in ["real", "integer", "character", "logical"]:
                    type_string = f"type({type_string})"
                elif type_string == "real":
                    type_string = f"{type_string}(r8)"
                decl = f"{type_string} :: {argvar.name}{argvar.bounds}"
                if decl + "\n" not in var_decl_to_add:
                    var_decl_to_add.append(decl + "\n")

        # Global variables , access through module interface
        if args_as_instances:
            for inst in args_as_instances.values():
                use_statement = f"use {inst.declaration}, only : {inst.name}"
                if use_statement + "\n" not in mods_to_add:
                    mods_to_add.append(use_statement + "\n")

    Additions = namedtuple("Additions", ["calls", "mods", "vars"])

    return Additions(calls=calls, mods=mods_to_add, vars=var_decl_to_add)


def prepare_main(subroutines, type_dict, instance_to_type, casedir):
    """
    Function to insert USE dependencies into main.F90 and subroutine calls for the FUT subs
    """
    iofile = open(f"{spel_mods_dir}main.F90", "r")
    lines = iofile.readlines()
    iofile.close()

    use_token = "!#USE_START"
    var_token = "!#VAR_DECL"
    call_token = "!#CALL_SUB"
    modules_to_add = []
    for s in subroutines.values():
        _, mod = get_module_name_from_file(s.filepath)
        modules_to_add.append(f"use {mod}, only : {s.name}\n")

    additions = find_parent_subroutine_call(subroutines, type_dict, instance_to_type)

    modules_to_add.extend(additions.mods)

    lines = insert_at_token(lines=lines, token=use_token, lines_to_add=modules_to_add)
    lines = insert_at_token(lines=lines, token=var_token, lines_to_add=additions.vars)
    lines = insert_at_token(
        lines=lines, token=call_token, lines_to_add=reversed(additions.calls)
    )
    with open(f"{casedir}/main.F90", "w") as iofile:
        iofile.writelines(lines)

    return None


def prepare_unit_test_files(
    inst_list,
    type_dict,
    files,
    case_dir,
    global_vars,
    subroutines,
    instance_to_type,
):
    """
    This function will prepare the use headers of main, initializeParameters,
    and readConstants.  It will also clean the variable initializations and
    declarations in main and elm_instMod
    """
    prepare_main(subroutines, type_dict, instance_to_type, case_dir)
    create_constants_io(mode="r", global_vars=global_vars, casedir=case_dir)
    create_constants_io(mode="w", global_vars=global_vars, casedir=case_dir)
    clean_use_statements(mod_list=files, file="initializeParameters", case_dir=case_dir)
    clean_use_statements(mod_list=files, file="elm_initializeMod", case_dir=case_dir)
    clean_use_statements(mod_list=files, file="update_accMod", case_dir=case_dir)
    allocations_to_add = create_type_allocators(type_dict, case_dir)

    ifile = open(f"{case_dir}/elm_initializeMod.F90", "r")
    lines = ifile.readlines()
    ifile.close()

    type_init_token = "!#VAR_INIT_START"
    lines = insert_at_token(
        lines=lines, token=type_init_token, lines_to_add=allocations_to_add
    )

    # write adjusted main to file in case dir
    with open(f"{case_dir}/elm_initializeMod.F90", "w") as of:
        of.writelines(lines)

    # Write DeepCopyMod for UnitTest
    create_deepcopy_module(type_dict, case_dir)

    return


def duplicate_clumps(typedict):
    """
    Function that writes a Fortran module containing
    subroutines needed to duplicate the input data
    to an arbirtary number of gridcells
    """
    file = open(f"{spel_output_dir}duplicateMod.F90", "w")
    spaces = " " * 2
    file.write("module duplicateMod\n")
    file.write("contains\n")

    file.write("subroutine duplicate_weights(unique_sites,total_gridcells)\n")
    file.write(spaces + "use elm_varsur, only : wt_lunit, urban_valid\n")
    file.write(spaces + "implicit none\n")
    file.write(spaces + "integer, intent(in) :: unique_sites\n")
    file.write(spaces + "integer, intent(in) :: total_gridcells\n")
    file.write(spaces + "integer :: g, dim3, l, gcopy\n")
    file.write(spaces + "dim3 = size(wt_lunit,3)\n")
    file.write(spaces + "print *, 'dim3 = ',dim3\n")
    file.write(spaces + "do g = unique_sites+1, total_gridcells\n")
    file.write(spaces + spaces + "gcopy = mod(g-1,unique_sites)+1\n")
    file.write(spaces + spaces + "do l=1,dim3\n")
    file.write(spaces * 3 + "wt_lunit(g,1,l) = wt_lunit(gcopy,1,l)\n")
    file.write(spaces * 2 + "end do\n")
    file.write(spaces * 2 + "urban_valid(g,1) = urban_valid(gcopy,1)\n")
    file.write(spaces + "end do\n")
    file.write("end subroutine duplicate_weights\n")

    file.write("subroutine duplicate_clumps(mode,unique_sites,num_sites)\n")

    # Use statements
    for type_name, dtype in typedict.items():
        if dtype.active:
            for var in dtype.instances.values():
                if var.active:
                    mod = var.declaration
                    vname = var.name
                    file.write(spaces + "use {}, only : {}\n".format(mod, vname))

    file.write(
        spaces + "use decompMod, only : bounds_type, get_clump_bounds, procinfo\n"
    )
    file.write(spaces + "use elm_varcon\n")
    file.write(spaces + "use elm_varpar\n")
    file.write(spaces + "use elm_varctl\n")
    file.write(spaces + "use landunit_varcon\n")
    file.write(spaces + "implicit none\n")
    file.write(spaces + "integer, intent(in) :: mode, unique_sites, num_sites\n")
    file.write(spaces + "type(bounds_type)  :: bounds_copy, bounds\n")
    file.write(spaces + "integer :: errcode, nc,nc_copy, nclumps\n")
    file.write(spaces + "integer :: begp_copy, endp_copy, begp, endp\n")
    file.write(spaces + "integer :: begc_copy, endc_copy, begc, endc\n")
    file.write(spaces + "integer :: begg_copy, endg_copy, begg, endg\n")
    file.write(spaces + "integer :: begt_copy, endt_copy, begt, endt\n")
    file.write(spaces + "integer :: begl_copy, endl_copy, begl, endl\n")
    file.write(spaces + "nclumps = num_sites\n")
    #
    file.write(spaces + "if(mode == 0) then\n")
    file.write(spaces * 2 + "do nc=unique_sites+1, num_sites\n")
    file.write(spaces * 3 + "nc_copy = mod(nc-1,unique_sites)+1\n")
    file.write(spaces * 3 + "call get_clump_bounds(nc,bounds)\n")
    file.write(spaces * 3 + "call get_clump_bounds(nc_copy,bounds_copy)\n")

    file.write(spaces * 3 + "begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg\n")
    file.write(spaces * 3 + "begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt\n")
    file.write(spaces * 3 + "begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl\n")
    file.write(spaces * 3 + "begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc\n")
    file.write(spaces * 3 + "begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp\n")

    file.write(spaces * 3 + "begg=bounds%begg; endg=bounds%endg\n")
    file.write(spaces * 3 + "begt=bounds%begt; endt=bounds%endt\n")
    file.write(spaces * 3 + "begl=bounds%begl; endl=bounds%endl\n")
    file.write(spaces * 3 + "begc=bounds%begc; endc=bounds%endc\n")
    file.write(spaces * 3 + "begp=bounds%begp; endp=bounds%endp\n")

    # First create mode for duplicating decomp related data.
    ignore_list = ["is_veg", "is_bareground", "wt_ed"]
    for type_name, dtype in typedict.items():
        if dtype.active and type_name in PHYSICAL_PROP_TYPE_LIST:
            for var in dtype.instances.values():
                if var.active:
                    for c in dtype.components.values():
                        active = c["active"]
                        field_var = c["var"]
                        bounds = c["bounds"]
                        if not active:
                            continue
                        if field_var.name in ignore_list:
                            continue
                        fname = var.name + "%" + field_var.name
                        dim = bounds
                        newdim = get_delta_from_dim(dim, "y")
                        dim1 = get_delta_from_dim(dim, "n")
                        dim1 = dim1.replace("_all", "")
                        if newdim == "(:)" or newdim == "":
                            continue
                        file.write(spaces * 3 + fname + newdim + " &" + "\n")
                        file.write(spaces * 4 + "= " + fname + dim1 + "\n")

    file.write(spaces * 2 + "end do\n")

    file.write(spaces + "else\n")
    file.write(spaces * 2 + "do nc=unique_sites+1, num_sites\n")
    file.write(spaces * 3 + "nc_copy = mod(nc-1,unique_sites)+1\n")
    file.write(spaces * 3 + "call get_clump_bounds(nc,bounds)\n")
    file.write(spaces * 3 + "call get_clump_bounds(nc_copy,bounds_copy)\n")

    file.write(spaces * 3 + "begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg\n")
    file.write(spaces * 3 + "begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt\n")
    file.write(spaces * 3 + "begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl\n")
    file.write(spaces * 3 + "begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc\n")
    file.write(spaces * 3 + "begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp\n")

    file.write(spaces * 3 + "begg=bounds%begg; endg=bounds%endg\n")
    file.write(spaces * 3 + "begt=bounds%begt; endt=bounds%endt\n")
    file.write(spaces * 3 + "begl=bounds%begl; endl=bounds%endl\n")
    file.write(spaces * 3 + "begc=bounds%begc; endc=bounds%endc\n")
    file.write(spaces * 3 + "begp=bounds%begp; endp=bounds%endp\n")

    # Duplicate statements for unit test variables
    for type_name, dtype in typedict.items():
        if dtype.active and type_name not in PHYSICAL_PROP_TYPE_LIST:
            for var in dtype.instances.values():
                if not var.active:
                    continue
                for c in dtype.components.values():
                    active = c["active"]
                    field_var = c["var"]
                    bounds = c["bounds"]
                    if not active:
                        continue
                    fname = var.name + "%" + field_var.name
                    dim = bounds
                    newdim = get_delta_from_dim(dim, "y")
                    dim1 = get_delta_from_dim(dim, "n")
                    dim1 = dim1.replace("_all", "")
                    if newdim == "(:)" or newdim == "":
                        continue
                    file.write(spaces * 3 + fname + newdim + " &" + "\n")
                    file.write(spaces * 4 + "= " + fname + dim1 + "\n")

    file.write(spaces + "end do\n")
    file.write(spaces + "end if\n")

    file.write("end subroutine duplicate_clumps\n")
    file.write("end module\n")
    file.close()


def create_constants_io(mode, global_vars, casedir):
    """
    Function to create either readConstantsMod or writeConstantsMod
    """
    filename = "ReadConstantsMod.F90" if mode == "r" else "WriteConstantsMod.F90"

    tab = " " * TAB_WIDTH
    indent = 1
    lines = []
    mod_name = filename.replace(".F90", "")
    lines.append(f"module {mod_name}\n")
    lines.append("implicit None\n")
    lines.append("contains\n")
    sub_name = mod_name.replace("Mod", "")
    tabs = tab * indent
    lines.append(f"{tabs}subroutine {sub_name}()\n")

    indent += 1
    tabs += tab * indent
    for gv in global_vars.values():
        if gv.parameter or not gv.active:
            continue
        lines.append(f"{tabs}use {gv.declaration}, only : {gv.name}\n")
    lines.append(tabs + "use fileio_mod, only : fio_open, fio_close\n")
    if mode == "r":
        lines.append(tabs + "use fileio_mod, only : fio_read\n")
    lines.append(tabs + "integer :: fid, errcode=0\n")
    lines.append(tabs + 'character(len=64) :: ofile = "E3SM_constants.txt"\n')
    lines.append(tabs + "fid = 23\n")
    lines.append(tabs + "call fio_open(fid,ofile, 2)\n\n")
    for gv in global_vars.values():
        if gv.parameter or not gv.active:
            continue
        if mode != "r":
            lines.append(f'{tabs}write(fid,"(A)") "{gv.name}"\n')
            lines.append(f"{tabs}write(fid,*) {gv.name}\n")
        else:
            str1 = f"{tabs}call fio_read(18,'{gv.name}', {gv.name}, errcode=errcode)\n"
            str2 = f"{tabs}if (errcode .ne. 0) stop\n"
            lines.append(str1)
            lines.append(str2)

    lines.append(f"{tabs}call fio_close(fid)\n")
    indent -= 1
    tabs = tab * indent
    lines.append(f"{tabs}end subroutine {sub_name}\n")
    lines.append(f"end module {mod_name}")

    with open(f"{casedir}/{filename}", "w") as ofile:
        ofile.writelines(lines)

    return None


def create_write_vars(typedict, subname, use_isotopes=False):
    """
    This function generates the subroutine write_vars that is to be called from
    E3SM prior to execution of the desired subroutine
        * typedict : dictionary of all derived types related to Unit Test with
                     needed ones toggled by dtype.active = True
        * subname  : used to name file written by `write_vars`
        * use_isotopes : flag toggles c13/c14 vars.
    """
    func_name = "create_write_vars"
    spaces = " " * 2  # holds tabs indentations without using \t
    ofile = open(f"{spel_output_dir}writeMod.F90", "w")
    ofile.write("module writeMod\n")
    ofile.write("contains\n")
    ofile.write("subroutine write_vars()\n")
    ofile.write(spaces + "use fileio_mod, only : fio_open, fio_close\n")
    ofile.write(spaces + "use elm_varsur, only : wt_lunit, urban_valid\n")

    # Use statements
    for type_name, dtype in typedict.items():
        if dtype.active:
            for var in dtype.instances.values():
                if var.active:
                    c13c14 = bool("c13" in var.name or "c14" in var.name)
                    if c13c14:
                        continue
                    mod = var.declaration
                    ofile.write(spaces + "use {}, only : {}\n".format(mod, var.name))

    ofile.write(spaces + "implicit none\n")
    ofile.write(spaces + "integer :: fid\n")
    ofile.write(spaces + f'character(len=64) :: ofile = "{subname}_vars.txt"\n')
    ofile.write(spaces + "fid = 23\n")

    for dtype in typedict.values():
        if dtype.active:
            dtype.create_write_read_functions("w", ofile, gpu=True)

    # TODO: can't decide if icemask_grc is needed by default.
    # glc2lnd_vars%icemask:
    # ofile.write(spaces+"write(fid,'(A)') 'glc2lnd_vars%icemask_grc'\n")
    # ofile.write(spaces+'write(fid,*) glc2lnd_vars%icemask_grc')

    for dtype in typedict.values():
        if dtype.active:
            dtype.create_write_read_functions("w", ofile, gpu=True)

    ofile.write(spaces + "call fio_open(fid,ofile, 2)\n\n")
    ofile.write(spaces + 'write(fid,"(A)") "wt_lunit"\n')
    ofile.write(spaces + "write(fid,*) wt_lunit\n")
    ofile.write(spaces + 'write(fid,"(A)") "urban_valid"\n')
    ofile.write(spaces + "write(fid,*) urban_valid\n\n")

    # Add I/O statements for each component of needed derived types.
    #  the physical property types will be done first.
    for dtype in typedict.values():
        if dtype.active and dtype.type_name in PHYSICAL_PROP_TYPE_LIST:
            dtype.create_write_read_functions("w", ofile)

    for dtype in typedict.values():
        if dtype.active and dtype.type_name not in PHYSICAL_PROP_TYPE_LIST:
            dtype.create_write_read_functions("w", ofile)

    ofile.write(spaces + "call fio_close(fid)\n")
    ofile.write("end subroutine write_vars\n")
    ofile.write("end module writeMod\n")
    ofile.close()


def create_read_vars(typedict):
    """
    Function that creates the readMod.F90 file similar to writeMod.F90.
    """
    # TODO:Incorporate the ability to use I/O libraries like netcdf if desired.
    #     Original purpose of unit test is to be as light weight as possible, but
    #     netCDF may allow more flexibility for generating unit tests of larger scale
    #     such as for EcosystemDynNoLeaching2.
    spaces = " " * 2
    ofile = open(f"{spel_output_dir}readMod.F90", "w")
    ofile.write("module readMod\n")

    # Use Statements
    for key in typedict.keys():
        for var in typedict[key].instances.values():
            if var.active:
                mod = var.declaration
                vname = var.name
                c13c14 = bool("c13" in vname or "c14" in vname)
                if c13c14:
                    continue
                ofile.write("use {}, only : {}\n".format(mod, vname))

    # The remaining use statements are for decomp vars
    ofile.write("use decompMod, only : bounds_type\n")
    ofile.write("use elm_varcon\n")
    ofile.write("use elm_varpar\n")
    ofile.write("use elm_varctl\n")
    ofile.write("use landunit_varcon\n")
    ofile.write("use elm_instMod, only: glc2lnd_vars\n")

    ofile.write("contains\n")

    # Subroutine read_weights
    ofile.write("subroutine read_weights(in_file,numg)\n")
    ofile.write(spaces + "use fileio_mod, only : fio_open, fio_read, fio_close\n")
    ofile.write(spaces + "use elm_varsur, only : wt_lunit, urban_valid\n")
    ofile.write(spaces + "implicit none\n")
    ofile.write(spaces + "character(len=256), intent(in) :: in_file\n")
    ofile.write(spaces + "integer, intent(in) :: numg\n")
    ofile.write(spaces + "integer :: errcode = 0\n\n")
    ofile.write(spaces + "call fio_open(18,in_file,1)\n")
    ofile.write(
        spaces + "call fio_read(18,'wt_lunit',wt_lunit(1:numg,1,:),errcode=errcode)\n"
    )
    ofile.write(spaces + "if(errcode .ne. 0) stop\n")
    ofile.write(
        spaces
        + "call fio_read(18,'urban_valid',urban_valid(1:numg,1),errcode=errcode)\n"
    )
    ofile.write(spaces + "if(errcode .ne. 0) stop\n\n")
    ofile.write(spaces + "end subroutine read_weights\n\n")

    # Beginning of Subroutine `read_vars`
    ofile.write("subroutine read_vars(in_file,bounds,mode,nsets)\n")
    ofile.write(spaces + "use fileio_mod, only : fio_open, fio_read, fio_close\n")
    ofile.write(spaces + "implicit none\n")

    # Dummy Variables
    ofile.write(spaces + "character(len=256),intent(in) :: in_file\n")
    ofile.write(spaces + "type(bounds_type), intent(in) :: bounds\n")
    ofile.write(spaces + "integer, intent(in) :: mode\n")
    ofile.write(spaces + "integer, intent(in) :: nsets\n")

    # Local Variables
    ofile.write(spaces + "integer :: errcode = 0\n")
    ofile.write(spaces + "integer :: begp,  endp\n")
    ofile.write(spaces + "integer :: begc,  endc\n")
    ofile.write(spaces + "integer :: begg,  endg;\n")
    ofile.write(spaces + "integer :: begl,  endt;\n")
    ofile.write(spaces + "integer :: begt,  endl;\n")
    #
    ofile.write(spaces + "begp = bounds%begp; endp = bounds%endp/nsets\n")
    ofile.write(spaces + "begc = bounds%begc; endc = bounds%endc/nsets\n")
    ofile.write(spaces + "begl = bounds%begl; endl = bounds%endl/nsets\n")
    ofile.write(spaces + "begt = bounds%begt; endt = bounds%endt/nsets\n")
    ofile.write(spaces + "begg = bounds%begg; endg = bounds%endg/nsets\n")

    ofile.write(spaces + 'print *,"begp range :",begp, endp\n')
    ofile.write(spaces + 'print *,"begc range :",begc, endc\n')
    ofile.write(spaces + 'print *,"begl range :",begl, endl\n')
    ofile.write(spaces + 'print *,"begt range :",begt, endt\n')
    ofile.write(spaces + 'print *,"begg range :",begg, endg\n')

    ofile.write(spaces + "call fio_open(18,in_file, 1)\n")
    ofile.write(spaces + "if(mode == 1) then\n")
    ofile.write(spaces + "print *, 'reading in physical properties'\n")

    # Start with physical property types
    for dtype in typedict.values():
        if dtype.active and dtype.type_name in PHYSICAL_PROP_TYPE_LIST:
            dtype.create_write_read_functions("r", ofile)
    ofile.write(spaces + "else\n")

    for dtype in typedict.values():
        if dtype.active and dtype.type_name not in PHYSICAL_PROP_TYPE_LIST:
            dtype.create_write_read_functions("r", ofile)

    ofile.write(spaces + "end if\n")
    ofile.write(spaces + "call fio_close(18)\n")
    ofile.write("end subroutine read_vars\n")
    ofile.write("end module\n")
    ofile.close()


def create_pointer_type_sub(lines, dtype, all_active=False):
    tabs = set_indent("reset")

    lines.append(f"{tabs}subroutine set_pointers_{dtype.type_name}(this_type)\n")
    tabs = set_indent("shift")
    inst_dim = max([inst.dim for inst in dtype.instances.values()])
    dim_string = ""
    if inst_dim == 1:
        dim_string = "(:)"
    else:
        print(f"ERROR: {dtype.type_name} inst.dim > 1 may need extra care")
        sys.exit(1)
    lines.append(
        f"{tabs}type({dtype.type_name}), intent(inout) :: this_type{dim_string}\n"
    )

    # Allocate the instance based on the number of unique targets for the pointer fields:
    num_targets = 0
    for member in dtype.components.values():
        member_var = member["var"]
        active = member["active"]
        num_targets_new = len(member_var.pointer)
        if num_targets == 0:
            num_targets = num_targets_new
        elif num_targets_new != num_targets:
            print(f"WARNING::{dtype} pointers with inconsistent targets")
            sys.exit(1)


def create_type_sub(lines, dtype, all_active=False):
    """
    Functiion that creates a subroutine to allocate
    the active members of dtype
    Arguments
        * lines : lines corresponding to the Module to be written (ie. Read/WriteConstantsMod)
        * dtype : DerivedType obj of type to allocate
        * all_active : Allocate all members regardless of use in UnitTest
    """
    tabs = set_indent("reset")

    lines.append(f"{tabs}subroutine allocate_{dtype.type_name}(bounds,this_type)\n")
    tabs = set_indent("shift")
    lines.append(f"{tabs}type(bounds_type), intent(in) :: bounds\n")
    inst_dim = max([inst.dim for inst in dtype.instances.values()])
    if inst_dim == 0:
        lines.append(f"{tabs}type({dtype.type_name}), intent(inout) :: this_type\n")
    elif inst_dim == 1:
        lines.append(f"{tabs}type({dtype.type_name}), intent(inout) :: this_type(:)\n")
    else:
        print(f"ERROR: {dtype.type_name} inst.dim > 1 may need extra care")
        sys.exit(1)
    lines.append(tabs + "integer :: begp, endp\n")
    lines.append(tabs + "integer :: begc, endc\n")
    lines.append(tabs + "integer :: begl, endl\n")
    lines.append(tabs + "integer :: begt, endt\n")
    lines.append(tabs + "integer :: begg, endg\n")
    if inst_dim == 1:
        lines.append(tabs + "integer :: i,N\n")
    lines.append(tabs + "!-------------------------------------\n")
    lines.append(tabs + "begp = bounds%begp; endp = bounds%endp\n")
    lines.append(tabs + "begc = bounds%begc; endc = bounds%endc\n")
    lines.append(tabs + "begl = bounds%begl; endl = bounds%endl\n")
    lines.append(tabs + "begg = bounds%begg; endg = bounds%endg\n")
    lines.append(tabs + "begt = bounds%begt; endt = bounds%endt\n")

    if inst_dim == 1:
        lines.append(f"{tabs}N=size(this_type)\n")
        lines.append(tabs + "do i = 1, N\n")
        tabs = set_indent("shift")
    inst_name = "this_type" if inst_dim == 0 else "this_type(i)"
    for member in dtype.components.values():
        member_var = member["var"]
        active = member["active"]
        if active:
            dim_string = ""
            if member_var.dim > 0:
                dim_li = [":" for i in range(0, member_var.dim)]
                dim_string = ",".join(dim_li)
                dim_string = f"({dim_string})"
                bounds = member["bounds"].strip()
                statement = f"{tabs}allocate({inst_name}%{member_var.name}{bounds});"
                lines.append(statement)
            elif member_var.ptrscalar:
                statement = f"{tabs}allocate({inst_name}%{member_var.name});"
                lines.append(statement)

            init_val = None
            match member_var.type:
                case "real":
                    init_val = "spval"
                case "integer":
                    init_val = "ispval"
                case "logical":
                    init_val = ".False."
                case "character":
                    init_val = "''"

            if not init_val:
                print(f"Error: No init_val for {member_var}")
                sys.exit(1)
            init_statement = f"{inst_name}%{member_var.name}{dim_string} = {init_val}\n"
            lines.append(init_statement)

    # End subroutine:
    tabs = set_indent("unshift")
    lines.append(f"{tabs}end subroutine allocate_{dtype.type_name}\n\n")
    return lines


def create_type_allocators(type_dict, casedir):
    """
    function to creates a fortran module to allocate the active
    members of derived types
    """

    filename = "UnitTestAllocatorMod"
    lines = []
    indent = 0
    tab = " " * TAB_WIDTH
    indent += 1
    tabs = tab * indent

    skip_types = [
        "clumpfilter",
        "vegetation_physical_properties",
        "column_physical_properties",
        "landunit_physical_properties",
        "gridcell_physical_properties_type",
        "topounit_physical_properties",
    ]
    lines.append(f"module {filename}\n")
    lines.append(f"{tabs}use elm_varcon\n")
    lines.append(f"{tabs}use elm_varpar\n")
    lines.append(f"{tabs}use decompMod ,only : bounds_type\n")

    active_instances = {
        inst_var.name: inst_var
        for dtype in type_dict.values()
        for inst_var in dtype.instances.values()
        if inst_var.active
    }
    active_types = {inst_var.type: True for inst_var in active_instances.values()}

    for type_name in active_types:
        if type_name in skip_types:
            continue
        dtype = type_dict[type_name]
        statement = f"{tabs}use {dtype.declaration},only: {type_name}\n"
        if statement not in lines:
            lines.append(statement)
    lines.append(f"{tabs}implicit None\n")

    for type_name in active_types:
        if type_name in skip_types:
            continue
        statement = f"{tabs} public :: allocate_{type_name}\n"
        lines.append(statement)

    lines.append(f"{tabs}contains\n")

    # Generate type allocator subroutines:
    for type_name in active_types:
        if type_name in skip_types:
            continue
        dtype = type_dict[type_name]
        lines = create_type_sub(lines, dtype)

    lines.append(f"end module {filename}")

    with open(f"{casedir}/{filename}.F90", "w") as ofile:
        ofile.writelines(lines)

    # Return list of subroutine calls to be inserted in elm_init
    allocations = []
    tabs = " " * 6
    for inst in active_instances.values():
        if inst.type in skip_types or "c13" in inst.name or "c14" in inst.name:
            continue
        statement = f"{tabs}call allocate_{inst.type}(bounds_proc,{inst.name})\n"
        if statement not in allocations:
            allocations.append(statement)

    return allocations


def create_deepcopy_subroutine(lines, dtype, all_active=False):
    """
    Function to generate a subroutine for dtype that manually
    copies over the active members of dtype.
        if all_active = True, all members are considered active
    """
    tabs = set_indent("reset")
    array1d = False
    scalar = False
    for inst in dtype.instances.values():
        if inst.dim == 0:
            scalar = True
        elif inst.dim == 1:
            array1d = True
        else:
            print(_bc.WARNING + f"WARNING:Instance dim > 1D: {inst}" + _bc.ENDC)

    members_to_copy = [
        comp["var"]
        for comp in dtype.components.values()
        if comp["active"] or all_active
    ]
    if scalar:
        subname = f"deepcopy_{dtype.type_name}"
        lines.append(f"{tabs}subroutine {subname}(this_type)\n")
        tabs = set_indent("shift")
        lines.append(f"{tabs}type({dtype.type_name}), intent(inout) :: this_type\n")
        lines.append(f"{tabs}!$acc enter data copyin(this_type)\n")
        lines.append(f"{tabs}!$acc enter data copyin(&\n")
        for num, member in enumerate(members_to_copy):
            dim_string = ""
            if member.dim > 0:
                dim_li = [":" for i in range(0, member.dim)]
                dim_string = ",".join(dim_li)
                dim_string = f"({dim_string})"

            name = "this_type" + "%" + member.name + dim_string
            lines.append(f"{tabs}!$acc& {name}")
            final_num = bool(num == len(members_to_copy) - 1)
            if not final_num:
                lines.append(",&\n")
            else:
                lines.append(")")
        lines.append("\n")
        tabs = set_indent("unshift")
        lines.append(f"{tabs}end subroutine {subname}\n")

    if array1d:
        subname = f"deepcopy_{dtype.type_name}_array"
        lines.append(f"{tabs}subroutine {subname}(this_type)\n")
        tabs = set_indent("shift")
        lines.append(f"{tabs}type({dtype.type_name}), intent(inout) :: this_type(:)\n")
        lines.append(f"{tabs}integer :: i,N\n")
        lines.append(f"{tabs}N=size(this_type)\n")
        lines.append(f"{tabs}!$acc enter data copyin(this_type(:))\n")
        lines.append(tabs + "do i = 1, N\n")
        tabs = set_indent("shift")

        inst_name = "this_type(i)"
        lines.append(f"{tabs}!$acc enter data copyin(&\n")
        for num, member in enumerate(members_to_copy):
            dim_string = ""
            if member.dim > 0:
                dim_li = [":" for i in range(0, member.dim)]
                dim_string = ",".join(dim_li)
                dim_string = f"({dim_string})"

            name = inst_name + "%" + member.name + dim_string
            lines.append(f"{tabs}!$acc& {name}")
            final_num = bool(num == len(members_to_copy) - 1)
            if not final_num:
                lines.append(",&\n")
            else:
                lines.append(")")
        lines.append("\n")
        tabs = set_indent("unshift")
        lines.append("end do\n")
        tabs = set_indent("unshift")
        lines.append(f"{tabs}end subroutine {subname}\n")

    return lines


def create_deepcopy_module(type_dict, casedir):
    """
    Function to create subroutine(s) for performing a manual deepcopy
    """
    tabs = set_indent("reset")
    lines = []

    lines.append("module DeepCopyMod\n")

    active_instances = {
        inst_var.name: inst_var
        for dtype in type_dict.values()
        for inst_var in dtype.instances.values()
        if inst_var.active
    }
    active_types = {inst_var.type: True for inst_var in active_instances.values()}

    for type_name in active_types:
        dtype = type_dict[type_name]
        statement = f"{tabs}use {dtype.declaration},only: {type_name}\n"
        if statement not in lines:
            lines.append(statement)
    lines.append(f"{tabs}implicit none\n")

    for type_name in active_types:
        statement = f"{tabs}public :: deepcopy_{type_name}\n"
        lines.append(statement)
    lines.append("contains\n\n")

    for type_name in active_types:
        dtype = type_dict[type_name]
        lines = create_deepcopy_subroutine(lines, dtype)

    lines.append("end module DeepCopyMod")

    with open(f"{casedir}/DeepCopyMod.F90", "w") as ofile:
        ofile.writelines(lines)
    return None
