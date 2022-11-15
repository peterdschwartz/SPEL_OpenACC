import sys
import re
import subprocess as sp
from analyze_subroutines import Subroutine
from mod_config import elm_files

#compile list of lower-case module names to remove
bad_modules =  ['abortutils','shr_log_mod','clm_time_manager','shr_infnan_mod',
               'shr_sys_mod','perf_mod','shr_assert_mod','spmdmod', 'restutilmod',
               'histfilemod','accumulmod','ncdio_pio','shr_strdata_mod','fileutils',
               'elm_nlutilsmod',
               'shr_mpi_mod', 'shr_nl_mod','shr_str_mod','controlmod','getglobalvaluesmod',
               'organicfilemod','elmfatesinterfacemod','externalmodelconstants',
               'externalmodelinterfacemod']

fates_mod = ['elmfatesinterfacemod','elmfatesinterfacemod']
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

        # #mutst be argument?
        # if(match_var and not match_call and not match_type):
        #     l = l.replace(var,'')+ comment_ +lines[ct].strip()
        #     lines[ct] = l

        ct+=1

    return lines

def get_used_mods(ifile,mods,verbose):
    """
    checks to see what mods are needed to compile the file
    and then analyze them
    """
    file = open(elm_files+ifile,'r')
    lines = file.readlines()
    file.close()

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
            l = l.replace(',',' ') #get rid of comma if no space
            mod = l.split()[1]
            mod = mod.strip()
            #needed since FORTRAN is not case-sensitive!
            lower_mods = [m.lower().replace('.F90','') for m in mods] 
            if(mod not in needed_mods and mod.lower() not in lower_mods 
               and mod.lower() not in ['elm_instmod','cudafor','verificationmod']):
                needed_mods.append(mod)
        ct+=1
    #check against already used Mods
    files_to_parse = []
    for m in needed_mods:
        if(m.lower() in bad_modules): continue 
        cmd = f'grep -i "module {m}" {elm_files}*.F90'
        output = sp.getoutput(cmd)
        if(not output):
            #if(verbose): print(f"{m} is already in bad_modules")
            print(f"Could not find module {m}")
            required = input("Is this module required?")
            if(required.lower() in ['y','yes']):
                sys.exit(f"ERROR Add module {m} to {elm_files} ")
            elif(required.lower() in ['n','no']):
                print(f"Adding module {m} to mods to be removed")
                bad_modules.append(m.lower())
        else:
            needed_modfile = output.split('\n')[0].replace(elm_files,'').split(':')[0]
            if(needed_modfile not in mods):
                files_to_parse.append(needed_modfile)
                mods.append(needed_modfile)
    
    #Recursive call to the mods that need to be processed
    if(files_to_parse): 
        for f in files_to_parse:
            mods = get_used_mods(ifile=f,mods=mods,verbose=verbose)
    
    return mods

