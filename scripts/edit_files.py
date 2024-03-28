import sys
import re
from analyze_subroutines import Subroutine
from utilityFunctions import getLocalVariables, find_file_for_subroutine, get_interface_list, line_unwrapper
from fortran_modules import FortranModule, get_filename_from_module, get_module_name_from_file
from utilityFunctions import  parse_line_for_variables,comment_line, find_variables
from DerivedType import  get_derived_type_definition

# Compile list of lower-case module names to remove
bad_modules =  ['abortutils','shr_log_mod',
               'elm_time_manager','shr_infnan_mod',
               'clm_time_manager','pio',
               'shr_sys_mod','perf_mod','shr_assert_mod',
               'spmdmod', 'restutilmod',
               'histfilemod','accumulmod',
               'ncdio_pio','shr_strdata_mod','fileutils',
               'elm_nlutilsmod',
               'shr_mpi_mod', 'shr_nl_mod','shr_str_mod',
               'controlmod','getglobalvaluesmod',
               'organicfilemod','elmfatesinterfacemod','externalmodelconstants',
               'externalmodelinterfacemod', 'waterstatetype', 'seq_drydep_mod',
               'temperaturetype','waterfluxtype','shr_file_mod','mct_mod','elm_instmod']

fates_mod = ['elmfatesinterfacemod']
betr_mods = ['betrsimulationalm']

bad_subroutines = ['endrun','restartvar','hist_addfld1d','hist_addfld2d',
               'init_accum_field','extract_accum_field','hist_addfld_decomp',
               'ncd_pio_openfile','ncd_io','ncd_pio_closefile']

remove_subs = ['restartvar','hist_addfld1d','hist_addfld2d',
               'init_accum_field','extract_accum_field',
               'prepare_data_for_em_ptm_driver','prepare_data_for_em_vsfm_driver']

"""
Contains python scripts that are useful for editing files to prep for
unit testing
"""


def remove_subroutine(lines, start):
    """
    Special function to comment out a subroutine
    """
    end_sub = False
    ct = start
    endline = 0
    while(not end_sub):
        if(ct > len(lines)): sys.exit("ERROR didn't find end of subroutine")
        match_end = re.search(r'^(\s*end subroutine)',lines[ct])
        if(match_end):
            end_sub = True
            endline = ct
        lines[ct] = '!#py '+lines[ct]
        ct += 1

    return lines, endline

def parse_local_mods(lines,start):
    """
    This function is called to determine if
    a subroutine uses ncdio_pio. and remove it if it does
    """
    past_mods = False
    remove = False
    ct = start
    while (not past_mods and not remove and ct < len(lines)):
        line = lines[ct]
        l = line.split('!')[0]
        if(not l.strip()): ct+=1; continue; #line is just a commment
        lline = line.strip().lower()
        if("ncdio_pio" in lline or "histfilemod" in lline or "spmdmod" in lline):
            remove = True
            break
        match_var = re.search(r'^(type|integer|real|logical|implicit)',l.strip().lower())
        if(match_var):
            past_mods = True;
            break
        ct+=1

    return remove

def process_fates_or_betr(lines,mode):
    """
    This function goes back through the file and comments out lines
    that require FATES/BeTR variables/functions
    """

    ct = 0
    if (mode == 'fates'):
        type = "hlm_fates_interface_type"
        var  = "alm_fates"
    elif(mode == 'betr'):
        type = "betr_simulation_alm_type"
        var  = "ep_betr"
    else:
        sys.exit("Error wrong mode!")

    if(mode == 'fates'):  comment_ = '!#fates_py '
    if(mode == 'betr' ):  comment_ = '!#betr_py '

    while(ct < len(lines)):
        line = lines[ct]
        l = line.split('!')[0]  # don't search comments
        if(not l.strip()):
            ct+=1; continue

        match_type = re.search(f'\({type}\)',l.lower())
        if(match_type):
            lines, ct = comment_line(lines=lines,ct=ct,mode=mode)
            ct+=1; continue

        match_call = re.search(f'[\s]+(call)[\s]+({var})',l.lower())
        if(match_call):
            lines, ct = comment_line(lines=lines,ct=ct,mode=mode)
            ct+=1; continue

        match_var = re.search(f'{var}',l.lower())
        if(match_var):
            #could be a function or argument to fucntions?
            lines, ct = comment_line(lines=lines,ct=ct,mode=mode)
            ct+=1; continue
        ct+=1

    return lines

