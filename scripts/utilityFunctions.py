"""
Python Module that collects functions that 
have broad utility for several modules in SPEL 
"""
import sys 
import re 
import subprocess as sp
from mod_config import ELM_SRC, _bc

# Regular Expressions
find_type = re.compile(r'(?<=\()\w+(?=\))') # Matches type(user-type) -> user-type
# Match any variable declarations
find_variables = re.compile(r'^(class\s*\(|type\s*\(|integer|real|logical|character)',re.IGNORECASE)
# Match variable names
regex_var = re.compile(r'\w+')
# Match subgrid index i.e., bounds%begc -> c
regex_subgrid_index = re.compile(r'(?<=bounds\%beg)[a-z]',re.IGNORECASE)
# Capture instrinsic types to separate from user-defined types
intrinsic_type = re.compile(r'^(integer|real|logical|character)', re.IGNORECASE)
# Capture user-defined types
user_type = re.compile(r'^(class\s*\(|type\s*\()',re.IGNORECASE) 
# non-greedy capture for arrays
ng_regex_array = re.compile(f'\w+?\s*\(.+?\)')
# capture array bounds only:
regex_bounds = re.compile(r'(?<=(\w|\s))\(.+\)')
class Variable(object):
    """
    Class to hold information on the variable
    declarations in a subroutine 
        * self.type -> data type of variable 
        * self.name -> name of variable 
        * self.subgrid -> subgrid level used for allocation 
        * self.ln -> line number of declaration
    """
    def __init__(self, type,name,subgrid,ln,
                 dim,declaration='',optional=False,keyword=''):
        self.type = type
        self.name = name
        self.subgrid = subgrid
        self.ln = ln 
        self.dim = dim
        # These are used for Argument variables
        self.optional = optional
        self.keyword = keyword
        self.filter_used = ''
        self.subs = []
        if(declaration):
            self.declaration = declaration
        else:
            self.declaration = '' 

    # Define equality for comparison of two Variables
    def __eq__(self,other):
        if(self.name == other.name and self.type == other.type 
            and self.dim == other.dim):
            return True
        else:
            return False
    
    # Override __str__ for easy printing
    def __str__(self):
        return f"{self.type} {self.name} {self.dim}"

    def printVariable(self,ofile=None): 
        if(ofile):
            ofile.write(f"{self.type} {self.dim}-D {self.name}\n")
            if(self.subs):
                ofile.write(f"Passed to {self.subs} {self.keyword}\n")
        else:
            print(f"{self.type} {self.dim}-D {self.name}")
            if(self.subs):
                print(f"Passed to {self.subs} {self.keyword}")
        
def comment_line(lines,ct,mode='normal',verbose=False):
    """
    function comments out lines accounting for line continuation
    """
    if(mode == 'normal'): comment_ = '!#py '
    if(mode == 'fates' ): comment_ = '!#fates_py '
    if(mode == 'betr'  ): comment_ = '!#betr_py '
    
    newline = lines[ct]
    # Get first non-whitespace character:
    str_ = newline.strip()[0]
    if(not str_): 
        print("comment_line :: Error - Empty line")
    
    newline = newline.replace(str_,comment_+str_,1)
    lines[ct] = newline
    continuation = bool(newline.strip('\n').endswith('&'))
    if(verbose): print(lines[ct].rstrip('\n'))
    while(continuation):
        ct +=1
        newline = lines[ct]
        str_ = newline.split()[0]
        newline = newline.replace(str_, comment_+str_,1)
        lines[ct] = newline
        if(verbose): print(lines[ct].rstrip('\n'))
        continuation = bool(newline.strip('\n').endswith('&'))
    return lines, ct

def removeBounds(line,verbose=False):
    """
    This function matches (:,:,:) and removes it from the line

    """
    cc = "[ a-zA-Z0-9%\-\+]*?:[ a-zA-Z0-9%\-\+]*?"
    non_greedy1D = re.compile(f"\({cc}\)")
    non_greedy2D = re.compile(f"\({cc},{cc}\)")
    non_greedy3D = re.compile(f"\({cc},{cc},{cc}\)")
    non_greedy4D = re.compile(f"\({cc},{cc},{cc},{cc}\)")
    newline = line

    m1D = non_greedy1D.findall(newline)
    for bound in m1D: 
        newline = newline.replace(bound,'')

    m2D = non_greedy2D.findall(newline)
    for bound in m2D:
        newline = newline.replace(bound,'')

    m3D = non_greedy3D.findall(newline)
    for bound in m3D: 
        newline = newline.replace(bound,'')

    m4D = non_greedy4D.findall(newline)
    for bound in m4D: 
        newline = newline.replace(bound,'')

    match_arrays = ng_regex_array.findall(newline)
    # Check if an array is being assigned
    match_array_init = re.search(r'(\(/)(.+)(/\))',newline) 
    if(match_arrays):
        # not all bounds could be removed. 
        # Check if they are of the form arr(1,2) (no semicolon)
        for arr in match_arrays:
            expr = regex_bounds.search(arr).group()
            newline = newline.replace(expr,'')
    elif(match_array_init):
        newline = newline.replace(match_array_init.group(),'')
    
    
    match_arrays = ng_regex_array.findall(newline)
    if(match_arrays):
        print(f"removeBounds::Error - Coudln't remove array bounds completely")
        print(f"line: {line}")
        sys.exit(1)
    
    return newline