def modify_file(lines,casename,fn,verbose=False,overwrite=False): 
    """
    Function that modifies the source code of the file
    """
    from utilityFunctions import getLocalVariables, find_file_for_subroutine, get_interface_list

    subs_removed = []
    ct = 0
    #Note: can use grep to get sub_start faster...
    sub_start = 0
    remove_fates = False
    remove_betr = False
    in_subroutine = False

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
            #get bad subs; Need to refine this for variables, etc...
            if(':' in l and 'nan' not in l): 
                subs = l.split(':')[1]
                subs.replace('=>',' ')
                subs = subs.split(',')
                for el in subs:
                    temp = el.strip().split()
                    if(len(temp)>1): el = temp[0]
                    if el.strip() not in bad_subroutines:
                        bad_subroutines.append(el.strip())

            #comment out use statement
            lines, ct = comment_line(lines=lines,ct=ct,verbose=True)

        #Test if subroutine has started
        match_sub = re.search(r'^(\s*subroutine\s+)',l.lower())
        if(match_sub):
            endline = 0
            
            subname = l.split()[1].split('(')[0]
            interface_list = get_interface_list()
            if(subname in interface_list): 
                ct += 1 
                continue 
            if(verbose): print(f"found subroutine {subname} at {ct+1}")
            sub_start = ct+1
            #if(subname not in ["Init","InitAllocate","InitHistory"]):
             
            fn1,startline,endline = find_file_for_subroutine(name=subname,fn=fn)
            # Consistency checks: 
            if(startline != sub_start): 
                sys.exit(f"Subroutine start line-numbers do not match for {subname}: {sub_start},{startline}")
            #
            # Instantiate Subroutine
            #   
            # sub.startline = startline; sub.endline = endline;
            sub = Subroutine(subname,fn1,[''],start=startline,end=endline)
            x = getLocalVariables(sub,verbose=False)
            # sub.printSubroutineInfo()

            # rm_sub_string = '|'.join(remove_subs); rm_sub_string = f'({rm_sub_string})'
            # match_remove = re.search(f'[\s]+(call)[\s]+{rm_sub_string}',l.lower())
            match_remove = bool(subname.lower() in remove_subs)
            if(match_remove and 'init' not in subname.lower().replace('initcold','cold')):
                print(f'Removing subroutine {subname}')
                lines, endline = remove_subroutine(lines=lines,start=sub_start)
                if(endline == 0): sys.exit('Error: subroutine has no end!')
                ct = endline
                subs_removed.append(subname)
        
        bad_sub_string = '|'.join(bad_subroutines)
        bad_sub_string = f'({bad_sub_string})'
        match_call = re.search(f'[\s]+(call)[\s]+{bad_sub_string}',l)
        if(match_call):
            lines, ct = comment_line(lines=lines,ct=ct)

        match_func = re.search(f'{bad_sub_string}',l)
        if(match_func and '=' in l):
            _str = l.split()[0]
            lines, ct = comment_line(lines=lines,ct=ct)

        #match write
        match_write = re.search(f'[\s]+(write[\s]*\()',l)
        if(match_write):
            lines, ct = comment_line(lines=lines,ct=ct)

        #match SHR_ASSERT_ALL
        match_assert = re.search(r'[\s]+(SHR_ASSERT_ALL)',line)
        if(match_assert): newline = line.replace(line,''); lines[ct]=newline;
        match_end = re.search(r'^(\s*end subroutine)',lines[ct])
        if(match_end): in_subroutine = False
        ct+=1
    
    # added to try and avoid the compilation 
    # warnings concerning not declared procedures
    if(subs_removed):
        lines = remove_reference_to_subroutine(lines=lines,subnames=subs_removed)

def process_for_unit_test(fname,casename,mods=None,overwrite=False,verbose=False):
    """
    This function looks at the whole .F90 file.
    Comments out functions that are cumbersome
    for unit testing purposes.
    Gets module dependencies of the module and
    process them recursively 
    """
    
    initial_mods = mods[:]
    # First, get complete list of modules to be processed 
    # and removed.
    #add just processed file to list of mods:
    lower_mods =  [m.lower() for m in mods]
    if (fname.lower() not in lower_mods): mods.append(fname)
    #find if this file has any not-processed mods
    mods = get_used_mods(ifile=fname,mods=mods,verbose=verbose)

    if(verbose):
        print("Total modules to edit are\n",mods)
        print("========================================")
        print("Modules to be removed list\n", bad_modules)
    
    for mod_file in mods:
        if (mod_file in initial_mods): continue
        file = open(elm_files+mod_file,'r')
        lines = file.readlines()
        file.close()
        if(verbose): print(f"Processing {mod_file}")
        modify_file(lines,casename,mod_file,verbose=verbose,overwrite=overwrite)
        if(overwrite):
            out_fn = elm_files+mod_file
            if(verbose): print("Writing to file:",out_fn)
            with open(out_fn,'w') as ofile:
                ofile.writelines(lines)


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

    # if(mode == "full"):
    #     #add just processed file to list of mods:
    #     lower_mods =  [m.lower() for m in mods]
    #     if (fname.lower() not in lower_mods): mods.append(fname)
    #     #find if this file has any not-processed mods
    #     mods = get_used_mods(ifile=fname,mods=mods,verbose=verbose)
    #     return mods