def get_used_mods(ifile,mods,singlefile,mod_dict,verbose=False):
    """
    Checks to see what mods are needed to compile the file
    """
    func_name = "get_used_mods"
    fn = ifile 
    file = open(fn,'r')
    lines = file.readlines()
    file.close()

    # Keep track of nested level
    linenumber, module_name = get_module_name_from_file(fpath=ifile)
    fort_mod = FortranModule(fname=ifile,name=module_name,ln=linenumber) 
    needed_mods = []
    ct = 0

    # Define regular expressions for catching variables declared in the module
    regex_contains = re.compile(r'^(contains)',re.IGNORECASE)
    user_defined_types = {} # dictionary to store user-defined types in module 

    module_head = True
    while(ct < len(lines)):
        line = lines[ct]
        l, ct = line_unwrapper(lines=lines,ct=ct)
        l = l.strip().lower()
        match_contains = regex_contains.search(l)
        if(match_contains): 
            module_head = False
            # Nothing else to check in this line
            ct+=1
            continue

        if(module_head): 
            # First check if a user-derived type is being defined
            # create new l to simplify regex needed.
            lprime = l.replace('public','').replace('private','').replace(',','')
            match_type_def1 = re.search(r'^(type\s*::)',lprime) # type :: type_name
            match_type_def2 = re.search(r'^(type\s+)(?!\()',lprime) # type type_name
            type_name = None
            if(match_type_def1):
                # Get type name
                type_name = lprime.split('::')[1].strip()
            elif(match_type_def2):
                # Get type name
                matched_expr = match_type_def2.group()
                type_name = lprime.replace(matched_expr,'').strip()
            if(type_name): 
                # Analyze the type definition
                user_dtype,ct = get_derived_type_definition(ifile=ifile,modname=module_name,
                                                            lines=lines,ln=ct,
                                                            type_name=type_name,verbose=verbose)
                user_defined_types[type_name] = user_dtype
            
            # Check for variable declarations
            variable_list = parse_line_for_variables(ifile=ifile,l=l,ln=ct,verbose=verbose)
            # Store variable as Variable Class object and add to Module object
            if(variable_list):
                for v in variable_list:
                    v.declaration = module_name
                fort_mod.global_vars.extend(variable_list)

        match_use = re.search(r'^(use)[\s]+',l)
        if(match_use):
            # Get rid of comma if no space
            l = l.replace(',',' ') 
            mod = l.split()[1]
            mod = mod.strip()
            mod = mod.lower()
            if(mod not in fort_mod.modules and mod not in bad_modules): 
                fort_mod.modules.append(mod)
            # Needed since FORTRAN is not case-sensitive!
            lower_mods = [m.lower().replace('.F90','') for m in mods] 
            if(mod not in needed_mods and mod.lower() not in lower_mods 
               and mod.lower() not in ['elm_instmod','cudafor','verificationmod']):
                needed_mods.append(mod)
        ct+=1
    
    # Done with first pass through the file. 
    # Check against already used Mods
    # NOTE: Could refactor this loop into a function
    #       that takes a module name and returns the filepath.
    files_to_parse = []
    for m in needed_mods:
        if(m.lower() in bad_modules): continue
        needed_modfile = get_filename_from_module(m,verbose=verbose) 
        if(needed_modfile == None):
            if(verbose): print(f"Couldn't find {m} in ELM or shared source -- adding to removal list")
            bad_modules.append(m.lower())
            if(m.lower() in fort_mod.modules): fort_mod.modules.remove(m.lower())
        elif(needed_modfile not in mods):
            files_to_parse.append(needed_modfile)
            mods.append(needed_modfile)
    
    # Store user-defined types in the module object 
    # and find any global variables that have the user-defined type
    # 
    list_type_names = [key for key in user_defined_types.keys()]
    for gvar in fort_mod.global_vars:
        if(gvar.type in list_type_names):
            user_defined_types[gvar.type].instances.append(gvar)

    fort_mod.defined_types  = user_defined_types
    mod_dict[fort_mod.name] = fort_mod
    
    # Recursive call to the mods that need to be processed
    if(files_to_parse and not singlefile): 
        for f in files_to_parse:
            mods,mod_dict = get_used_mods(ifile=f,mods=mods,verbose=verbose,
                                        singlefile=singlefile,mod_dict=mod_dict)
    
    return mods, mod_dict 