def getArguments(l,verbose=False):
    """
    Function that takes a string of the subroutine call
    as an argument and returns the variables 
    passed as arguments. 

    Will be used to compare with the subroutine's 
    argument list.
    
    This is neccessary to change variable allocations,
    resolve ambiguities from interfaces, and
    track global variables passed as arguments.
    """
    if(verbose): print(_bc.WARNING+f"getArguments:: Processing {l}\n\n"+_bc.ENDC)
    # Matches longest string between parentheses
    par = re.compile("(?<=\().+(?=\))")
    m = par.search(l)
    if(not m): 
        args = []
        return args
    args = m.group()
    
    # Remove bounds from arrays so that only argument names are comma separated
    newargs = removeBounds(args,verbose)

    args = newargs.split(',')
    args = [x.strip() for x in args]

    return args

def lineContinuationAdjustment(lines,ln,verbose=False): 
   """
   This function returns takes a string that
   accounts for line continuations 

   Could be simpler/easier to read without using enumerate 
   in calling loop. 
   """
   l = lines[ln];
   l = l.split('!')[0]
   l = l.strip().lower()
   l = l.rstrip('\n')

   lines_to_skip = 0
   while(l.endswith('&')): 
      lines_to_skip+=1
      ct = ln+lines_to_skip
      newline = lines[ct].split('!')[0]
      newline = newline.strip().lower() 
      l = l[:-1] + newline.strip().rstrip('\n')

   if(verbose and lines_to_skip > 0): 
      print("Started with line: ")
      print(lines[ln]) 
      print("Returning line:")
      print(l)
      print(f"Skipped {lines_to_skip} lines")

   return l, lines_to_skip

def find_end_subroutine(fn,startline):
    """
    Function that will find next "end subroutine" statement starting
    from the subroutine starting line 'startline'.
    
    This may be needed in case the 'end subroutine <subroutine_name>'
    convention is not used.
    """
    func_name = "find_end_subroutine"
    ifile = open(fn,'r')
    lines = ifile.readlines()
    ifile.close()
    regex_end_subroutine = re.compile(r'\s*(end)\s+(subroutine)',re.IGNORECASE)
    for ln in range(startline,len(lines)):
        line = lines[ln]
        #get rid of comments
        line = line.split('!')[0]
        line = line.strip()
        if(not line): continue
        match = regex_end_subroutine.search(line)
        if(match):
            endline = ln
            break
    
    return endline

def find_file_for_subroutine(name,fn='',ignore_interface=False):
    """
    finds file, start and end line numbers for subroutines
    find file and start of interface block for interfaces
    """
    func_name = "find_file_for_subroutine"
    if(not fn):
        search_file = f"{ELM_SRC}*"
    else:
        search_file = f"{fn}"
    
    interface_list = get_interface_list() 
    if(name not in interface_list or ignore_interface):
        cmd = f'grep -rin -E "^[[:space:]]*(subroutine[[:space:]]* {name})\\b" {search_file} | head -1'
        cmd_end = f'grep -rin -E "^[[:space:]]*(end subroutine[[:space:]]* {name})\\b" {search_file} | head -1'
    else:
        cmd = f'grep -rin -E "^[[:space:]]+(interface[[:space:]]* {name})" {search_file} | head -1'
        cmd_end = ''

    output = sp.getoutput(cmd)
    if(not fn):
        file = output.split(':')[0]
        # Need to separate the file name and path
        # fpath = dir_regex.search(file).group()
        # file = dir_regex.sub('',file)
        output = output.split(':')
        if(len(output) < 2 ):
            print(f"Error: Couldn't find info for {name}\n {output}")
            sys.exit()
        startline = int(output[1])
        if(cmd_end!=''):
            output = sp.getoutput(cmd_end)
            if(not output):
                print(f"{func_name}::Didn't match end of subroutine\n output: {output}")
                endline = find_end_subroutine(file,startline)
                print(f"{func_name}::Endline found: {endline} for {name}")
            else:
                endline = int(output.split(':')[1]) 
        else:
            endline = 0
    else:
        file = fn
        output = output.split(':') 
        if(len(output) < 2):
            sys.exit(f"{func_name}::Didn't match subroutine\n cmd: {cmd}\n output: {output}")
        startline = int(output[0])
        if(cmd_end!=''):
            output = sp.getoutput(cmd_end)
            if(not output):
                print(f"{func_name}::Didn't match end of subroutine\n output: {output}") 
                endline = find_end_subroutine(file,startline)
                print(f"{func_name}::Endline found: {endline} for {name}")
            else:
                output = output.split(':')
                endline = int(output[0])
        else:
            endline = 0
    
    if(file == 'grep'):
        print(f"ERROR FILE FOR {name} NOT PRESENT")
        sys.exit(1)

    return file, startline, endline

