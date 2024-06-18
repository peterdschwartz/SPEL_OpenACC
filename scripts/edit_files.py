import sys
import re
import subprocess as sp 
from mod_config import E3SM_SRCROOT, spel_output_dir
from analyze_subroutines import Subroutine
from utilityFunctions import find_file_for_subroutine, get_interface_list, line_unwrapper
from fortran_modules import FortranModule, get_filename_from_module, get_module_name_from_file
from utilityFunctions import  parse_line_for_variables,comment_line, find_variables
from DerivedType import  get_derived_type_definition
from collections import namedtuple 

# Compile list of lower-case module names to remove
# SPEL expects these all to be lower-case currently 
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
               'temperaturetype','waterfluxtype','shr_file_mod','mct_mod','elm_instmod',
               'spmdgathscatmod']

fates_mod = ['elmfatesinterfacemod']
betr_mods = ['betrsimulationalm']

bad_subroutines = ['endrun','restartvar','hist_addfld1d','hist_addfld2d',
               'init_accum_field','extract_accum_field','hist_addfld_decomp',
               'ncd_pio_openfile','ncd_io','ncd_pio_closefile']

remove_subs = ['restartvar','hist_addfld1d','hist_addfld2d',
               'init_accum_field','extract_accum_field',
               'prepare_data_for_em_ptm_driver','prepare_data_for_em_vsfm_driver', 
               'decompinit_lnd_using_gp']
#
# Macros that we want to process. Any not in the list will be
# skipped. 
macros = ['MODAL_AER']
#    gfortran -D<FLAGS> -I{E3SM_SRCROOT}/share/include -cpp -E <file> > <output>
# will generate the preprocessed file with Macros processed.
# But what to do about line numbers? 
# The preprocessed file will have a '# <line_number>' indicating 
# the line number immediately after the #endif in the original file.

# Name tuple used to conveniently store line numbers
# for preprocessed and original files
PreProcTuple = namedtuple('PreProcTuple',['cpp_ln','ln'])   

def remove_subroutine(og_lines,cpp_lines, start):
    """Function to comment out an entire subroutine
    """
    func_name = "remove_subroutine"
    end_sub = False
    
    og_ln = start.ln
    endline = 0
    while(not end_sub):
        if(og_ln > len(og_lines)):
            print(f"{func_name}::ERROR didn't find end of subroutine")
            sys.exit(1)
        match_end = re.search(r'^(\s*end subroutine)',og_lines[og_ln].lower())
        if(match_end):
            end_sub = True
            endline = og_ln
        og_lines[og_ln] = '!#py '+og_lines[og_ln]
        og_ln += 1
    
    if(start.cpp_ln):
        # Manually find the end of the subroutine in the preprocessed file
        # Since the subroutine is not of interest, just find the end
        end_sub = False
        cpp_endline = 0
        cpp_ln = start.cpp_ln
        while(not end_sub):
            match_end = re.search(r'^(\s*end subroutine)',cpp_lines[cpp_ln].lower())
            if(match_end):
                end_sub = True
                cpp_endline = cpp_ln
            cpp_ln += 1 
    else:
        cpp_endline = None
    
    out_ln_pair = PreProcTuple(cpp_ln=cpp_endline,ln=endline)

    return og_lines, out_ln_pair


