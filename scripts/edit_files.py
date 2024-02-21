import sys
import re
import subprocess as sp
from analyze_subroutines import Subroutine
from mod_config import ELM_SRC, SHR_SRC, _bc
from utilityFunctions import getLocalVariables, find_file_for_subroutine, get_interface_list, line_unwrapper
from fortran_modules import FortranModule

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
               'externalmodelinterfacemod', 'waterstatetype',
               'temperaturetype','waterfluxtype','shr_file_mod','mct_mod']

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
def comment_line(lines,ct,mode='normal',verbose=False):
    """
    function comments out lines accounting for line continuation
    """
    if(mode == 'normal'): comment_ = '!#py '
    if(mode == 'fates' ): comment_ = '!#fates_py '
    if(mode == 'betr'  ): comment_ = '!#betr_py '
    
    newline = lines[ct]
    str_ = newline.split()[0]
    newline = newline.replace(str_,comment_+str_,1)
    lines[ct] = newline
    continuation = bool(newline.strip('\n').endswith('&'))
    if(verbose): print(lines[ct])
    while(continuation):
        ct +=1
        newline = lines[ct]
        str_ = newline.split()[0]
        newline = newline.replace(str_, comment_+str_,1)
        lines[ct] = newline
        if(verbose): print(lines[ct])
        continuation = bool(newline.strip('\n').endswith('&'))
    return lines, ct

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

def get_used_mods(ifile,mods,singlefile,modtree,verbose=False):
    """
    Checks to see what mods are needed to compile the file
    """
    fn = ifile 
    file = open(fn,'r')
    lines = file.readlines()
    file.close()
    # Keep track of nested level
    depth= 0

    needed_mods = []
    ct = 0
    
    while(ct < len(lines)):
        line = lines[ct]
        l = line.split('!')[0].strip()
        if(not l):
            ct+=1
            continue
        match_use = re.search(r'^(use)[\s]+',l)
        if(match_use):
            # Get rid of comma if no space
            l = l.replace(',',' ') 
            mod = l.split()[1]
            mod = mod.strip()
            
            # Needed since FORTRAN is not case-sensitive!
            lower_mods = [m.lower().replace('.F90','') for m in mods] 
            if(mod not in needed_mods and mod.lower() not in lower_mods 
               and mod.lower() not in ['elm_instmod','cudafor','verificationmod']):
                needed_mods.append(mod)
        ct+=1
    
    # Check against already used Mods
    # NOTE: Could refactor this loop into a function
    #       that takes a module name and returns the filepath.
    files_to_parse = []
    for m in needed_mods:
        if(m.lower() in bad_modules): continue 
        cmd = f'grep -rin --exclude-dir=external_models/ "module {m}" {ELM_SRC}*'
        output = sp.getoutput(cmd)
        if(not output):
            if(verbose): print(f"Checking shared modules...")
            #
            # If file is not an ELM file, may be a shared module in E3SM/share/util/
            #
            cmd = f'grep -rin --exclude-dir=external_models/ "module {m}" {SHR_SRC}*'
            shr_output = sp.getoutput(cmd) 
            
            if(not shr_output):
                if(verbose): print(f"Couldn't find {m} in ELM or shared source -- adding to removal list")
                bad_modules.append(m.lower())
            else:
                needed_modfile = shr_output.split('\n')[0].split(':')[0]
                modtree.append({'depth': -9999,'file': needed_modfile})
                if(needed_modfile not in mods):
                    files_to_parse.append(needed_modfile)
                    mods.append(needed_modfile)
        else:
            needed_modfile = output.split('\n')[0].split(':')[0]
            modtree.append({'depth': depth,'file': needed_modfile})
            if(needed_modfile not in mods):
                files_to_parse.append(needed_modfile)
                mods.append(needed_modfile)
    
    # Recursive call to the mods that need to be processed
    if(files_to_parse): 
        for f in files_to_parse:
            mods,modtree = get_used_mods(ifile=f,mods=mods,verbose=verbose,
                                         singlefile=singlefile,modtree=modtree)
    
    return mods, modtree 