def modify_file(lines,fn,sub_list,verbose=True,overwrite=False): 
    """
    Function that modifies the source code of the file 
    Occurs after parsing the file for subroutines and modules
    that need to be removed.
    """

    subs_removed = []
    ct = 0
    #Note: can use grep to get sub_start faster...
    sub_start = 0
    remove_fates = False
    remove_betr = False
    in_subroutine = False

    regex_if = re.compile(r'^(if)[\s]*(?=\()',re.IGNORECASE)
    regex_endif = re.compile(r'^(end\s*if)',re.IGNORECASE)
    regex_ifthen = re.compile(r'^(if)(.+)(then)$',re.IGNORECASE)
    while( ct < len(lines)):
        line = lines[ct]
        l = line.split('!')[0]  # don't search comments
        l = l.strip().lower()
        # l, newct = line_unwrapper(lines=lines,ct=ct)
        if(not l):
            ct+=1; continue;
        if("#include" in l.lower() and 'unittest_defs' not in l):
            newline = l.replace('#include','!#py #include')
            lines[ct] = newline
        
        #match use statements
        bad_mod_string = '|'.join(bad_modules)
        bad_mod_string = f'({bad_mod_string})'
        match_use = re.search(f'\s*(use)[\s]+{bad_mod_string}',l,re.IGNORECASE)
        if(match_use):
            if(verbose): 
                print(f"Matched modules to remove: {l}")
            # Get bad subs; Need to refine this for variables, etc...
            if ( ':' in l ): 
                # account for multiple lines
                l, newct = line_unwrapper(lines=lines, ct=ct)
                subs = l.split(':')[1]
                subs = subs.rstrip('\n')
                subs = re.sub(r'\b(assignment\(=\))\b','',subs)
                # Add elements used from the module to be commented out 
                subs = subs.split(',')
                for el in subs:
                    if ( '=>' in el):
                        match_nan = re.search(r'\b(nan)\b',el)
                        if(match_nan):
                            el = re.sub(r'\b(nan)\s*(=>)\s*','',el)
                        else:
                           el = re.sub(r'\s*(=>)\s*','|',el)
                    el = el.strip().lower()
                    if(el not in bad_subroutines):
                        if(verbose):
                            print(f"Adding {el} to bad_subroutines")
                            print(f"from {fn} \nline: {l}")
                        bad_subroutines.append(el)
            # comment out use statement
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)

        bad_sub_string = '|'.join(bad_subroutines)
        bad_sub_string = f'({bad_sub_string})'

        # Test if subroutine has started
        match_sub = re.search(r'^(\s*subroutine\s+)',l,re.IGNORECASE)
        # Test if a bad subrotuine is being called.
        match_call = re.search(f'\s*(call)[\s]+{bad_sub_string}',l,re.IGNORECASE)
        
        lprime, newct = line_unwrapper(lines=lines, ct=ct)
        lprime = lprime.strip().lower()
        match_bad_inst = re.search(r'\b({})\b'.format(bad_sub_string), lprime)
        
        if(match_sub):
            in_subroutine = True
            endline = 0
            subname = l.split()[1].split('(')[0]
            interface_list = get_interface_list()
            if(subname in interface_list or "_oacc" in subname): 
                ct += 1 
                continue 
            if(verbose): print(f"found subroutine {subname} at {ct+1}")
            sub_start = ct+1

            fn1,startline,endline = find_file_for_subroutine(name=subname,fn=fn)
            # Consistency checks: 
            if(startline != sub_start): 
                sys.exit(f"Subroutine start line-numbers do not match for {subname}: {sub_start},{startline}")
            #
            # Instantiate Subroutine
            #   
            sub = Subroutine(subname,fn1,[''],start=startline,end=endline)
            x = getLocalVariables(sub,verbose=False)
            sub_list.append(sub)

            match_remove = bool(subname.lower() in remove_subs)
            if(match_remove and 'init' not in subname.lower().replace('initcold','cold')):
                if(verbose): print(f'Removing subroutine {subname}')
                lines, endline = remove_subroutine(lines=lines,start=sub_start)
                if(endline == 0): 
                    print('Error: subroutine has no end!'); sys.exit(1)
                ct = endline
                subs_removed.append(subname)
            
            # Remove if it's an IO routine
            elif('readnl' in subname.lower() or re.search(r'(gsmap)',subname.lower())):
                if(verbose): print(f'Removing subroutine {subname}')
                lines, endline = remove_subroutine(lines=lines,start=sub_start)
                if(endline == 0): 
                    print('Error: subroutine has no end!'); sys.exit(1)
                ct = endline
                subs_removed.append(subname)
        
        elif(match_call):
            if(verbose):
                print(f"Matched sub call to remove: {l}")
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
        elif(match_bad_inst):
            if(verbose):
                print(f"Matched bad subroutine instance: {match_bad_inst.group()}\n{l}")
            # Check if any thing used from a module that is to be removed 
            match_if = regex_if.search(l)
            match_decl = find_variables.search(l)
            if(not match_use and not match_decl):
                # Check if the bad element is in an if statement.
                # If so, need to remove the entire if statement.
                if(match_if): 
                    # Get a new line adjusted for continuation lines
                    # So that we can match 'if() then' versus just a 'if()'
                    l_cont, newct = line_unwrapper(lines=lines,ct=ct)
                    l_cont = l_cont.strip().lower() 
                    match_ifthen = regex_ifthen.search(l_cont)
                    if(match_ifthen):
                        if_counter = 1
                        match_end_if = regex_endif.search(l)
                        lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
                        while(if_counter > 0):
                            ct+=1
                            line = lines[ct]
                            l = line.split('!')[0]  # don't search comments
                            l = l.strip().lower()
                            if(l):
                                # Get another complete line to check for nested if statements
                                #
                                l_cont, newct = line_unwrapper(lines=lines,ct=ct)
                                l_cont = l_cont.strip().lower() 

                                match_nested_ifthen = regex_ifthen.search(l_cont)
                                if(match_nested_ifthen): if_counter+=1

                                # See if we are at the end of the if statement
                                match_end_if = regex_endif.search(l)
                                if(match_end_if): if_counter-=1
                                lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)

                    else: # not match_ifthen 
                        lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
                else: # not match_if
                    lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
            elif(match_decl and not in_subroutine):
                lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
        elif(re.search(r'(gsmap)',l.lower() )):
            if(verbose):
                print("Removing gsmap ")
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)
        # match SHR_ASSERT_ALL
        match_assert = re.search(r'^[\s]+(SHR_ASSERT_ALL|SHR_ASSERT)\b',line)
        if(match_assert): 
            lines, ct = comment_line(lines=lines,ct=ct)
        match_end = re.search(r'^(\s*end subroutine)',lines[ct])
        if(match_end): 
            in_subroutine = False
        ct+=1
    
    # Added to try and avoid the compilation 
    # warnings concerning not declared procedures
    if(subs_removed and overwrite):
        lines = remove_reference_to_subroutine(lines=lines,subnames=subs_removed)
    