def get_interface_list():
    """
    returns a list of all interfaces

    NOTE:  Should store it in mod_config so it's only run once per 
           Unit Test creation
    """
    import os 
    cmd = f'grep -rin --exclude-dir={ELM_SRC}external_models/ -E "^[[:space:]]+(interface)" {ELM_SRC}*'
    output = sp.getoutput(cmd)
    output = output.split('\n')
    interface_list = []
    for el in output:
        el = el.split()
        interface = el[2]
        interface_list.append(interface.lower())

    return interface_list

def getLocalVariables(sub,verbose=False,class_var=False ):
    """
    this function will retrieve  the local variables from
    the subroutine at startline, endline in the given file

    Note: currently only looks at type declaration for class object
    """
    func_name = "getLocalVariables"

    filename = sub.filepath
    subname = sub.name 
    file = open(filename,'r')
    lines = file.readlines()
    file.close()
    startline = sub.startline 
    endline = sub.endline

    args_present = bool(sub.dummy_args_list)
    if(verbose): 
        print(f"{func_name}::{filename},{subname} at L{startline}-{endline}")
    cc = "." 
    # non-greedy capture
    ng_regex_array = re.compile(f'\w+?\s*\({cc}+?\)')
    if(args_present):
        arg_string = '|'.join(sub.dummy_args_list)
        find_arg = re.compile(r'\b({})\b'.format(arg_string),re.IGNORECASE)
        if(verbose): 
            print(f"{func_name}::arg_string\n{arg_string}")
    else:
        match_arg = None

    find_type = re.compile(r'(?<=\()\w+(?=\))')
    class_var = re.compile(r'^(class\s*\()',re.IGNORECASE)
    find_variables = re.compile('^(class\s*\(|type\s*\(|integer|real|logical|character)',re.IGNORECASE)
    regex_var = re.compile(r'\w+')
    regex_subgrid_index = re.compile('(?<=bounds\%beg)[a-z]',re.IGNORECASE)
    # test for intrinsic data types or user defined
    intrinsic_type = re.compile(r'^(integer|real|logical|character)', re.IGNORECASE)
    user_type = re.compile(r'^(class\s*\(|type\s*\()',re.IGNORECASE)

    #
    for ln in range(startline,endline):
        line = lines[ln].split("!")[0]
        line = line.strip()
        line = line.strip("\n")
        if(not(line)): continue
        match_variable = find_variables.search(line)
        
        if(match_variable):
            # Track variable declaration start / end 
            if(sub.var_declaration_startl == 0):
                sub.var_declaration_startl = ln
            # store everytime we find a variable declaration
            sub.var_declaration_endl = ln 
            if("::" not in line): 
                # Repeated code here, could be simplified?
                # Need to check if variable declarations w/o '::'
                # have more syntax restrictions.
                m_type = intrinsic_type.search(line)
                if(m_type):
                    data_type = m_type.group()
                else: #user-defined type 
                    m_type = user_type.search(line)
                    if(not m_type): 
                        print(f"{func_name}::Error Can't Identify Data Type for {line}") 
                        sys.exit(1)
                    data_type = find_type.search(line).group()
                
                temp_vars = intrinsic_type.sub('',line)
            else:
                # Could be a list of variables
                temp_decl = line.split("::")[0]
                temp_vars = line.split("::")[1]
            
                # Get data type first 
                m_type = intrinsic_type.search(temp_decl)
                if(m_type):
                    data_type = m_type.group() 
                else: #user-defined type 
                    m_type = user_type.search(temp_decl)
                    if(not m_type):
                        print(f"{func_name}::Error: Can't Identify Data Type for {line}") 
                        sys.exit(1)
                    data_type = find_type.search(temp_decl).group()
            match_class = class_var.search(line)
            if(match_class):
                sub.class_method = True
                sub.class_type = data_type
            #
            # Go through and replace all arrays first
            #
            match_arrays = ng_regex_array.findall(temp_vars)
            if(match_arrays): 
                for arr in match_arrays:
                    varname = regex_var.search(arr).group()
                    index = regex_subgrid_index.search(arr)
                    if(index):
                        subgrid = index.group() 
                    else:
                        subgrid = '?'
                    # Storing line number of declaration 
                    dim = arr.count(',')+1
                    # Test if variable is same as a dummy argument
                    if(args_present):
                        match_arg = find_arg.search(varname)
                    if(match_arg):
                        if('optional' in temp_decl):
                            optional = True
                        else:
                            optional = False
                        sub.Arguments[varname] = Variable(data_type,varname,subgrid,ln,dim,optional=optional)
                    else: 
                        sub.LocalVariables['arrays'][varname] = Variable(data_type,varname,subgrid,ln,dim)
                        sub.LocalVariables['arrays'][varname].declaration = line
                    # This removes the array from the list of variables
                    temp_vars = temp_vars.replace(arr,'')

            # Get the scalar arguments  
            temp_vars = temp_vars.split(',')
            temp_vars = [x.strip() for x in temp_vars if x.strip()]
            for var in temp_vars:
                if(args_present):
                    match_arg = find_arg.search(var)
                if(match_arg):
                    if('optional' in temp_decl):
                        optional = True
                    else:
                        optional = False
                    sub.Arguments[var] = Variable(data_type,var,'',ln,dim=0,optional=optional)
                else:
                    parameter = bool("parameter" in temp_decl.lower())
                    if(parameter): continue
                    if("=" in var): var = var.split("=")[0]
                    sub.LocalVariables['scalars'][var] = Variable(data_type,var,'',ln,dim=0)
    return

