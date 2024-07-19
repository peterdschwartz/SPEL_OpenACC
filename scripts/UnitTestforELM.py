# arrow and tab are strings for writing files or printing readable output
arrow = '|--->'
tab   = ' '*2
from mod_config import _bc

def main():
    """
    Edit case_dir and sub_name_list to create a Functional Unit Test 
    in a directory called {case_dir} for the subroutines in sub_name_list.
    """
    import sys
    import os
    from analyze_subroutines import Subroutine
    from utilityFunctions import insert_header_for_unittest, Variable
    import write_routines as wr
    from mod_config import default_mods, unittests_dir, scripts_dir, spel_mods_dir
    from mod_config import ELM_SRC, spel_output_dir
    from edit_files import process_for_unit_test
    import subprocess as sp
    import csv 
    func_name = 'main'
    # Note unittests_dir is a location to make unit tests directories named {casename}
    casename = "LakeTemp"
    case_dir = unittests_dir + casename
    # List of subroutines to be analyzed
    sub_name_list = ["SoilTemperature"]

    # Determines if SPEL should run to make optimizations 
    opt = False
    add_acc = False
    adjust_allocation = False  
    preprocess = False 

    # Create script output directory if not present:
    if(not os.path.isdir(f"{scripts_dir}/script-output")):
        print("Making script output directory")
        os.system(f"mkdir {scripts_dir}/script-output")
    
    #Create case directory 
    if(not os.path.isdir(f"{case_dir}") ):
        print(f"Making case directory {case_dir}")
        if(not os.path.isdir(f"{unittests_dir}")):
            os.system(f"mkdir {unittests_dir}")
        os.system(f"mkdir {case_dir}")
        preprocess = True
    else:
        x = input(f"case {case_dir} already exists - Preprocess?")
        if(x == 'n'):
            preprocess = False
        elif(x == 'y'):
            preprocess = True
        else:
            sys.exit("Error - input not recognized") 

    main_sub_dict = {}

    # Initialize list of derived types to 
    read_types  = [] 
    write_types = []
    sub_name_list = [s.lower() for s in sub_name_list]
    subroutines = {k:[] for k in sub_name_list}
    # List to hold all the modules needed for the unit test
    needed_mods = [] 
    for s in sub_name_list:
        # Get general info of the subroutine
        subroutines[s] = Subroutine(s,calltree=['elm_drv'])

        # Process by removing certain modules and syntax
        # so that a standalone unit test can be compiled.
        if(preprocess and not opt):
            fn = subroutines[s].filepath
            mod_dict, file_list = process_for_unit_test(fname=fn,case_dir=case_dir,
                                    mods=needed_mods,required_mods=default_mods, 
                                    main_sub_dict=main_sub_dict,
                                    overwrite=False,verbose=False)
            
            subroutines[s] = main_sub_dict[s]
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
    # examineLoops performs adjustments that go beyond the "naive"                  #
    # reliance on the "!$acc routine" directive.                                    #
    #    * adjust_allocation : rewrites local variable allocation and indexing      #
    #    * add_acc : accelerated via "!$acc parallel loop" directives               #
    #              which relies on using processor level filters in main.F90.       #
    #                                                                               #
    # NOTE: avoid having both adjust_allocation and add_acc both True for now       #
    #       as they don't currently communicate and they both modify the same files #
    #       which may cause subroutine line numbers to change, etc...               #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    if(opt): 
        for s in sub_name_list: 
            if(subroutines[s].name not in main_sub_dict):
                main_sub_dict[subroutines[s].name] = subroutines[s]
            subroutines[s].examineLoops(global_vars=[],varlist=var_list,main_sub_dict=main_sub_dict,verbose=False,
                           add_acc=add_acc,adjust_allocation=adjust_allocation)
        print("Done running in Optimization Mode")
    
    # print_spel_module_dependencies(mod_dict=mod_dict,subs=subroutines)
    ofile = open(f"{case_dir}/module_dependencies.txt",'w')
    for mod in mod_dict.values():
        mod.display_info(ofile=ofile)
    ofile.close()

    with open(f'{case_dir}/source_files_needed.txt','w') as ofile:
        for f in file_list:
            ofile.write(f+'\n')
    
    type_dict = {}
    for modname, mod in mod_dict.items():
        for utype, dtype in mod.defined_types.items():
            type_dict[utype] = dtype
        
    for s in sub_name_list:
        #
        # Parsing means getting info on the variables read and written
        # to by the subroutine and any of its callees
        #
        subroutines[s].parse_subroutine(dtype_dict=type_dict,
                                        main_sub_dict=main_sub_dict,verbose=True)
        
        print(_bc.OKGREEN+f"Variable Analysis for {subroutines[s].name}"+_bc.ENDC)
        
        subroutines[s].child_subroutines_analysis(dtype_dict=type_dict,
                                        main_sub_dict=main_sub_dict,verbose=True)
        
        print(_bc.OKGREEN+f"Derived Type Analysis for {subroutines[s].name}")
        print(f"{func_name}::Read-Only")
        for key in subroutines[s].elmtype_r.keys():
            print(key, subroutines[s].elmtype_r[key])
        print(f"{func_name}::Write-Only")
        for key in subroutines[s].elmtype_w.keys():
            print(key, subroutines[s].elmtype_w[key])
        print(f"{func_name}::Read-Write")
        for key in subroutines[s].elmtype_rw.keys():
            print(key, subroutines[s].elmtype_rw[key])
        print(_bc.ENDC)

        for key in subroutines[s].elmtype_r.keys():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_r[key]
                continue
            if("_inst" in key):
               print(f"error: {key} has _inst")
               sys.exit(1)
            read_types.append(key)
        
        for key in subroutines[s].elmtype_w.keys():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_w[key]
                continue
            if("_inst" in key):
                print(f"error: {key} has _inst")
                sys.exit(1)
            write_types.append(key)
        
        for key in subroutines[s].elmtype_rw.keys():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_w[key]
                continue
            write_types.append(key)

    file_list = insert_header_for_unittest(file_list=file_list,mod_dict=mod_dict) 

    # Create a makefile for the unit test
    wr.generate_makefile(files=file_list,case_dir=case_dir)

    # Make sure physical properties types are read/written:
    list_pp = ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']
    
    print("read_types:",read_types)
    print("write_types:",write_types)

    aggregated_elmtypes_list = []
    for x in read_types:
        dtype_inst = x.split('%')[0]
        if(dtype_inst not in aggregated_elmtypes_list):
            aggregated_elmtypes_list.append(dtype_inst)    
    for x in write_types:
        dtype_inst = x.split('%')[0]
        if(dtype_inst not in aggregated_elmtypes_list):
            aggregated_elmtypes_list.append(dtype_inst)
    
    # for l in list_pp:
    #     aggregated_elmtypes_list.append(l)
    print("list of global vars:",aggregated_elmtypes_list)
    instance_to_user_type = {}
    elm_inst_vars = {}
    for type_name, dtype in type_dict.items():
        if('bounds' in type_name): 
            continue
        if(not dtype.instances):
            print(f"Warning: no instances found for {type_name}")
            cmd = f'grep -rin -E "^[[:space:]]*(type)[[:space:]]*\({type_name}" {ELM_SRC}/main/elm_instMod.F90'
            output = sp.getoutput(cmd)
            print(f"output: {output}")
            if(output):
                output = output.split('\n')
                if(len(output) > 1):
                    print(f"Warning: multiple instances found for {type_name}")
                    print(output)
                    sys.exit(1)
                line = output[0]
                line = line.replace('::','')
                line = line.split(':')
                
                decl = line[1].strip()
                decl = decl.split()
                var = decl[1]
                new_inst = Variable(type_name,var,subgrid='?',ln=0,dim=0,declaration='elm_instMod')
                dtype.instances.append(new_inst)
                elm_inst_vars[var] = dtype
            else:
                print(f"Warning: no instances found for {type_name}")
        for instance in dtype.instances:
            instance_to_user_type[instance.name] = type_name

    dtype_info_list = []
        
    for s in sub_name_list:
        set_active_variables(type_dict,instance_to_user_type,
                             subroutines[s].elmtype_r,dtype_info_list)
        set_active_variables(type_dict,instance_to_user_type,
                             subroutines[s].elmtype_w,dtype_info_list)
        set_active_variables(type_dict,instance_to_user_type,
                             subroutines[s].elmtype_rw,dtype_info_list)
        
    print(dtype_info_list)

    # Will need to read in physical properties type
    # so set all components to True
    for type_name, dtype in type_dict.items():
        instances = [inst.name for inst in dtype.instances]
        for varname in instances:
            if varname in ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']:
                dtype.active = True
                for c in dtype.components:
                    c['active'] = True
    # 
    for el in write_types:
        if(el not in read_types):
            read_types.append(el)
    #
    # Write derived type info to csv file
    # 
    ofile = open(f"{case_dir}/derive_type_info.csv",'w')
    csv_file = csv.writer(ofile)
    row = ['Derived Type', 'Component', 'Type', 'Dimension']
    csv_file.writerow(row)
    for row in dtype_info_list:
        csv_file.writerow(row)
    ofile.close()

    print(f"Call Tree for {case_dir}")
    for sub in subroutines.values():
        tree = sub.calltree[2:]
        sub.analyze_calltree(tree,case_dir)
    
    # This generates verificationMod to test the results of
    # the subroutines.  
    # Call the relevant update_vars_{sub} after the parallel region.
    
    elmvars_dict = {}
    for dtype in type_dict.values():
        for inst in dtype.instances:
            elmvars_dict[inst.name] = inst
    # 
    for sub in subroutines.values():
        # create list of variables that should be used for verification.
        # Will go ahead and use all variables for now but can limit to just w,rw 
        # to save memory if needed.
        verify_vars = {}
        total_vars = [] 
        total_vars.extend(sub.elmtype_r.keys()) 
        total_vars.extend(sub.elmtype_w.keys())
        total_vars.extend(sub.elmtype_rw.keys())
        for var in total_vars:
            if('bounds' in var):
                continue
            dtype, component = var.split('%')
            verify_vars.setdefault(dtype,[]).append(component)

        sub.generate_update_directives(elmvars_dict,verify_vars)

    with open(f'{scripts_dir}/script-output/concat.F90','w') as outfile:
        outfile.write("module verificationMod \n")
        outfile.write("contains \n")

        for s in sub_name_list:
            with open(f"{scripts_dir}/script-output/update_vars_{s}.F90") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
        outfile.write("end module verificationMod\n")
    
    cmd = f"cp {scripts_dir}/script-output/concat.F90 {case_dir}/verificationMod.F90"
    os.system(cmd)
    
    #
    # print and write stencil for acc directives to screen to be c/p'ed in main.F90
    # may be worth editing main.F90 directly.
    #

    aggregated_elmtypes_list.sort(key=lambda v: v.upper())
    acc = _bc.BOLD+_bc.HEADER+"!$acc "
    endc = _bc.ENDC
    print(acc+"enter data copyin( &"+endc)
    with open(f"{case_dir}/global_data_types.txt",'w') as ofile:
        for el in aggregated_elmtypes_list:
            ofile.write(el)
    i = 0
    for el in aggregated_elmtypes_list:
        i+=1
        if(i == len(aggregated_elmtypes_list)):
            print(acc+el+'      &'+endc)
        else :
            print(acc+el+'     , &'+endc)
    print(acc+'  )'+endc)

    # Remove xxx_pp from read_types
    for l in list_pp:
        if l in read_types:
            read_types.remove(l)

    wr.clean_main(aggregated_elmtypes_list,
                         files=needed_mods,case_dir=case_dir)
    
    wr.write_elminstMod(elm_inst_vars,case_dir)
    
    wr.duplicate_clumps(type_dict)
    wr.create_read_vars(type_dict,read_types)
    wr.create_write_vars(type_dict,read_types,casename,use_isotopes=False)
    sys.exit(0)
    files_for_unittest = ' '.join(needed_mods) 
    os.system(f"cp {files_for_unittest} {case_dir}")
    os.system(f"cp {spel_output_dir}duplicateMod.F90 {spel_output_dir}readMod.F90 {spel_output_dir}writeMod.F90 {case_dir}")
    os.system(f"cp {spel_mods_dir}fileio_mod.F90 {case_dir}")
    os.system(f"cp {spel_mods_dir}unittest_defs.h {case_dir}")
    os.system(f"cp {spel_mods_dir}decompInitMod.F90 {case_dir}")

def set_active_variables(type_dict,type_lookup,variable_list,dtype_info_list):
    """
    This function sets the active status of the user defined types
    based on variable list
        * type_dict -- dictionary of all user-defined types found in the code
        * type_lookup -- dictionary that maps an variable to it's user-defined type
        * variable_list -- list of variables that are used (eg. elmtype_r, elmtype_w)
    """
    for var in variable_list:
        dtype, component = var.split('%')
        if('bounds' in dtype): 
            continue
        type_name = type_lookup[dtype]
        type_dict[type_name].active = True 
        for c in type_dict[type_name].components:
            field_var = c['var']
            if(field_var.name == component):
                c['active'] = True
                datatype = field_var.type
                dim = field_var.dim 
                dtype_info_list.append([dtype,field_var.name,datatype,f"{dim}D"])
    
    return None 
    
if __name__ == '__main__':
    main()
