import sys

import scripts.io.helper as hio
from scripts.DerivedType import DerivedType
from scripts.utilityFunctions import Variable

# def generate_land_weights_io() -> list[str]:
#     vars: dict[str, Variable] = {
#         'wt_lunit' : Variable(
#             name='wt_lunit',
#             type='real',
#             dim=3,
#             bounds='(begg:endg,1:max_topounits, max_lunit)',
#             declaration='elm_varsur',
#             subgrid='g',
#             ln=16,
#                  ),
#
#         'urban_valid' : Variable(
#             name='urban_valid',
#             type='logical',
#             dim=2,
#             bounds='(begg:endg,1:max_topounits)',
#             declaration='elm_varsur',
#             subgrid='g',
#             ln=16,
#                  ),
#
#         'wt_glc_mec' : Variable(
#             name='wt_glc_mec',
#             type='real',
#             dim=3,
#             bounds='(begg:endg,1:max_topounits, maxpatch_glcmec)',
#             declaration='elm_varsur',
#             subgrid='g',
#             ln=16,
#                  ),
#     }
#     return lines


def create_nc_define_vars(vars: dict[str, Variable],bounds: bool=False) -> list[str]:
    """
    Create Subroutine for defining netcdf variables
    """
    tabs = hio.indent()
    arg_str = ",bounds" if bounds else ''
    lines: list[str] = [f"{tabs}subroutine define_vars(ncid{arg_str})\n"]
    tabs = hio.indent(hio.Tab.shift)
    lines.append(f"{tabs}integer, intent(in) :: ncid\n")
    if bounds:
        lines.append(f"{tabs}type(bounds_type), intent(in) :: bounds\n")
    lines.append(f"{tabs}integer :: varid\n")
    lines.append(f"{tabs}character(len=32), dimension(4) :: dim_names\n")
    nc_defns = create_nc_def(vars)
    lines.extend(nc_defns)
    tabs = hio.indent(hio.Tab.unshift)
    lines.append(f"{tabs}end subroutine define_vars\n")

    return lines


def generate_elmtypes_io_netcdf(
    type_dict: dict[str, DerivedType],
    inst_to_dtype_map: dict[str, str],
    casedir: str,
):
    tabs = hio.indent(hio.Tab.reset)
    filename = "ReadWriteMod.F90"
    mod_name = filename.replace(".F90", "")


    lines: list[str] = []
    lines.extend(
        [
            f"module {mod_name}\n",
            f"{tabs}!!! Auto-generated Fortran code for netcdf-fortran I/O\n",
            f"{tabs}use netcdf\n",
            f"{tabs}use nc_io\n",
            f"{tabs}use nc_allocMod\n",
        ])

    active_instances = {
        inst_var.name: inst_var
        for dtype in type_dict.values()
        for inst_var in dtype.instances.values()
        if inst_var.active
    }
    use_statements = hio.var_use_statements(active_instances)
    lines.extend(list(use_statements))

    lines.extend(
        [
            f"{tabs}implicit none\n",
            f"{tabs}public :: read_elmtypes, write_elmtypes, define_vars\n",
            "contains\n",
        ]
    )

    dtype_vars: dict[str, Variable] = {}

    for inst_var in active_instances.values():
        type_name = inst_to_dtype_map[inst_var.name]
        dtype = type_dict[type_name]
        for field_var in dtype.components.values():
            if field_var.active:
                new_var = field_var.copy()
                new_var.name = f"{inst_var.name}%{field_var.name.split('%')[-1]}"
                dtype_vars[new_var.name] = new_var

    sub_lines = create_nc_define_vars(dtype_vars,bounds=True)
    lines.extend(sub_lines)

    sub_lines = create_netcdf_io_routine(
        mode=hio.IOMode.read,
        sub_name="read_elmtypes",
        vars=dtype_vars,
        bounds=True,
    )
    lines.extend(sub_lines)
    sub_lines = create_netcdf_io_routine(
        mode=hio.IOMode.write,
        sub_name="write_elmtypes",
        vars=dtype_vars,
        bounds=True,
    )
    lines.extend(sub_lines)

    lines.append(f"end module {mod_name}\n")

    with open(f"{casedir}/{filename}", "w") as ofile:
        ofile.writelines(lines)

    return