def determine_class_instance(sub,verbose=False):
    """
    Find out what the data structure 'this' corresponds to
    """
    import subprocess as sp 
    func_name = "determine_class_instance"
    filename = sub.filepath
    
    subname = sub.name 
    # Open file and  loop through subroutine lines
    file = open(filename,'r');
    lines = file.readlines()
    file.close()
    startline = sub.startline; endline=sub.endline;

    find_this = re.compile(r'^(type)',re.IGNORECASE)
    find_type = re.compile(r'(?<=\()\w+(?=\))')
    print(f"{func_name}::Determining variable for {subname}")
    found_this = False
    for ln in range(startline,endline):
        line = lines[ln].split("!")[0]
        line = line.strip()
        line = line.strip("\n")
        if(not(line)): continue

        m_this = find_this.search(line.lower())
        m_type = find_type.search(line.lower())
    
        if(m_this and m_type):
            # the derived type should always be 1st
            var_type = m_type.group()
            found_this = True 
            if(verbose): 
                print(f"{func_name}:: 'this' -> {var_type}")
            break
            
    if(not found_this):
        print(f"Error: Couldn't find declaration for class variable in {sub.name} {sub.filepath}")
        sys.exit()
    else:
        return var_type


def convertAssociateDict(associate_vars, varlist):
    """
    Need to eliminate this function and properly match arguments 
    """
    dtypes = []
    replace_inst = []
    for vars in associate_vars.values():
        for v in vars: 
            _type, field = v.split("%")
            if(_type in replace_inst):
                _type = _type.replace("_inst","vars")
            if(_type not in dtypes):
                dtypes.append(_type)

    return