def modify_file(lines,casename,fn,sub_list,verbose=False,overwrite=False): 
    """
    Function that modifies the source code of the file
    """

    subs_removed = []
    ct = 0
    #Note: can use grep to get sub_start faster...
    sub_start = 0
    remove_fates = False
    remove_betr = False
    in_subroutine = False
    if('module pftvarcon' == lines[0].strip()):
        verbose = True 
    while( ct < len(lines)):
        line = lines[ct]
        l = line.split('!')[0]  # don't search comments
        if(not l.strip()):
            ct+=1; continue;
        if("#include" in l.lower()):
            newline = l.replace('#include','!#py #include')
            lines[ct] = newline
        
        #match use statements
        bad_mod_string = '|'.join(bad_modules)
        bad_mod_string = f'({bad_mod_string})'
        
        match_use = re.search(f'[\s]+(use)[\s]+{bad_mod_string}',l.lower())
        if(match_use):
            if(verbose): print(f"Matched modules to remove: {l}")
            #get bad subs; Need to refine this for variables, etc...
            if(':' in l and 'nan' not in l): 
                subs = l.split(':')[1]
                subs = subs.rstrip('\n')
                # account for multiple lines
                subs, newct = line_unwrapper(lines=lines,ct=ct)

                subs.replace('=>',' ')
                subs = subs.split(',')
                for el in subs:
                    temp = el.strip().split()
                    if(len(temp)>1): el = temp[0]
                    if el.strip() not in bad_subroutines:
                        bad_subroutines.append(el.strip())

            #comment out use statement
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)

        #Test if subroutine has started
        match_sub = re.search(r'^(\s*subroutine\s+)',l.lower())
        if(match_sub):
            endline = 0
            if(verbose): print(f"Matched subroutines to remove: {l}")
            
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
            elif('readnl' in subname.lower()):
                if(verbose): print(f'Removing subroutine {subname}')
                lines, endline = remove_subroutine(lines=lines,start=sub_start)
                if(endline == 0): 
                    print('Error: subroutine has no end!'); sys.exit(1)
                ct = endline
                subs_removed.append(subname)
        
        bad_sub_string = '|'.join(bad_subroutines)
        bad_sub_string = f'({bad_sub_string})'
        match_call = re.search(f'[\s]+(call)[\s]+{bad_sub_string}',l)
        if(match_call):
            if(verbose): print(f"Matched sub call to remove: {l}")
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)

        match_func = re.search(f'{bad_sub_string}',l)
        if(match_func and '=' in l):
            if(verbose): 
                print(f"Matched functions to remove: {l}\n match: {match_func.group()}")
            _str = l.split()[0]
            lines, ct = comment_line(lines=lines,ct=ct,verbose=verbose)

        # match SHR_ASSERT_ALL
        match_assert = re.search(r'[\s]+(SHR_ASSERT_ALL|SHR_ASSERT)\b',line)
        if(match_assert): 
            lines, ct = comment_line(lines=lines,ct=ct)
            # newline = line.replace(line,''); lines[ct]=newline;
        match_end = re.search(r'^(\s*end subroutine)',lines[ct])
        if(match_end): in_subroutine = False
        ct+=1
    
    # added to try and avoid the compilation 
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
    modtree = [] 
    depth = 0
    # First, get complete list of modules to be processed 
    # and removed.
    # add just processed file to list of mods:
    lower_mods =  [m.lower() for m in mods]
    if (fname.lower() not in lower_mods): 
        mods.append(fname)

    # Find if this file has any not-processed mods
    if(not singlefile):
        mods, modtree = get_used_mods(ifile=fname,mods=mods,verbose=verbose,singlefile=singlefile,modtree=modtree)

    if(verbose):
        print("Total modules to edit are\n",mods)
        print("Modules to be removed list\n", bad_modules)
    
    for mod_file in mods:
        if (mod_file in initial_mods): continue # Avoid preprocessing files over and over
        file = open(mod_file,'r')
        lines = file.readlines()
        file.close()
        if(verbose): print(f"Processing {mod_file}")
        modify_file(lines,casename,mod_file,sub_list,verbose=verbose,overwrite=overwrite)
        if(overwrite):
            out_fn = mod_file
            if(verbose): print("Writing to file:",out_fn)
            with open(out_fn,'w') as ofile:
                ofile.writelines(lines)

    return modtree
    
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
