## arrow and tab are strings for writing files or printing readable output
arrow = '|--->'
tab   = '    '

def main():
    """
    Edit casename and sub_name_list to create a Functional Unit Test 
    in a directory called {casename} for the subroutines in sub_name_list.
    """
    import sys
    import os
    from DerivedType import derived_type
    from analyze_subroutines import Subroutine,replace_key
    from utilityFunctions import find_file_for_subroutine, getLocalVariables
    import write_routines as wr
    from mod_config import elm_files, home_dir, default_mods, unittests_dir
    from edit_files import process_for_unit_test

    master_sub_dict = {} 

    # casename = "dyn_hwcontent"
    casename = "methane"
    casename = unittests_dir+casename
    # Determines if SPEL should run to make optimizations 
    opt = True
    add_acc = True
    adjust_allocation = False  

    sub_name_list = ["CH4"]
    # sub_name_list = ["ComputeWaterMassNonLake"] #["SurfaceRadiation"]  # ["dyn_cnbal_patch"]
    # sub_name_list = ['DustEmission','DustDryDep']

    # sub_name_list = ["HydrologyNoDrainage"] # ["SnowWater"] , "AerosolMasses","LakeHydrology"]

    # Create script output directory if not present:
    if(not os.path.isdir("./script-output")):
        print("Making script output directory")
        os.system("mkdir script-output")
    
    #Create case directory 
    if(not os.path.isdir(f"{casename}") ):
        print(f"Making case directory {casename}")
        if(not os.path.isdir(f"{unittests_dir}")):
            os.system(f"mkdir {unittests_dir}")
        os.system(f"mkdir {casename}")
        preprocess = True
    else:
        print(f"case {casename} already exists skipping preprocessing")
        preprocess = False 
    
    # EcoDyn_subs_list = ["SoilLittDecompAlloc", "SoilLittDecompAlloc2","Phenology","GrowthResp",
    #                "vegcf_summary_rr","RootDynamics","CarbonStateUpdate0","CNLitterToColumn","CarbonIsoFlux1"
    #                ,"CarbonStateUpdate1","NitrogenStateUpdate1","PhosphorusStateUpdate1","SoilLittVertTransp",
    #                "GapMortality","CarbonIsoFlux2","CarbonStateUpdate2","NitrogenStateUpdate2","PhosphorusStateUpdate2","CarbonIsoFlux2h",
    #                "NitrogenStateUpdate2h","PhosphorusStateUpdate2h","WoodProducts","CropHarvestPools","FireArea", "FireFluxes"
    #                ,"CarbonIsoFlux3","CarbonStateUpdate3","C14Decay","C14BombSpike","colcf_Summary_for_CH4","vegcf_summary_for_ch4"]
    
    # sub_name_list  = ['BareGroundFluxes','CanopyFluxes','UrbanFluxes','LakeFluxes']
    
    # sub_name_list = ['dyn_hwcontent_init','set_prior_weights','set_old_patch_weights',
    #                  'set_old_column_weights','dynSubgrid_wrapup_weight_changes',
    #                  'set_new_patch_weights','set_new_column_weights','set_subgrid_diagnostic_fields',
    #                  'initialize_new_columns','dyn_hwcontent_final','dyn_cnbal_patch','CarbonStateUpdateDynPatch',
    #                  'NitrogenStateUpdateDynPatch','PhosphorusStateUpdateDynPatch','dyn_cnbal_column']

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
    var_list = []
    mod_list = list(dict_mod.keys())
    # Create derived type instance for each variable:
    for mod in mod_list:
        for var in dict_mod[mod]:
            c13c14 = bool('c13' in var or 'c14' in var)
            if(c13c14): continue
            var_list.append(derived_type(var,mod))


    # Initialize list of derived types to 
    read_types  = []; write_types = [];
    subroutines = {k:[] for k in sub_name_list}

    needed_mods = default_mods[:]
    for s in sub_name_list:
        # Get general info of the subroutine
        subroutines[s] = Subroutine(s,calltree=['elm_drv'])

        # Process by removing certain modules and syntax
        # This is aimed for making subroutines compatible
        # with the !$acc routine directive, which may not be useful for
        # highly complex subroutines
        if(preprocess and not opt):
            process_for_unit_test(fname=file,casename=casename,
                     mods=needed_mods,overwrite=True,verbose=False)

    # examineLoops performs adjustments that go beyond the "naive" 
    # reliance on the "!$acc routine" directive. 
    #  * adjust_allocation : rewrites local variable allocation and indexing 
    #  * add_acc : accelerated via "!$acc parallel loop" directives
    #              which relies on using processor level filters in main.F90.

    # NOTE: avoid having both adjust_allocation and add_acc both True for now
    #       as they don't currently communicate and they both modify the same files
    #       which may cause subroutine line numbers to change, etc...
    if(opt): 
        for s in sub_name_list: 
            local_vars = getLocalVariables(subroutines[s],verbose=False)
            subroutines[s].examineLoops(global_vars=[],varlist=var_list,verbose=False,
                           add_acc=add_acc,adjust_allocation=adjust_allocation)
        sys.exit("Done running in Optimization Mode")
    
    for s in sub_name_list:
        # Parsing means getting info on the variables read and written
        # to by the subroutine and any of its callees
        
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
        
        #################################################
        for key in subroutines[s].elmtype_w.copy():
            c13c14 = bool('c13' in key or 'c14' in key)
            if(c13c14):
                del subroutines[s].elmtype_w[key]
                continue
            if("_inst" in key):
                key = key.replace("_inst","_vars")
                print(f"new write_types key: {key}")

            write_types.append(key)
        subroutines[s].exportReadWriteVariables()
         
    analyze_var = True
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
    agg_clm_read = []; agg_clm_write = [];
    for s in sub_name_list:
        for key, fieldlist in subroutines[s].elmtype_r.items():
            for field in fieldlist:
                fname = key+"_"+field
                if(fname not in agg_clm_read):
                    agg_clm_read.append(fname)
        for key, fieldlist in subroutines[s].elmtype_w.items():
            for field in fieldlist:
                fname = key+"_"+field
                if(fname not in agg_clm_write):
                    agg_clm_write.append(fname)

    print("Additional Mods files needed for this unit test:")
    for m in needed_mods:
        if(m not in default_mods): print(m)
    wr.generate_makefile(needed_mods,casename)

    # make sure physical properties types are read/written:
    list_pp = ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']
    for l in list_pp:
        read_types.append(l)
    
    replace_inst = ['soilstate_inst','waterflux_inst','canopystate_inst','atm2lnd_inst','surfalb_inst',
                'solarabs_inst','photosyns_inst','soilhydrology_inst','urbanparams_inst']
    read_types = list(set(read_types))
    write_types = list(set(write_types))
    for v in var_list:
        if(v.name in ['filter','clumps','procinfo']): continue
        c13c14 = bool('c13' in v.name or 'c14' in v.name)
        if(c13c14): continue
        if(v.name in write_types or v.name in read_types):
            if(not v.analyzed): v.analyzeDerivedType()
    
    vdict ={v.name : v for v in var_list}
    ofile = open("SharedPhysicalPropertiesVars.dat",'w')
    for v in list_pp:
        ofile.write(v+"\n")
        for c in vdict[v].components:
            ofile.write("   "+c[1]+"\n")
    ofile.close()

    

    aggregated_elmtypes_list = []
    for s in sub_name_list:
        print(f"========== Derived Types for {s} =================")
        for x in subroutines[s].elmtypes:
            if(x in replace_inst): x = x.replace('_inst','_vars')
            print(x)
            aggregated_elmtypes_list.append(x)
    
    #clean up:
    for l in list_pp:
        aggregated_elmtypes_list.append(l)

    aggregated_elmtypes_list = list(set(aggregated_elmtypes_list))
    
    # update the status of derived_types:
    for s in sub_name_list:
        for dtype, components in subroutines[s].elmtype_r.items():
            if(dtype in replace_inst): dtype = dtype.replace('_inst','_vars')
            if(dtype == 'col_cf_input'): dtype = 'col_cf'
            c13c14 = bool('c13' in dtype or 'c14' in dtype)
            if(c13c14): continue
            for c in vdict[dtype].components:
                if c[1] in components: c[0] = True

    print(f"Call Tree for {casename}")
    for sub in subroutines.values():
        tree = sub.calltree[2:]
        sub.analyze_calltree(tree)

    ## This generates verificationMod to test the results of
    ## the subroutines.  Call the relevant update_vars_{sub}
    ## after the parallel region.
    for sub in subroutines.values():
        sub.generate_update_directives(vdict)

    with open(f'{home_dir}scripts/script-output/concat.F90','w') as outfile:
        outfile.write("module verificationMod \n")
        outfile.write("contains \n")

        for s in sub_name_list:
            with open(f"{home_dir}scripts/script-output/update_vars_{s}.F90") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
        outfile.write("end module verificationMod\n")
    #
    cmd = f"cp {home_dir}scripts/script-output/concat.F90 {casename}/verificationMod.F90"
    print(cmd)
    os.system(f"cp {home_dir}scripts/script-output/concat.F90 {casename}/verificationMod.F90")

    # print and write stencil for acc directives to screen to be c/p'ed in main.F90
    # may be worth editing main.F90 directly.
    aggregated_elmtypes_list.sort(key=lambda v: v.upper())
    from mod_config import _bc
    acc = _bc.BOLD+_bc.HEADER+"!$acc "
    endc = _bc.ENDC
    print(acc+"enter data copyin( &"+endc)
    i = 0
    for el in aggregated_elmtypes_list:
        i+=1
        if(i == len(aggregated_elmtypes_list)):
            print(acc+el+'      &'+endc)
        else :
            print(acc+el+'     , &'+endc)
    print(acc+'  )'+endc)

    const_mods = ['elm_varcon','elm_varpar','shr_const_mod',
              'landunit_varcon','column_varcon','pftvarcon',
              'elm_varctl']
    constants = {k : [] for k in const_mods}

    #for s in subroutines:
    #    s._get_global_constants(constants)

    ## Will need to read in physical properties type
    ## so set all components to True
    print("setting physical properties type to True")
    for varname, dtype in vdict.items():
        if varname in ['veg_pp','lun_pp','col_pp','grc_pp','top_pp']:
            print(varname)
            for c in dtype.components:
                c[0] = True

    wr.clean_main_elminstMod(vdict, aggregated_elmtypes_list,
                         files=needed_mods,casename=casename)

    wr.duplicate_clumps(vdict,aggregated_elmtypes_list)
    subname = casename.replace(unittests_dir,'')

    wr.create_write_vars(vdict,read_types,subname=subname)
    wr.create_read_vars (vdict,read_types)
    ##Move the needed files to the case directory
    import os
    for file in needed_mods:
        cmd = f"cp {elm_files}{file} {casename}"
        os.system(cmd)

    os.system(f"cp duplicateMod.F90 readMod.F90 writeMod.F90 {casename}")
    os.system(f"cp {elm_files}fileio_mod.F90 {casename}")

if __name__ == '__main__':
    main()