def adjust_array_access_and_allocation(local_arrs,sub,dargs=False,verbose=False):
    """
    Function edits ELM FORTRAN files to reduce memory.
    Replaces statements like "arr(bounds%begc:bounds%endc)" -> "arr(1:num_filterc)" 
    and accesses like "arr(c)" -> "arr(fc)" 

    * local_arrs    : list of local array Variables
    * sub           : Subroutine that calls this function and declares the local_arrs
    * sub.VariablesPassedToSub : dictionary that matches "arr" to subroutines that take them as arguments
    """
    import re
    from mod_config import _bc, elm_files,home_dir
    import os.path 

    # Get lines of this file:
    ifile = open(elm_files+sub.filepath,'r')
    lines = ifile.readlines() # read entire file
    ifile.close()

    track_changes = []
    arg_list = [v for v in sub.Arguments] 
    scalar_list = [v.name for v in sub.LocalVariables['scalars'].values()]

    print(_bc.BOLD+_bc.FAIL+f"arguments for {sub.name} are",arg_list,_bc.ENDC)
    print(_bc.BOLD+_bc.FAIL+f"scalars for {sub.name} are",scalar_list,_bc.ENDC)

    # replace declarations first
    if(not dargs):
        for arr in local_arrs:
            var = arr 
            filter_used = arr.filter_used
            ln = var.ln; #line number of declaration
            subgrid = var.subgrid # subgrid index 

            print(_bc.BOLD+_bc.WARNING+f"Adjusting {var.name}"+_bc.ENDC)
            filter_used = filter_used + subgrid

            # Check that the corresponding num_filter exists
            num_filter = "num_"+filter_used.replace("filter_","")
            if(num_filter in arg_list):
                print(num_filter,"is passed as an argument!")
            elif(num_filter in scalar_list):
                print(f"{num_filter} is new local filter")
            else:
                sys.exit(f"utilityFunctions:: {num_filter} doesn't exit")
            lold = lines[ln]
            print(_bc.FAIL+lold.strip('\n')+_bc.ENDC)
            _str = f"bounds%beg{subgrid}:bounds%end{subgrid}"

            replace_str = f"1:{num_filter}"
            lnew = lines[ln].replace(_str,replace_str)
            print(_bc.OKGREEN+lnew.strip('\n')+_bc.ENDC)
            lines[ln] = lnew 
            track_changes.append(lnew)

    # Go through all loops and make replacements for filter index 
    ng_regex_array = re.compile("\w+\s*\([,\w+\*-]+\)",re.IGNORECASE)
    regex_var = re.compile(r'\w+')
    regex_indices = re.compile(r'(?<=\()(.+)(?=\))')
    print("Going through loops")
    # Make list for quick check if var should be adjusted.
    list_of_var_names = [v.name for v in local_arrs]

    for loop in sub.DoLoops:
        lstart = loop.start[0]; lend = loop.end[0]
        if(loop.subcall.name != sub.name): continue

        for n in range(lstart,lend):
            l = lines[n].split("!")[0]
            l = l.strip()
            if(not l): continue
            m_arr = ng_regex_array.findall(lines[n])
            lold = lines[n]
            lnew = lines[n]

            replaced = False 
            temp_line = lold
            
            removing = True
            while(removing):
                # set removing to be False unless there is a match
                removing = False 
                
                for arr in m_arr:
                    v = regex_var.search(arr).group()

                    # min and max functions are special cases since they take two argumnets (fix?)
                    if(v in ["min","max"]): 
                        temp_line = temp_line.replace(arr,v)
                        removing = True
                        continue

                    # Check if var is 
                    if(v in list_of_var_names):
                        loc_ = list_of_var_names.index(v)
                        local_var = local_arrs[loc_]
                        var = local_var
                        subgrid = var.subgrid
                        filter_used = var.filter_used + var.subgrid

                        # Consistency check for filter.
                        # TODO: allow scripts to insert reverse filter (eg., "fc = col_to_filter(c)" )
                        loop_filter = loop.filter[0] 
                        same_filter_type = bool(filter_used[:-1] == loop_filter[:-1])
                        if(filter_used != loop_filter and not same_filter_type):
                            print(f"Filter Mismatch: loops uses {loop.filter[0]}, {var.name} needs {filter_used}")
                            sys.exit()
                        elif(same_filter_type and filter_used != loop_filter):
                            print(_bc.WARNING+_bc.BOLD+f"{var.name} needs reverse filter!")

                        # Make replacement in line: (assumes subgrid is first index!!)
                        # lnew = lnew.replace(f"{v}({subgrid}",f"{v}(f{subgrid}")
                        lnew = re.sub(f"{v}\s*\({subgrid}",f"{v}(f{subgrid}",lnew)
                        replaced = True 

                    regex_check_index = re.compile(f"\w+\([,a-z0-9*-]*(({v})\(.\))[,a-z+0-9-]*\)",re.IGNORECASE)
                    match = regex_check_index.search(temp_line)
                    if(match): # array {v} is being used as an index
                        # substitute from the entire line 
                        i = regex_indices.search(arr).group()
                        i = f"\({i}\)"
                        temp_line = re.sub(f"{v}{i}",v,temp_line)
                        removing = True
                m_arr = ng_regex_array.findall(temp_line)
                
            if(replaced and verbose):
                print(_bc.FAIL + lold.strip('\n') + _bc.ENDC)
                print(_bc.OKGREEN+lnew.strip('\n')+_bc.ENDC)
                print("\n")
                lines[n] = lnew
                track_changes.append(lnew)

    
    # Check if subroutine calls need to be adjusted
    # First filter out sub arguments that aren't local 
    # variables only accessed by a filter 
    # Adjust Subroutine calls

    # Note that these subroutines have specific versions for 
    # using filter or not using a filter. 
    dont_adjust = ['c2g','p2c','p2g','p2c','c2l','l2g']
    dont_adjust_string = '|'.join(dont_adjust)
    regex_skip_string = re.compile(f"({dont_adjust_string})",re.IGNORECASE)

    vars_to_check = { s : [] for s in sub.VariablesPassedToSubs }
    for subname, arg in sub.VariablesPassedToSubs.items():
        m_skip = regex_skip_string.search(subname)
        if(m_skip): 
            print(_bc.FAIL+f"{subname} must be manually altered !"+_bc.ENDC)
            continue  
        for v in arg: 
            if(v.name in list_of_var_names):
                print(f"Need to check {v.name} for mem adjustment called in {subname}.")
                vars_to_check[subname].append(v)
    
    for sname, vars in vars_to_check.items():
        for v in vars:
            print(f"{sname} :: {v.name}")
    
    for subname,args in sub.VariablesPassedToSubs.items(): 
        m_skip = regex_skip_string.search(subname)
        if(m_skip): 
            print(_bc.FAIL+f"{subname} must be manually altered !"+_bc.ENDC)
            continue    
        regex_subcall = re.compile(f'\s+(call)\s+({subname})',re.IGNORECASE)
        
        for arg in args: 
            # If index fails, then there is an inconsistency 
            # in examineLoops 
            if(arg.name not in list_of_var_names): continue 
            loc_ = list_of_var_names.index(arg.name)
            local_var = local_arrs[loc_]
            filter_used = local_var.filter_used + arg.subgrid
            # bounds string:
            bounds_string = f"(\s*bounds%beg{arg.subgrid}\s*:\s*bounds%end{arg.subgrid}\s*|\s*beg{arg.subgrid}\s*:\s*end{arg.subgrid}\s*)"
            # string to replace bounds with
            num_filter = "num_"+filter_used.replace("filter_","")
            num_filter = f"1:{num_filter}"
            regex_array_arg = re.compile(f"{arg.name}\s*\({bounds_string}")

            for ln in range(sub.startline, sub.endline):
                line = lines[ln]
                match_call = regex_subcall.search(line)
                if(match_call): 
                    replaced = False 
                    # create regex to match variables needed
                    l = line[:]
                    m_var = regex_array_arg.search(l)
                    if(m_var):
                        lold = lines[ln].rstrip('\n')
                        lnew = regex_array_arg.sub(f"{arg.name}({num_filter}",lines[ln])
                        lines[ln] = lnew
                        replaced = True
                        track_changes.append(lnew)

                    while(l.rstrip('\n').endswith('&') and not replaced):
                        ln += 1
                        l = lines[ln]
                        m_var = regex_array_arg.search(l)
                        if(m_var): 
                            lold = lines[ln].rstrip('\n')
                            lnew = regex_array_arg.sub(f"{arg.name}({num_filter}",lines[ln])
                            lines[ln] = lnew 
                            replaced = True 
                            track_changes.append(lnew)

                    if(replaced): 
                        print(_bc.FAIL   +lold.rstrip('\n')+_bc.ENDC)
                        print(_bc.OKGREEN+lnew.rstrip('\n')+_bc.ENDC)
                        print("\n")
                        break
                    else:
                        print(_bc.FAIL+f"Couldn't replace {arg.name} in {subname} subroutine call"+_bc.ENDC)
                        sys.exit()

    # Save changes:
    if(track_changes):
        if(not os.path.exists(home_dir+f"modified-files/{sub.filepath}")):
            print(_bc.BOLD+_bc.WARNING+"Writing to file ",home_dir+f"modified-files/{sub.filepath}"+_bc.ENDC)
            ofile = open(home_dir+f"modified-files/{sub.filepath}",'w')
            ofile.writelines(lines) 
            ofile.close()
        else: 
            print(_bc.BOLD+_bc.WARNING+"Writing to file ",elm_files+sub.filepath+_bc.ENDC)
            ofile = open(elm_files+sub.filepath,'w')
            ofile.writelines(lines) 
            ofile.close()

    for subname,args in sub.VariablesPassedToSubs.items():
        # Modify dummy arguments for child subs if needed 
        # may be redundant to find file here?
        #         
        m_skip = regex_skip_string.search(subname)
        if(m_skip): 
            print(_bc.FAIL+f"{subname} must be manually altered !"+_bc.ENDC)
            continue  
        print(_bc.WARNING+f"Modifying dummy args for {subname}")
        file,startline,endline = find_file_for_subroutine(subname)
        childsub = sub.child_Subroutine[subname]
        adjust_child_sub_arguments(childsub,file,startline,endline,args)
        