def process_for_unit_test(fname,casename,mods=None,overwrite=False,verbose=False,singlefile=False):
    """
    This function looks at the whole .F90 file.
    Comments out functions that are cumbersome
    for unit testing purposes.
    Gets module dependencies of the module and
    process them recursively.

    Arguments:
        fname -> File path for .F90 file that with needed subroutine
        sub   -> Subroutine object
        casename -> label of Unit Test
        mods     -> list of already known (if any) files that were previously processed
        verbose  -> Print more info
        singlefile -> flag that disables recursive processing.
    """
    sub_list = []
    initial_mods = mods[:]
    mod_dict = {}

    # First, get complete list of modules  
    # to be processed and removed.
    # add just processed file to list of mods:

    lower_mods =  [m.lower() for m in mods]
    if (fname.lower() not in lower_mods): 
        mods.append(fname)

    # Find if this file has any not-processed mods
    if(not singlefile):
        mods, mod_dict = get_used_mods(ifile=fname,mods=mods,
                                       verbose=verbose,singlefile=singlefile,
                                       mod_dict=mod_dict)

    if(verbose):
        print("Total modules to edit are\n",mods)
        print("Modules to be removed list\n", bad_modules)
    
    for mod_file in mods:
        # Avoid preprocessing files over and over
        if (mod_file in initial_mods): continue 
        file = open(mod_file,'r')
        lines = file.readlines()
        file.close()
        if(verbose): print(f"Processing {mod_file}")
        modify_file(lines,mod_file,sub_list,
                    verbose=verbose,overwrite=overwrite)
        if(overwrite):
            out_fn = mod_file
            if(verbose): print("Writing to file:",out_fn)
            with open(out_fn,'w') as ofile:
                ofile.writelines(lines)

    linenumber,unit_test_module = get_module_name_from_file(fpath=fname)
    file_list = sort_file_dependency(mod_dict,unit_test_module)

    return mod_dict, file_list
    