def generate_constants_io_netcdf(vars: dict[str, Variable], casedir: str):
    """
    Function generates fortran module for constants needed in unit-test
    """

    tabs = hio.indent(hio.Tab.reset)

    filename = "FUTConstantsMod.F90"
    mod_name = filename.replace(".F90", "")

    lines: list[str] = []
    lines.append(f"module {mod_name}\n")
    lines.append(f"{tabs}!!! Auto-generated Fortran code for netcdf-fortran I/O\n")
    lines.append(f"{tabs}use netcdf\n")
    lines.append(f"{tabs}use nc_io\n")
    lines.append(f"{tabs}use nc_allocMod\n")
    use_stmts = hio.var_use_statements(vars)
    lines.extend(use_stmts)

    lines.extend(
        [
            f"{tabs}implicit none\n",
            f"{tabs}public :: read_constants, write_constants, define_vars\n",
            "contains\n",
        ]
    )
    sub_lines = create_nc_define_vars(vars)
    lines.extend(sub_lines)

    sub_lines = create_netcdf_io_routine(
        hio.IOMode.read,
        "read_constants",
        vars,
    )

    lines.extend(sub_lines)

    sub_lines = create_netcdf_io_routine(
        hio.IOMode.write,
        "write_constants",
        vars,
    )
    lines.extend(sub_lines)

    tabs = hio.indent(hio.Tab.unshift)
    lines.extend(f"{tabs}end module {mod_name}\n")

    with open(f"{casedir}/{filename}", "w") as ofile:
        ofile.writelines(lines)

    return


def create_netcdf_io_routine(
    mode: hio.IOMode,
    sub_name: str,
    vars: dict[str, Variable],
    bounds: bool = False,
) -> list[str]:
    tabs = hio.indent()
    arg_str = ",bounds" if bounds else ''
    lines: list[str] = [f"{tabs}subroutine {sub_name}(nsets,fn{arg_str})\n"]
    tabs = hio.indent(hio.Tab.shift)

    mode_str = "create_file" if mode == hio.IOMode.write else "open_file"
    if mode == hio.IOMode.write:
        stmt = f"{tabs}type(bounds_type), intent(in) :: bounds\n" if bounds else ''
    else:
        stmt = f"{tabs}type(bounds_type), intent(inout) :: bounds\n" if bounds else ''

    # Arguments + Locals:
    lines.extend(
        [
            f"{tabs}integer, intent(in) :: nsets\n{stmt}\n",
            f"{tabs}character(len=*), intent(in) :: fn \n\n",
            f"{tabs}integer :: ncid\n",
            f"{tabs}ncid = nc_create_or_open_file(trim(fn), {mode_str})\n",
        ]
    )
    if mode == hio.IOMode.write:
        lines.extend([
                f"{tabs}call define_vars(ncid{arg_str})\n",
                f"{tabs}call check(nf90_enddef(ncid))\n",  # exit define mode:
            ]
        )
    if mode == hio.IOMode.read:
        sub_lines = create_nc_read(vars)
    else:
        sub_lines = create_nc_write(vars)
    lines.extend(sub_lines)
    tabs = hio.indent(hio.Tab.unshift)
    lines.append(f"{tabs}end subroutine {sub_name}\n")

    return lines


def create_nc_def(vars: dict[str, Variable]) -> list[str]:
    lines: list[str] = []
    tabs = hio.indent()

    for var in vars.values():
        dim_names_str = get_dim_names(var)
        varname = var.name.replace('%','__')
        nc_type = match_nc_type(var.type)
        if nc_type == "nf90_char":
            # Ex: call nc_define_var(ncid, 1,[len(nu_com)], ["nu_com"//"_str"], "nu_com",NF90_char, varid)
            dim_str = f"[len({var.name})]"
            dim=1
        else:
            dim_str = f"shape({var.name})" if var.dim>0 else "[0]"
            dim=var.dim
        if var.dim>0 or nc_type == "nf90_char":
            lines.append(f"{tabs}dim_names(1:{dim}) = {dim_names_str}\n")
        #                            file,   ndims,  shape    ,   [dim names]  ,  var name,    ncf type , varid
        stmt = f"call nc_define_var(ncid, {dim}, {dim_str}, dim_names, '{varname}', {nc_type}, varid)\n"
        lines.append(f"{tabs}{stmt}")
        # if array store lbounds and ubounds:
        if var.dim > 0:
            stmt = f"call check(nf90_put_att(ncid, varid, 'lbounds', lbound({var.name}))); call check(nf90_put_att(ncid, varid, 'ubounds', ubound({var.name})));"
            lines.append(f"{tabs}{stmt}\n")


    return lines