def adjust_child_sub_arguments(sub,file,lstart,lend,args):
    """
    Function that checks and modifies bounds accesses 
    for subroutine arguments 
        * childsub : Subroutine instance for child subroutine 
        * arg : Variable instance for dummy arg name
    """
    import os 
    from mod_config import home_dir, _bc

    if(os.path.exists(home_dir+f"modified-files/{file}")):
            print(file,"has already been modified")
            file = f"../modified-files/{file}"
    
    print(f"Opening {sub.filepath}")
    ifile = open(sub.filepath,'r') 
    lines = ifile.readlines() 
    ifile.close() 

    for arg in args:
        # Use keyword instead of arg name.  
        # If keyword is missing then we need to determine the name!
        kw = arg.keyword
        if(not kw): 
            sys.exit(f"Error keyword for {arg.name} in {sub.name} is missing")

        regex_arg_type = re.compile(f"{arg.type}",re.IGNORECASE)
        regex_arg_name = re.compile(f"{kw}\s*\(",re.IGNORECASE)
        regex_bounds_full = re.compile(f"({kw}\s*\()(bounds%beg{arg.subgrid})\s*(:)\s*(bounds%end{arg.subgrid})\s*(\))",re.IGNORECASE)
        regex_bounds = re.compile(f"({kw}\s*\(\s*bounds%beg{arg.subgrid}[\s:]+\))",re.IGNORECASE)
        for ct in range(lstart-1,lend):
            #
            line= lines[ct]
            lold = line
            line = line.split("!")[0] 
            line = line.strip()

            replaced = False 
            # Match type and name for arg 
            match_type = regex_arg_type.search(line) 
            match_name = regex_arg_name.search(line)

            if(match_type and match_name): 
                match_bounds = regex_bounds.search(line) 
                match_full_bounds = regex_bounds_full.search(line)
                if(match_bounds and not match_full_bounds):
                    lnew = regex_bounds.sub(f"{kw}(1:)",lold)
                    lines[ct] = lnew
                    print(_bc.BOLD+_bc.FAIL+lold.rstrip('\n')+_bc.ENDC)
                    print(_bc.BOLD+_bc.OKGREEN+lnew.rstrip('\n')+_bc.ENDC)
                    replaced = True
                else:
                    print(f"{line} -- No Action Needed")
                    sys.exit()
    
    # Write to file 
    with open(sub.filepath,'w') as ofile:
        ofile.writelines(lines)
    
    # re-run access adjustment for the dummy args only!
    sub.filepath = file
    print(f"Adjust dargs for {sub.name} at {sub.filepath}")
    dargs = [] 
    for arg in args:
        v = arg
        v.name = v.keyword 
        v.keyword = ''

    adjust_array_access_and_allocation(local_arrs=args,sub=sub,verbose=True,dargs=True)
    sys.exit("Why is this here?")
    