def remove_reference_to_subroutine(lines, subnames):
    """
    Given list of subroutine names, this function goes back and
    comments out declarations and other references
    """
    sname_string = '|'.join(subnames); sname_string = f'({sname_string})'
    print(f"remove reference to {sname_string}")
    ct = 0
    while (ct<len(lines)):
        line = lines[ct]
        l = line.split('!')[0]  # don't search comments
        if(not l.strip()):
            ct+=1; continue;
        match = re.search(sname_string.lower(),l.lower())
        if(match):
            lines, ct = comment_line(lines=lines,ct=ct)
        ct+=1
    return lines

def sort_file_dependency(mod_dict,unittest_module,file_list=[],verbose=False):
    """
    Function that unravels a dictionary of all module files
    that were parsed in process_for_unit_test. 

    Each element of the dictionary is a FortranModule object.
    """
    # Start with the module that we want to test
    main_fort_mod = mod_dict[unittest_module]

    for mod in main_fort_mod.modules:
        if(mod in bad_modules): continue
        
        # Get module instance from dictionary
        dependency_mod = mod_dict[mod]
        if(dependency_mod.filepath in file_list): continue
        
        # This module has no other dependencies, add to list
        if(not dependency_mod.modules and dependency_mod.filepath not in file_list): 
            file_list.append(dependency_mod.filepath) 
            continue
        
        # Test to see if all of its dependencies are in the file list 
        for dep_mod in dependency_mod.modules:
            if(mod in bad_modules): continue

            # Check if module dependencies are already in the file list
            if(mod_dict[dep_mod].filepath not in file_list):
                if(verbose):
                    print(f"Switching to {dep_mod} to get its dependencies")
                dep_file_list = sort_file_dependency(mod_dict,unittest_module=dep_mod,file_list=file_list)
                
                if(verbose): 
                    print(f"New dependency list: {dep_file_list}")
                    print(f"Current list is:\n{file_list}")
        # Since all of its dependencies are in the file list, add the module to the list
        if(dependency_mod.filepath not in file_list): file_list.append(dependency_mod.filepath)
            
    file_list.append(main_fort_mod.filepath)
    return file_list