def get_dim_names(var: Variable) -> str:
    if var.dim == 0 and var.type != "character":
        return "['']"  # empty list
    elif var.type == "character":
        return f"[character(len=32) :: '{var.name}_str']"
    # Temp list to preprocess subgrids?
    dim_names = var.bounds.split(",")
    assert len(dim_names) == var.dim, f"(get_dim_names) Inconsistent dimensions\n name: {var.name}bounds: {var.bounds} dim: {var.dim}"
    dim_names = [f"'{hio.get_subgrid(dim)}'" for dim in dim_names]

    dim_str = ",".join(dim_names)
    return f"[character(len=32) :: {dim_str}]"


def match_nc_type(var_type: str) -> str:
    match var_type:
        case "real":
            return "nf90_double"
        case "integer":
            return "nf90_int"
        case "logical":
            return "nf90_int"
        case "character":
            return "nf90_char"
        case _:
            print(f"(match_nc_type) {var_type} Not Implemented")
            sys.exit(1)


def create_nc_write(vars: dict[str, Variable]) -> list[str]:
    """
    Function to create the
        call nc_write_var(ncid, dim, shape, dim_names, var, varname)
    or for characters:
        call nc_write_var(ncid, var, varname)
    """
    lines: list[str] = []
    tabs = hio.indent()

    scalars = [var for var in vars.values() if var.dim == 0]
    arrays = [var for var in vars.values() if var.dim > 0 ]

    for var in scalars:
        varname = var.name.replace('%','__')
        if var.type == "character":
            stmt = f"call nc_write_var_array(ncid, {var.name}, '{varname}')\n"
        else:
            stmt = f"call nc_write_var_scalar(ncid, {var.name}, '{varname}')\n"
        lines.append(f"{tabs}{stmt}")

    for var in arrays:
        dim_names_str = get_dim_names(var)
        reshape_str = f"reshape({var.name}, [product(shape({var.name}))])"
        varname = var.name.replace('%','__')
        stmt = f"call nc_write_var_array(ncid,{var.dim}, shape({var.name}), {dim_names_str}, {reshape_str}, '{varname}')\n"
        # lines.append(f"{tabs}print *, 'Writing {var.name}'\n")
        lines.append(f"{tabs}{stmt}")

    return lines


def create_nc_read(vars: dict[str, Variable]) -> list[str]:
    """
    Function to create the
        call nc_write_var(ncid, dim, shape, dim_names, var, varname)
    or for characters:
        call nc_write_var(ncid, var, varname)
    """
    lines: list[str] = []
    tabs = hio.indent()
    scalars = [var for var in vars.values() if var.dim == 0]
    arrays = [var for var in vars.values() if var.dim > 0]

    for var in scalars:
        varname = var.name.replace('%','__')
        if var.ptrscalar:
            lines.append(f"{tabs}allocate({var.name})\n")
        if var.type == "character":
            stmt = f"call nc_read_var(ncid, '{varname}', '{var.name}_str', {var.name})\n"
        else:
            stmt = f"call nc_read_var(ncid, '{varname}', {var.name})\n"
        lines.append(f"{tabs}{stmt}")

    for var in arrays:
        assert (
            var.type != "character"
        ), f"Error - Need to implement array of characters nc write for {var.name}"

        varname = var.name.replace('%','__')
        # lines.append(f"{tabs}print *, 'Reading {var.name}'\n")
        lines.append( f'{tabs}call nc_alloc(ncid, "{varname}", {var.dim}, {var.name})\n')
        stmt = f"call nc_read_var(ncid,'{varname}', {var.dim}, {var.name})\n"
        lines.append(f"{tabs}{stmt}")

    return lines

def generate_verify(rw_set: set[str], type_dict: dict[str,DerivedType]):
    """
    rw_set is set of active elmtypes with status of 'w' or 'rw'

    """
    lines: list[str] = []
    active_instances = {
        inst_var.name: inst_var
        for dtype in type_dict.values()
        for inst_var in dtype.instances.values()
        if inst_var.active
    }
    use_statements = hio.var_use_statements(active_instances)
    lines.extend(list(use_statements))

    return