def determine_filter_access(sub,verbose=False):
    """
    Function that will go through all the loops for 
    local variables that are bounds accessed.
    """
    
    print(_bc.BOLD+_bc.WARNING+f"Adjusting Allocation for {sub.name}"+_bc.ENDC)
    
    # TODO: 
    # Insert function call to check if any local 
    # variables are passed as subroutine arguments 
    if(verbose): print("Checking if variables can be allocated by filter")
    ok_to_replace = {}
    
    # List that accumulates all info necessary for memory adjustment
    local_vars = []  # [Variable]
    array_dict = sub.LocalVariables["arrays"]
    for vname, lcl_var in array_dict.items():
        if(lcl_var.subgrid == "?"): continue 
        lcl_arr = lcl_var.name 
        ok_to_replace[lcl_arr] = False 
        filter_used = ''
        indx, ln = lcl_var.subgrid, lcl_var.ln 
        for loop in sub.DoLoops: 
            if(loop.subcall.name != sub.name): continue 
            if(lcl_arr in loop.vars or lcl_arr in loop.reduce_vars):
                if(not loop.filter): # Loop doesn't use a filter?
                    filter_used = "None"
                    continue
                fvar, fidx, newidx = loop.filter
                # Case where no filter is used 
                if(not fvar): 
                    if(indx not in loop.index):
                        print(f"{lcl_arr} {indx} used in {loop.subcall.name}:L{loop.start[0]} {fvar},{fidx}{loop.index}")
                if(not filter_used):
                    # Get rid of the subgrid info
                    filter_used = fvar[:-1]
                elif(filter_used != fvar[:-1] and filter_used != "Mixed"):
                    print(_bc.BOLD+_bc.HEADER+f"{lcl_arr} {indx} used in {loop.subcall.name}:L{loop.start[0]} {fvar},{fidx}{loop.index}"+_bc.ENDC)
                    filter_used = "Mixed"
                    break
        #
        if(filter_used == "None"):
            print(f"No filter being used -- won't adjust {lcl_arr}")
        elif(filter_used == "Mixed"): 
            print(_bc.WARNING+f"{lcl_arr} has multiple filters being used -- won't adjust"+_bc.ENDC)
            ok_to_replace[lcl_arr] = False 
        elif(filter_used and filter_used != "Mixed"):
            print(f"{lcl_arr} only uses {filter_used}{indx}")
            ok_to_replace[lcl_arr] = True 
            lcl_var.filter_used = filter_used
            local_vars.append(lcl_var)
        else: 
            print(_bc.WARNING + f"{lcl_arr} is not used by any loops!!"+ _bc.ENDC)
        
    if(local_vars):
        list_of_var_names = [v.name for v in local_vars]
        print(_bc.BOLD+_bc.HEADER+f"Adjusting {sub.name} vars:{list_of_var_names}"+_bc.ENDC)
        adjust_array_access_and_allocation(local_vars, sub=sub,verbose=True)
    else:
        print(_bc.BOLD+_bc.HEADER+f"No variables need to be adjusted for {sub.name}"+_bc.ENDC)

