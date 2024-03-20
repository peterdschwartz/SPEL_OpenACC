## arrow and tab are strings for writing files or printing readable output
arrow = '|--->'
tab   = '    '
from mod_config import _bc

def main():
    """
    Edit casename and sub_name_list to create a Functional Unit Test 
    in a directory called {casename} for the subroutines in sub_name_list.
    """
    import sys
    import os
    from analyze_subroutines import Subroutine, replace_key
    from utilityFunctions import getLocalVariables, insert_header_for_unittest, Variable
    import write_routines as wr
    from mod_config import default_mods, unittests_dir, scripts_dir,spel_mods_dir
    from mod_config import ELM_SRC
    from edit_files import process_for_unit_test
    from fortran_modules import print_spel_module_dependencies
    import subprocess as sp
    import csv 
    
    print(f"CWD is {os.getcwd()}")

    main_sub_dict = {}
    case = "LakeTemp"
    casename = unittests_dir+case
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
    if(not os.path.isdir(f"{casename}") ):
        print(f"Making case directory {casename}")
        if(not os.path.isdir(f"{unittests_dir}")):
            os.system(f"mkdir {unittests_dir}")
        os.system(f"mkdir {casename}")
        preprocess = True
    else:
        x = input(f"case {casename} already exists - Preprocess?")
        if(x == 'n'):
            preprocess = False
        elif(x == 'y'):
            preprocess = True
        else:
            sys.exit("Error - input not recognized") 
        
    # sub_name_list = ["PhosphorusMinFluxes","PhosphorusBiochemMin", "NitrogenLeaching", "PhosphorusLeaching",
    #                  "NitrogenStateUpdate3", "PhosphorusStateUpdate3", "PrecisionControl", "veg_cf_summary_for_ch4_acc",
    #                  "veg_cf_summary_acc", "veg_nf_summary_acc", "veg_pf_summary_acc", "summary_veg_flux_p2c",
    #                  "veg_cs_summary_acc", "veg_ns_summary_acc", "veg_ps_summary_acc", "summary_veg_state_p2c",
    #                  "col_cf_summary_for_ch4_acc", "col_cs_summary_acc",
    #                  "col_nf_summary_acc", "col_ns_summary_acc",
    #                  "col_pf_summary_acc", "col_ps_summary_acc" ]

    # sub_name_list = ["NitrogenDeposition","NitrogenFixation","NitrogenFixation_balance", 
    #                  "MaintenanceResp","PhosphorusWeathering","PhosphorusBiochemMin",
    #                  "PhosphorusBiochemMin_balance","PhosphorusDeposition","decomp_rate_constants_bgc",
    #                  "decomp_rate_constants_cn","decomp_vertprofiles","Allocation1_PlantNPDemand"]

    # sub_name_list = ["SoilLittDecompAlloc", "SoilLittDecompAlloc2","Phenology","GrowthResp"]
                    # "veg_cf_summary_rr",
                    # "CarbonStateUpdate0","CNLitterToColumn", "CarbonStateUpdate_Phase1_col", 
                    # "NitrogenStateUpdate_Phase1_col", "PhosphorusStateUpdate_Phase1_col",
                    # "CarbonStateUpdate_Phase1_PFT", "NitrogenStateUpdate_Phase1_pft",
                    # "PhosphorusStateUpdate_Phase1_pft", "SoilLittVertTransp", "GapMortality",
                    # "CarbonStateUpdate2", "NitrogenStateUpdate2","PhosphorusStateUpdate2",
                    # "CarbonStateUpdate2h","NitrogenStateUpdate2h",  "PhosphorusStateUpdate2h",
                    # "WoodProducts", "CropHarvestPools", "FireArea","FireFluxes"]
    
    sub_name_list = ["LakeTemperature"]
    
    # modfile is a running list of which modules hold derived-type definitions
    modfile = 'usemod.txt'
    file = open(modfile, 'r')
    mods = file.readlines()
    file.close()

    mod_list = [l.split()[0] for l in mods]
    dict_mod = {k : [] for k in mod_list}

    for l in mods:
        l.strip('\n')
        line = l.split()
        for el in line[1:]:
            dict_mod[line[0]].append(el)

    # Removing redundancies from mod_list:
    # var_list = []
    # mod_list = list(dict_mod.keys())
    # # Create derived type instance for each variable:
    # for mod in mod_list:
    #     for var in dict_mod[mod]:
    #         c13c14 = bool('c13' in var or 'c14' in var)
    #         if(c13c14): continue
    #         var_list.append(derived_type(var,mod))

    # Initialize list of derived types to 
    read_types  = []; write_types = [];
    subroutines = {k:[] for k in sub_name_list}

    needed_mods = [] # default_mods[:]  
    for s in sub_name_list:
        # Get general info of the subroutine
        subroutines[s] = Subroutine(s,calltree=['elm_drv'])

        # Process by removing certain modules and syntax
        # so that a standalone unit test can be compiled.
        if(preprocess and not opt):
            fn = subroutines[s].filepath
            mod_dict, file_list = process_for_unit_test(fname=fn,casename=casename,
                     mods=needed_mods,overwrite=True,verbose=False)
    
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
            local_vars = getLocalVariables(subroutines[s],verbose=False)
            if(subroutines[s].name not in main_sub_dict):
                main_sub_dict[subroutines[s].name] = subroutines[s]
            subroutines[s].examineLoops(global_vars=[],varlist=var_list,main_sub_dict=main_sub_dict,verbose=False,
                           add_acc=add_acc,adjust_allocation=adjust_allocation)
        sys.exit("Done running in Optimization Mode")
    
    # print_spel_module_dependencies(mod_dict=mod_dict,subs=subroutines)
    ofile = open(f"{casename}/module_dependencies.txt",'w')
    for mod in mod_dict.values():
        mod.display_info(ofile=ofile)
    ofile.close()

    with open(f'{casename}/source_files_needed.txt','w') as ofile:
        for f in file_list:
            ofile.write(f+'\n')
    
    type_dict = {}
    for modname, mod in mod_dict.items():
        for utype, dtype in mod.defined_types.items():
            type_dict[utype] = dtype
    var_list = [dtype for dtype in type_dict.values()]
    for s in sub_name_list:
        #
        # Parsing means getting info on the variables read and written
        # to by the subroutine and any of its callees
        #
        local_vars = getLocalVariables(subroutines[s],verbose=False)

        subroutines[s].parse_subroutine(var_list,verbose=True)
        subroutines[s].child_subroutines_analysis(var_list)

        for key in subroutines[s].elmtype_r.copy():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_r[key]
                continue
            if("_inst" in key):
                key = key.replace("_inst","_vars")
                print(f"new read_types key: {key}")
            read_types.append(key)
        
        for key in subroutines[s].elmtype_w.copy():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_w[key]
                continue
            if("_inst" in key):
                key = key.replace("_inst","_vars")
                print(f"new write_types key: {key}")

            write_types.append(key)
         
    analyze_var = False
    if(analyze_var):
        write_var_dict = {}
        print(f"Opening {casename}-timelineanalysis.dat")
        vfile = open(f"{casename}-timelineanalysis.dat",'w')
        ffile = open(f"{casename}-analysis.dat",'w')

        for s in sub_name_list:
            vfile.write(f"++++++++++{s}++++++++++\n")
            ffile.write(f"{s}\n")

            # Figure out what variables that written to in the subroutine
            #  are used by other routines.
            temp_write_vars = [] #combine key%val
            for key,val in subroutines[s].elmtype_w.items():
                key1 = replace_key(key)
                for comp in val:
                    temp_write_vars.append(key1+'%'+comp)

            #Adjust write_var_dict:
            write_var_dict[s] = temp_write_vars[:]
        
            temp_read_vars = []
            for key, val in subroutines[s].elmtype_r.items():
                key1 = replace_key(key)
                for comp in val:
                    temp_read_vars.append(key1+'%'+comp)
        
            for key in write_var_dict:
                if (key == s): continue
                ffile.write(tab+key+'\n')
                for el in temp_read_vars:
                    if el in write_var_dict[key]:
                        vfile.write(f"{s}::{el} reads from {key} \n")
                        ffile.write(tab+tab+el+'\n')
            
        vfile.close()
        ffile.close()

    ######################################################
    agg_elm_read = []; agg_elm_write = [];
    for s in sub_name_list:
        for key, fieldlist in subroutines[s].elmtype_r.items():
            for field in fieldlist:
                fname = key+"_"+field
                if(key=="lun_ef"): print(fname) 
                if(fname not in agg_elm_read):
                    agg_elm_read.append(fname)
        for key, fieldlist in subroutines[s].elmtype_w.items():
            for field in fieldlist:
                fname = key+"_"+field
                if(fname not in agg_elm_write):
                    agg_elm_write.append(fname)

    file_list = insert_header_for_unittest(file_list=file_list,mod_dict=mod_dict) 

    # Create a makefile for the unit test
    wr.generate_makefile(files=file_list,casename=casename)

    # make sure physical properties types are read/written:
    list_pp = ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']
    for l in list_pp:
        read_types.append(l)

    replace_inst = ['soilstate_inst','waterflux_inst','canopystate_inst','atm2lnd_inst','surfalb_inst',
                'solarabs_inst','photosyns_inst','soilhydrology_inst','urbanparams_inst']
    read_types = list(set(read_types))
    write_types = list(set(write_types))

    # for v in var_list:
    #     if(v.name in ['filter','clumps','procinfo']): continue
    #     c13c14 = bool('c13' in v.name or 'c14' in v.name)
    #     if(c13c14): continue
    #     if(v.name in write_types or v.name in read_types):
    #         if(not v.analyzed): 
    #            v.analyzeDerivedType()
    # type_dict ={v.name : v for v in var_list}
    # ofile = open("SharedPhysicalPropertiesVars.dat",'w')
    # for v in list_pp:
    #     ofile.write(v+"\n")
    #     for c in type_dict[v].components:
    #         ofile.write("   "+c[1]+"\n")
    # ofile.close()

    aggregated_elmtypes_list = []
    for s in sub_name_list:
        for x in subroutines[s].elmtypes:
            if(x in replace_inst): x = x.replace('_inst','_vars')
            aggregated_elmtypes_list.append(x)
    
    #clean up:
    for l in list_pp:
        aggregated_elmtypes_list.append(l)

    aggregated_elmtypes_list = list(set(aggregated_elmtypes_list))

    instance_to_user_type = {}
    elm_inst_vars = {}
    for type_name, dtype in type_dict.items():
        if('bounds' in type_name): continue
        if(not dtype.instances):
            cmd = f'grep -rin -E "^[[:space:]]*(type)[[:space:]]*\({type_name}" {ELM_SRC}/main/elm_instMod.F90'
            output = sp.getoutput(cmd)
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
    # Update the active status of user defined types:
    for s in sub_name_list:
        for dtype, components in subroutines[s].elmtype_r.items():
            if(dtype in replace_inst): dtype = dtype.replace('_inst','_vars')
            if(dtype == 'col_cf_input'): dtype = 'col_cf'
            c13c14 = bool('c13' in dtype or 'c14' in dtype)
            if(c13c14): continue
            type_name = instance_to_user_type[dtype]
            type_dict[type_name].active = True 
            for c in type_dict[type_name].components:
                field_var = c['var']
                if field_var.name in components:
                    c['active'] = True
                    datatype = field_var.type
                    dim = field_var.dim 
                    dtype_info_list.append([dtype,field_var.name,datatype,f"{dim}D"])
    
    for s in sub_name_list:
        for dtype, components in subroutines[s].elmtype_w.items():
            if(dtype in replace_inst): dtype = dtype.replace('_inst','_vars')
            if(dtype == 'col_cf_input'): dtype = 'col_cf'
            c13c14 = bool('c13' in dtype or 'c14' in dtype)
            type_name = instance_to_user_type[dtype]
            type_dict[type_name].active = True 
            for c in type_dict[type_name].components:
                field_var = c['var']
                if field_var.name in components:
                    c['active'] = True
                    datatype = field_var.type
                    dim = field_var.dim 
                    dtype_info_list.append([dtype,field_var.name,datatype,f"{dim}D"])
    
    # Will need to read in physical properties type
    # so set all components to True
    for type_name, dtype in type_dict.items():
        instances = [inst.name for inst in dtype.instances]
        for varname in instances:
            if varname in ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']:
                dtype.active = True
                for c in dtype.components:
                    c['active'] = True
    # for dtype in type_dict.values():
    #     dtype.print_derived_type()
    for el in write_types:
        if(el not in read_types):
            read_types.append(el)
    #
    # Write derived type info to csv file
    # 
    ofile = open(f"{casename}/derive_type_info.csv",'w')
    csv_file = csv.writer(ofile)
    row = ['Derived Type', 'Component', 'Type', 'Dimension']
    csv_file.writerow(row)
    for row in dtype_info_list:
        csv_file.writerow(row)
    ofile.close()

    print(f"Call Tree for {casename}")
    for sub in subroutines.values():
        tree = sub.calltree[2:]
        sub.analyze_calltree(tree,casename)
    #
    # This generates verificationMod to test the results of
    # the subroutines.  
    # Call the relevant update_vars_{sub} after the parallel region.
    #
    elmvars_dict = {}
    for dtype in type_dict.values():
        for inst in dtype.instances:
            elmvars_dict[inst.name] = inst
    
    for sub in subroutines.values():
        sub.generate_update_directives(elmvars_dict)

    with open(f'{scripts_dir}/script-output/concat.F90','w') as outfile:
        outfile.write("module verificationMod \n")
        outfile.write("contains \n")

        for s in sub_name_list:
            with open(f"{scripts_dir}/script-output/update_vars_{s}.F90") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
        outfile.write("end module verificationMod\n")
    
    cmd = f"cp {scripts_dir}/script-output/concat.F90 {casename}/verificationMod.F90"
    os.system(cmd)
    
    #
    # print and write stencil for acc directives to screen to be c/p'ed in main.F90
    # may be worth editing main.F90 directly.
    #

    aggregated_elmtypes_list.sort(key=lambda v: v.upper())
    acc = _bc.BOLD+_bc.HEADER+"!$acc "
    endc = _bc.ENDC
    print(acc+"enter data copyin( &"+endc)
    with open(f"{casename}/global_data_types.txt",'w') as ofile:
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

    wr.clean_main(aggregated_elmtypes_list,
                         files=needed_mods,casename=casename)
    
    wr.write_elminstMod(elm_inst_vars,casename)
    
    wr.duplicate_clumps(type_dict)

    files_for_unittest = ' '.join(needed_mods) 
    os.system(f"cp {files_for_unittest} {casename}")
    os.system(f"cp duplicateMod.F90 readMod.F90 writeMod.F90 {casename}")
    os.system(f"cp {spel_mods_dir}fileio_mod.F90 {casename}")
    os.system(f"cp {spel_mods_dir}unittest_defs.h {casename}")

if __name__ == '__main__':
    main()