def parse_local_mods(lines,start):
    """This function is called to determine if
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

def check_cpp_line(base_fn ,og_lines, cpp_lines,
                   cpp_ln,og_ln,verbose=False):
    """ Function to check if the compiler preprocessor (cpp) line
    is a cpp comment and adjust the line numbers accordingly.
    returns the adjusted line numbers
    """
    func_name = "check_cpp_line"
    # regex to match if the proprocessor comments refer to mod_file
    regex_file = re.compile(r'({})'.format(base_fn))
    # regex matches a preprocessor comment
    regex_cpp_comment = re.compile(r'(^# [0-9]+)')
    # Store current lines to check 
    cpp_line = cpp_lines[cpp_ln]
    line = og_lines[og_ln]
    

    # Comment out include statements 
    # (NOTE: this is unnecessary and overly specific to elm use case?)
    regex_assert = re.compile(r'(shr_assert.h)',re.IGNORECASE)
    if(regex_assert.search(line)):
        if(verbose):
            print(f"{func_name}:: Found include statement to comment out:\n{line}")
            print(f"cpp line: {cpp_line}")
        newline = line.replace('#include','!#py #include')
        og_lines[og_ln] = newline
        # include statements take up multiple lines:
        match_file = regex_file.search(cpp_line)
        while(not match_file):
            cpp_ln+=1
            cpp_line = cpp_lines[cpp_ln]
            match_file = regex_file.search(cpp_line)
        print(f"{func_name}::Skipping to line {cpp_ln}\n {cpp_lines[cpp_ln]}")
    
    # Check if the line is a preprocessor comment
    m_cpp = regex_cpp_comment.search(cpp_line)
    if(m_cpp):
        # Check if the comment refers to the mod_file
        match_file = regex_file.search(cpp_line)
        if(match_file):
            # Get the line for the original file, adjusted for 0-based indexing
            # NOTE: if not match_file, then the comment is for an include statement
            #       which will be handled in the main part of the code?
            og_ln = int(m_cpp.group().split()[1]) - 1

        # Since it was a comment, go to the next line
        cpp_ln+=1
        if(verbose):
            print(f"{func_name}:: Found CPP comment, new line number: {og_ln}")
    # If not a cpp comment, these arguments are unchanged.        
    return cpp_ln, og_ln, og_lines

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
            if(True):#verbose): 
                print(f"Couldn't find {m} in ELM or shared source -- adding to removal list")
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
            if(gvar not in user_defined_types[gvar.type].instances):
                user_defined_types[gvar.type].instances.append(gvar)

    fort_mod.defined_types  = user_defined_types
    mod_dict[fort_mod.name] = fort_mod

    # Recursive call to the mods that need to be processed
    if(files_to_parse and not singlefile):
        for f in files_to_parse:
            mods,mod_dict = get_used_mods(ifile=f,mods=mods,verbose=verbose,
                                        singlefile=singlefile,mod_dict=mod_dict)

    return mods, mod_dict


def modify_file(lines,fn,sub_dict,verbose=False,overwrite=False):
    """
    Function that modifies the source code of the file
    Occurs after parsing the file for subroutines and modules
    that need to be removed.
    """
    func_name = "modify_file"
  
    # Test if the file in question contains any ifdef statements:
    cmd = f'grep -E "ifn?def"  {fn} | grep -v "_OPENACC"'
    output = sp.getoutput(cmd)
    base_fn = fn.split('/')[-1]

    if(output):
        # Need to loop a preprocessed version of the file
        cpp_file = True # Logical to determine what file we are looping through
        new_fn = f'{spel_output_dir}cpp_{base_fn}'
        # Set up cmd for preprocessing
        # Get macros used:
        macros_string = '-D'+ ' -D'.join(macros)
        # cmd to pass to subprocess
        cmd = f'gfortran -I{E3SM_SRCROOT}/share/include {macros_string} -cpp -E {fn} > {new_fn}'
        ier = sp.getoutput(cmd) # run the command
        # read lines of preprocessed file 
        file = open(new_fn,'r')
        cpp_lines = file.readlines()
        file.close()
    else:
        cpp_file = False 
        cpp_lines = [] 
    
    # Control flags that will be used to remove certain subroutines
    # remove_fates = False
    # remove_betr = False

    # Flag to keep track if we are currently in a subroutine
    in_subroutine = False
    
    regex_if = re.compile(r'^(if)[\s]*(?=\()',re.IGNORECASE)
    regex_endif = re.compile(r'^(end\s*if)',re.IGNORECASE)
    regex_ifthen = re.compile(r'^(if)(.+)(then)$',re.IGNORECASE)

    subs_removed = []

    # Function to convert adjust cpp ln number after commenting out lines 
    # in the original file (ie, for line continuations)
    AdjustLine = lambda a, b, c : a + (b - c)
    # Note: can use grep to get sub_start faster, but
    #       some modules have multiple of the same subroutine
    #       based on ifdef statements.
    sub_start = 0
    if(cpp_file):
        eof = len(cpp_lines)
    else:
        eof = len(lines)

    ct = 0 
    linenum = 0
    while( ct < eof):
        # Adjust if we are looping through compiler preprocessed file
        if(cpp_file):
            line = cpp_lines[ct]
            # Function to check if the line is a cpp comment 
            # and adjust the line numbers accordingly
            newct, linenum, lines = check_cpp_line(base_fn=base_fn,
                                                og_lines=lines, cpp_lines=cpp_lines,
                                                cpp_ln=ct,og_ln=linenum,verbose=verbose)
            # If cpp_line was a comment, increment and analyze next line
            if(newct > ct):
                ct = newct
                continue 
        else: # not cpp file
            linenum = ct 
            line = lines[ct]

        l = line.split('!')[0]  # don't search comments
        l = l.strip().lower()
        if(not l):
            linenum+=1
            ct+=1
            continue
        
        # Perform consistency check, This is only done after checking 
        # if the cpp_line is non-empty.  As, some empty cpp_lines are 
        # generated by the preprocessor and the og lines are not empty
        if(cpp_file):
            # if(verbose): 
            #     print(f"cpp Ln: {ct} Original Ln: {linenum}")
            if(line != lines[linenum]):
                print(f"{func_name}::Warning! Line mismatch in {base_fn}: cpp @{ct} and original file @{linenum}")
                print(f"{line}\n{lines[linenum]}")

        # Match use statements
        bad_mod_string = '|'.join(bad_modules)
        bad_mod_string = f'({bad_mod_string})'
        match_use = re.search(f'\s*(use)[\s]+{bad_mod_string}',l,re.IGNORECASE)
        
        if(match_use):
            if(match_use.group() == "elm_varcon"):
                print(f"ERROR: {match_use.group()}")
                print(bad_mod_string)
                sys.exit(1)
            if(verbose):
                print(f"{func_name}::Matched modules to remove: {l}")
            # Get bad subs; Need to refine this for variables, etc...
            if ( ':' in l ):
                # Account for multiple lines
                l, newct = line_unwrapper(lines=lines, ct=linenum)
                if(cpp_file and verbose):
                    l_dbg, ct_dbg = line_unwrapper(lines=cpp_lines, ct=ct)

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
                    if("spval" in el ):
                        print(f"ERROR: trying to remove {el}")
                        print(f"cpp_lin: {ct} og_lin: {linenum}")
                        print(f"line: {l}")
                        print(f"from file: {base_fn}")
                        sys.exit(1)
                    if(el not in bad_subroutines):
                        if(verbose):
                            print(f"Adding {el} to bad_subroutines")
                            print(f"from {fn} \nline: {l}")
                        bad_subroutines.append(el)
            # comment out use statement
            lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
            ct = AdjustLine(ct,newct,linenum)
            linenum = newct

        bad_sub_string = '|'.join(bad_subroutines)
        bad_sub_string = f'({bad_sub_string})'

        # Test if subroutine has started
        match_sub = re.search(r'^(\s*subroutine\s+)',l,re.IGNORECASE)
        # Test if a bad subrotuine is being called.
        match_call = re.search(f'\s*(call)[\s]+{bad_sub_string}',l,re.IGNORECASE)

        lprime, newct = line_unwrapper(lines=lines, ct=linenum)
        lprime = lprime.strip().lower()
        match_bad_inst = re.search(r'\b({})\b'.format(bad_sub_string), lprime)

        if(match_sub):
            in_subroutine = True
            # TODO: Add better regex to get subroutine name
            subname = l.split()[1].split('(')[0]
            interface_list = get_interface_list()
            if(subname in interface_list or "_oacc" in subname):
                ct += 1
                linenum+=1 
                continue
            if(verbose): 
                print(f"{func_name}::found subroutine {subname} at {ct+1}")
            
            if(cpp_file):
                sub_start = linenum
            else:
                sub_start = ct

            # Check if subroutine needs to be removed before processing
            match_remove = bool(subname.lower() in remove_subs)
            test_init = bool('init' not in subname.lower().replace('initcold','cold'))

            # Remove if it's an IO routine
            test_nlgsmap = bool('readnl' in subname.lower() or re.search(r'(gsmap)',subname.lower()) )
            test_decompinit = bool(subname.lower() == 'decompinit_lnd_using_gp' )
            if( (match_remove and test_init) or test_nlgsmap or test_decompinit):
                if(verbose): 
                    print(f'Removing subroutine {subname}')
                if(cpp_file):
                    ln_pair = PreProcTuple(cpp_ln=ct,ln=linenum)
                else:
                    ln_pair = PreProcTuple(cpp_ln=None,ln=linenum)
                
                lines, endline_pair = remove_subroutine(og_lines=lines,cpp_lines=cpp_lines,
                                                   start=ln_pair)
                if(endline_pair.ln == 0):
                    print('Error: subroutine has no end!')
                    sys.exit(1)
                if(cpp_file):
                    ct = endline_pair.cpp_ln
                    linenum = endline_pair.ln
                else:
                    ct = endline_pair.ln
                    linenum = ct 
                subs_removed.append(subname)               
        # Subroutine is calling a subroutine that needs to be removed
        elif(match_call):
            lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
            ct = AdjustLine(ct,newct,linenum)
            linenum = newct
            if(verbose):
                print(f"{func_name}::Matched sub call to remove: {l}")
                print(f"New line numbers: cpp {ct} python {linenum}")
                print(f"cpp line: {cpp_lines[ct]} \n og line: {lines[linenum]}")    

        # Found an instance of something used by a "bad" module
        elif(match_bad_inst):
            if(verbose):
                print(f"{func_name}::Removing usage of {match_bad_inst.group()}\n{l}")
            # Check if any thing used from a module that is to be removed
            match_if = regex_if.search(l)
            match_decl = find_variables.search(l)
            if(not match_use and not match_decl):
                # Check if the bad element is in an if statement.
                # If so, need to remove the entire if statement.
                if(match_if):
                    # Get a new line adjusted for continuation lines
                    # So that we can match 'if() then' versus just a 'if()'
                    l_cont, newct = line_unwrapper(lines=lines,ct=linenum)
                    l_cont = l_cont.strip().lower()
                    match_ifthen = regex_ifthen.search(l_cont)
                    if(match_ifthen):
                        if_counter = 1
                        match_end_if = regex_endif.search(l)
                        lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
                        ct = AdjustLine(ct,newct,linenum)
                        linenum = newct
                        while(if_counter > 0):
                            ct+=1
                            linenum+=1
                            # Adjust if we are looping through compiler preprocessed file
                            if(cpp_file):
                                line = cpp_lines[ct]
                                # Function to check if the line is a cpp comment 
                                # and adjust the line numbers accordingly
                                newct, linenum, lines = check_cpp_line(base_fn=base_fn,
                                                                    og_lines=lines, cpp_lines=cpp_lines,
                                                                    cpp_ln=ct,og_ln=linenum,verbose=verbose)
                                # If cpp_line was a comment, increment and analyze next line
                                if(newct > ct):
                                    ct = newct
                                    continue 
                            else:
                                # not cpp file
                                linenum = ct 
                                line = lines[ct]

                            l = line.split('!')[0]  # don't search comments
                            l = l.strip().lower()
                            if(l):
                                # Get another complete line to check for nested if statements
                                l_cont, newct = line_unwrapper(lines=lines,ct=linenum)
                                l_cont = l_cont.strip().lower()

                                match_nested_ifthen = regex_ifthen.search(l_cont)
                                if(match_nested_ifthen): 
                                    if_counter+=1
                                # See if we are at the end of the if statement
                                match_end_if = regex_endif.search(l)
                                if(match_end_if): 
                                    if_counter-=1
                                lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
                                ct = AdjustLine(ct,newct,linenum)
                                linenum = newct

                    else: # not match_ifthen
                        lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
                        ct = AdjustLine(ct,newct,linenum)
                        linenum = newct
                else: # not match_if
                    lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
                    ct = AdjustLine(ct,newct,linenum)
                    linenum = newct
            elif(match_decl and not in_subroutine):
                lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
                ct = AdjustLine(ct,newct,linenum)
                linenum = newct
        elif(re.search(r'(gsmap)',l.lower() )):
            if(verbose):
                print("Removing gsmap ")
            lines, newct = comment_line(lines=lines,ct=linenum,verbose=verbose)
            ct = AdjustLine(ct,newct,linenum)
            linenum = newct
        
        # match SHR_ASSERT_ALL
        match_assert = re.search(r'^[\s]+(SHR_ASSERT_ALL|SHR_ASSERT)\b',line)
        if(match_assert):
            lines, newct = comment_line(lines=lines,ct=ct)
            ct = AdjustLine(ct,newct,linenum)
            linenum = newct
        
        match_end = re.search(r'^(\s*end subroutine)',lines[ct])
        if(match_end):
            in_subroutine = False
            # Instantiate Subroutine if not already done
            if(subname not in sub_dict):
                if(cpp_file):
                    endline = linenum
                else:
                    endline = ct 
                if(verbose):
                    print(f"{func_name}:: Instantiating Subroutine {subname} at "
                          + f"L{sub_start}-{endline} in {base_fn}")
                sub = Subroutine(subname,fn,[''],start=sub_start,end=endline)
                sub_dict[subname] = sub
                
            else:
                if(verbose):
                    print(f"{func_name}::Subroutine {subname} already in sub_dict")

        # increment line numbers.
        linenum+=1
        ct+=1
    # Added to try and avoid the compilation
    # warnings about not declaring procedures
    if(subs_removed and overwrite):
        lines = remove_reference_to_subroutine(lines=lines,subnames=subs_removed)

    return None 


def process_for_unit_test(fname,case_dir,mods=None,
                          required_mods=[], main_sub_dict={},
                          overwrite=False,verbose=True,singlefile=False):
    """
    This function looks at the whole .F90 file.
    Comments out functions that are cumbersome
    for unit testing purposes.
    Gets module dependencies of the module and
    process them recursively.

    Arguments:
        fname -> File path for .F90 file that with needed subroutine
        case_dir -> label of Unit Test
        mods     -> list of already known (if any) files that were previously processed
        required_mods -> list of modules that are required for the unit test (see mod_config.py)
        main_sub_dict -> dictionary of all subroutines encountered for the unit test.
        verbose  -> Print more info
        singlefile -> flag that disables recursive processing.
    """
    sub_dict = main_sub_dict.copy()
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

    # Next process required modules if they are not already in the list
    # save current processed mods:
    temp_mods = mods[:]
    
    required_mod_paths = [get_filename_from_module(m) for m in required_mods]
    for rmod in required_mod_paths:
        if(rmod not in mods):
            mods.append(rmod)
            mods, mod_dict = get_used_mods(ifile=rmod,mods=mods,
                                                     verbose=verbose,singlefile=singlefile,
                                                     mod_dict=mod_dict)
    if(verbose):
        print(f"Newly added mods after processing required mods:")
        for m in mods:
            if(m not in temp_mods):
                match_ = re.search(r'(?<=/)(\w+\.F90)',m)
                print(match_.group())
        
    if(verbose):
        print("Total modules to edit are\n",mod_dict.keys() )
        print("Modules to be removed list\n", bad_modules)

    for mod_file in mods:
        # Avoid preprocessing files over and over
        if (mod_file in initial_mods): 
            continue
        file = open(mod_file,'r')
        lines = file.readlines()
        file.close()
        if(verbose): 
            print(f"Processing {mod_file}")
        modify_file(lines, mod_file, sub_dict, 
                    verbose=verbose,overwrite=overwrite)
        if(overwrite):
            out_fn = mod_file
            if(verbose): print("Writing to file:",out_fn)
            with open(out_fn,'w') as ofile:
                ofile.writelines(lines)
    
    # Transfer subroutines to main dictionary
    for subname, sub in sub_dict.items():
        if(subname not in main_sub_dict):
            main_sub_dict[subname] = sub
    
    # Sort the file dependencies
    # (NOTE: Could write a make file to do this instead and
    # read the results back into SPEL?)
    linenumber, unit_test_module = get_module_name_from_file(fpath=fname)
    file_list = sort_file_dependency(mod_dict,unit_test_module)
    for m in required_mods:
        file_list = sort_file_dependency(mod_dict, m.lower())
    
    if(verbose):
        print(f"File list for Unit Test: {case_dir}")
        for f in file_list:
            print(f)
    
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
        if(dependency_mod.filepath not in file_list): 
            file_list.append(dependency_mod.filepath)

    if(main_fort_mod.filepath not in file_list):
        file_list.append(main_fort_mod.filepath)

    return file_list