def line_unwrapper(lines,ct,verbose=False):
    """
    Function that takes code segment that has line continuations
    and returns it all on one line.
    """
    l = lines[ct].split('!')[0] # remove comments
    # remove new line character 
    l = l.rstrip('\n').strip()
    continuation = bool(l.endswith('&'))
    full_line = l    
    newct = ct
    while(continuation):
        newct += 1
        l = lines[newct].split('!')[0] # in case of inline comments
        l = l.rstrip('\n')
        # Fortran allow empty lines in between line continuations
        if(l.isspace() or not l):
            continue
        full_line = full_line[:-1] + l.strip()
        continuation = bool(full_line.endswith('&'))
    
    # Debug check:
    if(verbose):
        print("Original lines:\n",lines[ct:newct])
        print("Single line\n:",full_line)

    return full_line, newct

def insert_header_for_unittest(file_list,mod_dict):
    """
    Function that will insert the header file into files needed for unit test
    The header file contains definitions to aid in compilation (e.g, override pio types) 
    """
    for f in file_list:
        for mod in mod_dict:
            if(f == mod_dict[mod].filepath):
                linenumber = mod_dict[mod].ln
                break
        ifile = open(f,'r')
        lines = ifile.readlines()
        ifile.close()
        # First check if the header is already included
        match_include = re.search(r'^(#include "unittest_defs.h")',lines[linenumber+1])
        if(match_include):
            print("unittest_defs already included")
            continue
        else:
            lines.insert(linenumber,'#include "unittest_defs.h"\n')
            with(open(f,'w')) as ofile:
                ofile.writelines(lines)
    return file_list

def parse_line_for_variables(ifile,l,ln,verbose=False):
    """
    Function that takes a line of code and returns the variables 
    that are declared in it. 
    """
    # NOTE: This code is duplicated from getLocalVariables
    #       which should be refactored?
    func_name = "parse_line_for_variables"
    variable_list = [] 
    match_var = find_variables.search(l)
    if(match_var):
        if("::" not in l):
            # regex to separate type from variable when there is no '::' separator 
            ng_type = re.compile(f'^\w+?\s*\(.+?\)')
            match_type = ng_type.search(l)
            if(match_type): # Means there exists a character(len=) or type(.) or real(r8)
                temp_decl = match_type.group() 
                temp_vars = l.split(temp_decl)[1] 
            else: # means it's a simple decl such as 'integer' 
                temp_decl = find_variables.search(l)
                temp_vars = find_variables.sub('',l).strip()
        else:
            temp = l.split("::") # Is this a poor assumption?
            if(len(temp)<2):
                print(f"{func_name}:: Error - Thought there was a variable decl at \n {ifile}::L{ln+1}\n{l} ")
                sys.exit(1)
            temp_decl = l.split("::")[0]
            temp_vars = l.split("::")[1]
            if(verbose): 
                print(f"temp_decl: {temp_decl} temp_vars: {temp_vars}")

        # Get data type of variable by checking for intrinsic types
        # and then user-defined types separately  
        m_type = intrinsic_type.search(temp_decl)
        if(m_type):
            data_type = m_type.group() 
            if(verbose): print("matched data type: ",data_type)
        else: # User-Defined Type 
            m_type = user_type.search(temp_decl)
            if(not m_type): 
                print(f"Error: Can't Identify Data Type for {ifile}::L{ln+1}\n {l}")
                print(f"decl: {temp_decl}")
                sys.exit(1)
            data_type = find_type.search(temp_decl).group()
            if(verbose): 
                print("matched user data type: ",data_type)
        
        # Go through and replace all arrays first
        # match_arrays = ng_regex_array.findall(temp_vars)
        remove_slices = removeBounds(temp_vars)

        var_list = remove_slices.split(',')
        var_list = [x.strip() for x in var_list if x.strip()]

        for var in var_list:
            if('=' in var):
                var = var.split('=')[0].strip()
            # Check if current variable is an array
            ng_var_array = re.compile(f'{var}?\s*\(.+?\)',re.IGNORECASE)
            match_array = ng_var_array.search(temp_vars)
            if(match_array):
                arr = match_array.group()
                index = regex_subgrid_index.search(var)
                if(index):
                    subgrid = index.group() 
                else:
                    if(verbose): 
                        print(f"{arr} Not allocated by bounds")
                    subgrid = '?'
                # Storing line number of declaration 
                dim = arr.count(',') + 1
                if(verbose): 
                    print(f"var = {var}; subgrid = {subgrid}; {dim}-D")
            else:
                parameter = bool("parameter" in temp_decl.lower())
                subgrid = ''
                dim = 0
            variable_list.append(Variable(data_type,var,subgrid,ln,dim) )

    return variable_list