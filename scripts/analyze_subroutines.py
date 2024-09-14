import os.path
import re
import sys
from collections import namedtuple

from LoopConstructs import Loop, exportVariableDependency
from mod_config import _bc, home_dir
from process_associate import getAssociateClauseVars
from utilityFunctions import \
    get_interface_list  # just make this a global variable?
from utilityFunctions import (find_file_for_subroutine, getLocalVariables,
                              line_unwrapper)

# Declare namedtuple for readwrite status of variables:
ReadWrite = namedtuple('ReadWrite',['status','ln'])

# namedtuple to log the subroutines called and their arguments 
# to properly match read/write status of variables.
# SubroutineCall = namedtuple('SubroutineCall',['subname','args'])
# subclass namedtuple to allow overriding equality.
class SubroutineCall(namedtuple('SubroutineCall',['subname','args'])):
    def __eq__(self,other):
        return ((self.subname == other.subname) and (self.args == other.args))

def determine_variable_status(matched_variables, line,
                               ct, dtype_accessed, verbose=False):
    """
    Function that loops through each var in match_variables and 
    determines the ReadWrite status.

    Move to utilityFunctions.py?  Use for loop variable analysis as well?
    """
    func_name = "determine_variable_status"
    # match assignment
    match_assignment   =  re.search(r'(?<![><=/])=(?![><=])', line)  
    # match do and if statements 
    match_doif = re.search(r'[\s]*(do |if[\s]*\(|else[\s]*if[\s]*\()',line)
    regex_indices = re.compile(r'(?<=\()(.+)(?=\))')

    # Loop through each derived type and determine rw status.
    for dtype in matched_variables:
        # if the variables are in an if or do statement, they are read
        if(match_doif):
            rw_status = ReadWrite('r',ct) 
            dtype_accessed.setdefault(dtype,[]).append(rw_status)
        # Split line into rhs and lhs of assignment.
        # What if there is no assignment:
        #   1) subroutine call, 2) i/o statement
        # which I think we can safely skip over here
        elif(match_assignment):
            m_start = match_assignment.start() 
            m_end = match_assignment.end()
            lhs = line[:m_start]
            rhs = line[m_end:]
            # Check if variable is on lhs or rhs of assignment
            # Note: don't use f-strings as they will not work with regex
            regex_var = re.compile(r'\b({})\b'.format(dtype),re.IGNORECASE)
            match_rhs = regex_var.search(rhs)
            # For LHS, remove any indices and check if variable is still present
            # if present in indices, store as read-only 
            indices = regex_indices.search(lhs)
            if(indices):
                match_index = regex_var.search(indices.group())
            else:
                match_index = None
            match_lhs = regex_var.search(lhs)
        
            # May be overkill to check each combination,
            # but better to capture all information and 
            # simplify in a separate function based on use case.
            if(match_lhs and not match_rhs):
                if(match_index):
                    rw_status = ReadWrite('r',ct)
                else:
                    rw_status = ReadWrite('w',ct)
                dtype_accessed.setdefault(dtype,[]).append(rw_status)
            elif(match_rhs and not match_lhs):
                rw_status = ReadWrite('r',ct)
                dtype_accessed.setdefault(dtype,[]).append(rw_status)
            elif(match_lhs and match_rhs):
                rw_status = ReadWrite('rw',ct)
                dtype_accessed.setdefault(dtype,[]).append(rw_status)
    
    return dtype_accessed
    
def determine_level_in_tree(branch,tree_to_write):
    """
    Will be called recursively
    branch is a list containing names of subroutines
    ordered by level in call_tree
    """
    for j in range(0,len(branch)):
        sub_el = branch[j]
        islist = bool(type(sub_el) is list)
        if(not islist):
            if(j+1 == len(branch)):
                tree_to_write.append([sub_el,j-1])
            elif(type(branch[j+1]) is list):
                tree_to_write.append([sub_el,j-1])
        if(islist):
            tree_to_write = determine_level_in_tree(sub_el,tree_to_write)
    return tree_to_write

def add_acc_routine_info(sub):
    """
    This function will add the !$acc routine directive to subroutine
    """
    filename = sub.filepath

    file = open(filename,'r')
    lines = file.readlines() # read entire file
    file.close()

    first_use = 0
    ct = sub.startline
    while(ct < sub.endline):
        line = lines[ct]
        l = line.split('!')[0]
        if(not l.strip()): ct+=1; continue; #line is just a commment

        if (first_use == 0):
            m = re.search(f'[\s]+(use)',line)
            if(m): first_use = ct;

            match_implicit_none = re.search(r'[\s]+(implicit none)',line)
            if(match_implicit_none): first_use = ct
            match_type = re.search(r'[\s]+(type|real|integer|logical|character)',line)
            if(match_type): first_use = ct

        ct+=1
    print(f'first_use = {first_use}')
    lines.insert(first_use,'      !$acc routine seq\n')
    print(f"Added !$acc to {sub.name} in {filename}")
    with open(filename,'w') as ofile:
        ofile.writelines(lines)

class Subroutine(object):
    """
    Class object that holds relevant metadata on a subroutine
        * First, Given the name of the subroutine, the file is found
        * Call tree information is stored into self.calltree (must be analyzed at the end)
        * The Global variabes used in Associate clause are stored.
        * Dummy arguments are processed.
        * Rest of class elements are initialized.
    
    Note: Variables are stored using the Variable Class defined in utilityFunctions.py 
    Class Methods: 
        * printSubroutineInfo -> method to print to terminal subroutine metadata.
        * _get_dummy_args -> used to find keywords for subroutine arguments 
        * parse_subroutine -> Main function called and calls some class methods 
                              in order to collect all relevant metadata.
        * _check_acc_status -> checks if subroutine already as !$acc routine seq 
        * _get_global_constants -> Find global variables that are parameters (should it be a Class method?)
        * _preprocess_file -> (rename file?) Gets child subroutines
        * _analyze_variables -> loops through global vars, determines r/w status.
        * child_subroutines_analysis -> recursively analyzes child subs. Called after parse_subroutine
        * analyze_calltree -> unravel calltree list to generate proper/readable calltree to terminal or txt file.
        * generate_update_directives -> writes verificationMod subroutines
        * examineLoops -> Not part of primary Unit Test generation; enabled with opt flag.
                This collects all the metadata concerning the Loops of a subroutine (and child subroutines)
                Stores Loops in a Class defined in LoopConstructs.py 
                Once loop metadata is collected, OpenACC loop pragmas may be added.
                Data regions are inserted at the beginning and end of subroutines
                If adjust_allocation is enabled, then local variables are compressed as able.
        * exportReadWriteVariables -> writes formatted output for variable status
        * update_arg_tree -> maps dummy args to real args 
        * generate_unstructured_data_regions -> inserts OpenACC data regions for local variables 
    """
    from utilityFunctions import find_file_for_subroutine, getLocalVariables
    
    def __init__(self, name,file='',calltree=[],start=0,end=0,
                 cpp_start=None,cpp_end=None,cpp_fn=None,
                 ignore_interface=False,verbose=False, lib_func=False):
        """
        Initalizes the subroutine object:
            1) file for the subroutine is found if not given 
            2) calltree is assigned
            3) the associate clause is processed.
            5) 
        """
        
        self.name = name
        self.library = lib_func
        if(lib_func):
            print(f"Creating Subroutine {self.name} in {file} L{start}-{end}")
        # Find subroutine
        if(not ignore_interface):
            if( not file and start == 0 and end == 0):
                file, start, end = find_file_for_subroutine(name=name) 
                # grep isn't zero indexed so subtract 1 from start and end
                start -= 1 
                end -= 1

        self.filepath  = file
        self.startline = start
        self.endline   = end
        if(self.endline == 0 or self.startline == 0 or not self.filepath):
            print(f"Error in finding subroutine {self.name} {self.filepath} {self.startline} {self.endline}")
            sys.exit()
        self.cpp_filepath = cpp_fn

        # Initialize call tree
        self.calltree = list(calltree)
        self.calltree.append(name)

        # Process the Associate Clause 
        self.associate_vars = {}
        if(not lib_func):
            self.associate_vars, jstart, jend = getAssociateClauseVars(self)
            self.associate_start = jstart
            self.associate_end = jend
        
        # Initialize arguments and local variables 
        self.Arguments = {} # Order is important here 
        self.LocalVariables = {}
        self.LocalVariables['arrays'] = {} 
        self.LocalVariables['scalars'] = {}
        self.class_method = False
        self.class_type = None

        # Store when the arguments/local variable declarations start and end
        self.var_declaration_startl = 0
        self.var_declaration_endl = 0
        self.cpp_startline = cpp_start
        self.cpp_endline = cpp_end
        
        # Retrieve dummy arguments and parse variables
        if(not lib_func):
            self.dummy_args_list = self._get_dummy_args()
            getLocalVariables(self,verbose=verbose)

        self.elmtype_r = {}
        self.elmtype_w = {}
        self.elmtype_rw = {}
        self.subroutine_call = []
        self.child_Subroutine = {}
        
        self.acc_status = False
        self.elmtypes  = []
        self.DoLoops   = []
        self.status = False

    def printSubroutineInfo(self,long=False):
        """
        Prints the current subroutine metadata that has been collected.
        If `long` is True, then local scalar variables are printed as well.
        """
        tab = "  "
        print(_bc.OKCYAN+f"Subroutine {self.name} in {self.filepath} L{self.startline}-{self.endline}")
        print(f"{tab} Variable Declaration: L{self.var_declaration_startl}-{self.var_declaration_endl}")
        print(f"Has Arguments: ")
        for vname,arg in self.Arguments.items():
            if(arg.optional): 
                _str = "~"*len(tab)
            else:
                _str = tab
            print(_str+f"{arg.type} {arg.name} {arg.dim}-D {arg.subgrid} {arg.ln}")
        
        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
        # Print Other Modules needed to compile this subroutine # 
        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
        # print local variables      
        print(f"Local Arrays:")
        array_dict = self.LocalVariables['arrays']
        for arg in array_dict:
            var = array_dict[arg]
            print(f"{tab}{var.type} {var.name} {var.dim}-D {var.subgrid} {var.ln}")
        if(long):
            print(f"Local Scalars:")
            for arg in self.LocalVariables['scalars']:
                print(f"{tab}{arg.type} {arg.name} {arg.subgrid} {arg.ln}")
        
        # Print Child Subroutines
        if(self.child_Subroutine):
            print(f"Child Subroutines:")
            for s in self.child_Subroutine.values():
                print(f"{tab}{s.name}")
        print(_bc.ENDC)
        return None 

    def _get_dummy_args(self):
        """
        This function returns the arguments the subroutine takes
        for the s
        And then passes it to the getArguments function
        """
        from utilityFunctions import getArguments

        ifile = open(self.filepath,'r')
        lines = ifile.readlines()
        ifile.close() 
        
        ln = self.startline
        l = lines[ln].strip('\n')
        l = l.strip()

        while(l.endswith('&')):
            ln += 1 
            l = l[:-1] + lines[ln].strip('\n').strip()
        l = l.strip() 
        args = getArguments(l)
        return args


    def _get_global_constants(self,constants):
        """
        NOTE: Need to revisit this function
        This function will loop through an ELM F90 file,
        collecting all constants
        """
        const_mods = ['elm_varcon','elm_varpar',
                      'landunit_varcon','column_varcon','pftvarcon',
                      'elm_varctl']
        file = open(self.filepath,'r')
        lines = file.readlines()
        print(f"opened file {self.filepath}")
        ct = 0
        while (ct < len(lines)):
            line = lines[ct]
            l = line.strip()
            match_use = re.search(r'^use ',l.lower())
            if(match_use):
                l = l.replace(',',' ').replace(':', ' ').replace('only','').split()
                m = l[1]
                if(m in const_mods):
                    for c in l[2:]:
                        if c.lower() not in constants[m]: constants[m].append(c.lower())

            ct+=1
        print(constants)

    def _preprocess_file(self, main_sub_dict, dtype_dict,
                         interface_list, verbose=False):
        """
        This function will find child subroutines and variables used
        in the associate clause to be used for parsing for ro and wr derived types
        """
        from interfaces import resolve_interface
        from mod_config import _bc, regex_skip_string
        from utilityFunctions import getArguments 
        func_name = '_preprocess_file'
        
        # Note: no longer serves a purpose here
        self._check_acc_status()
        
        m_skip = regex_skip_string.search(self.name)
        
        if(self.cpp_filepath):
            fn = self.cpp_filepath
        else:
            fn = self.filepath
        
        file = open(fn,'r')
        lines = file.readlines()
        file.close()
        regex_ptr = re.compile(r'\w+\s*(=>)\s*\w+(%)\w+')
        # Set up dictionary of derived type instances
        global_vars = {} 
        for argname, arg in self.Arguments.items():
            if(arg.type in dtype_dict.keys()):
                global_vars[argname] = dtype_dict[arg.type]
        
        for typename, dtype in dtype_dict.items():
            for inst in dtype.instances:
                if(inst.name not in global_vars):
                    global_vars[inst.name] = dtype

        # Loop through subroutine and find any child subroutines
        if(self.cpp_startline):
            if(self.associate_end == 0):
                ct = self.cpp_startline
            else:
                # Note: currently don't differentiate between cpp files and regular files
                #       for location of the associate clause.
                ct = self.associate_end 
            endline = self.cpp_endline
        else:
            if(self.associate_end == 0):
                ct = self.startline
            else:
                ct = self.associate_end
            endline = self.endline 

        # Loop through the routine and find any child subroutines
        while(ct < endline):
            line = lines[ct]
            # get rid of comments
            line = line.split('!')[0].strip()
            if(not line): 
                ct+=1
                continue
            match_ptr = regex_ptr.search(line)
            if(match_ptr):
                print(f"{func_name}::Found pointer assignment at line {ct}\n{line}")
            match_call = re.search(r'^call ',line.strip())
            if(match_call) :
                x = line.strip().replace('(',' ').replace(')',' ').split()
                child_sub_name = x[1].lower()
                ignore = bool(child_sub_name in ['cpu_time','get_curr_date','t_start_lnd','t_stop_lnd','endrun'] 
                              or 'update_vars' in child_sub_name 
                              or "_oacc" in child_sub_name)
                if(ignore): 
                    ct += 1
                    continue 

                # Get the arguments passed to the subroutine
                l = lines[ct].strip('\n')
                l = l.strip()
                while(l.endswith('&')):
                    ct += 1
                    l = l[:-1] + lines[ct].strip('\n').strip()
                l = l.strip()

                # args is a list of arguments passed to subroutine
                args = getArguments(l)

                # If child sub name is an interface, then 
                # find the actual subroutine name corresponding
                # to the main subroutine dictionary
                if(child_sub_name in interface_list):
                    child_sub_name, childsub = resolve_interface(self,iname=child_sub_name,
                                                                args=args,dtype_dict=global_vars,
                                                                sub_dict=main_sub_dict,
                                                                verbose=verbose)
                    if(not child_sub_name): 
                        print(f"{func_name}::Error couldn't resolve interface for {x[1]}")
                        self.printSubroutineInfo()
                        sys.exit(1)
                    print(f"{func_name}::New child sub name is:", child_sub_name)
                elif('%' in child_sub_name):
                    # TODO: in DerivedType module, add logic to capture any `Alias` => 'function`
                    #       statements to more easily resolve class methods called with 
                    #       `call <var>%<alias>()` syntax.
                    print(_bc.WARNING
                        +f"{func_name}::WARNING CALLING CLASS METHOD at {self.name}:L{ct}!\n{l}"
                        +_bc.ENDC)
                    var_name, method_name = child_sub_name.split('%')
                    class_type = global_vars[var_name].type_name
                    for test_sub in main_sub_dict.values():
                        if(test_sub.class_type == class_type):
                            if(method_name in test_sub.name):
                                child_sub_name = test_sub
                                break
                    print(f"{func_name}::Class method is {child_sub_name}")
                else:
                    if(child_sub_name not in main_sub_dict):
                        print(_bc.WARNING+f"Warning: {child_sub_name} not in main_sub_dict."
                              +"\nCould be library function?"+_bc.ENDC)
                        childsub = Subroutine(name=child_sub_name,calltree=[],file='lib.F90', start=-999,
                                              end=-999, lib_func=True)
                    else:
                        childsub = main_sub_dict[child_sub_name]
                # Store the subroutine call information (name of parent and the arguments passed)
                subcall = SubroutineCall(self.name,args)
                if(subcall not in childsub.subroutine_call):
                    childsub.subroutine_call.append(subcall)
                # Add child subroutine to the dict if not already present              
                child_sub_names = [ s for s in self.child_Subroutine.keys() ]
                if(child_sub_name not in child_sub_names):
                    childsub.calltree = self.calltree.copy()
                    childsub.calltree.append(child_sub_name)
                    self.child_Subroutine[child_sub_name] = childsub
            ct+=1
        print(f"{func_name}::Finished analyzing for {self.name}")
        
        return None

    def _check_acc_status(self):
        """
        checks if subroutine already has !$acc directives
        """
        filename = self.filepath
        file = open(filename,'r')
        lines = file.readlines() # read entire file
        for ct in range(self.startline, self.endline):
            line = lines[ct]
            # checks for any !$acc directives
            match_acc = re.search(r'^[\s]+(\!\$acc)',line)
            if(match_acc): 
                self.acc_status = True; 
                return None 


    def _analyze_variables(self,dtype_dict,verbose=False):
        """
        Function used to determine read and write variables
        If var is written to first, then rest of use is ignored.
        Vars determined to be read are read-in from a file generated by
            full E3SM run called {unit-test}_vars.txt by default.

        Vars that are written to must be checked to verify
        results of unit-testing.

        !!
        REWRITE NOTES:
            - Part 1, check rw status of any derived types
            - Part 2, check rw status of associated derived types
                    self.associate_vars is a dictionary { ptrname : variable}
            - Part 3, check rw status of global vars (not derived types?)
        """
        func_name = "_analyze_variables"
        
        if(self.cpp_filepath):
            fn = self.cpp_filepath
        else:
            fn = self.filepath
        
        file = open(fn,'r')
        lines = file.readlines()
        file.close()
        if(self.associate_end == 0):
            if(self.cpp_startline):
                startline = self.cpp_startline
            else:
                startline = self.startline 
        else:
            startline = self.associate_end
        
        if(self.cpp_endline):
            endline = self.cpp_endline
        else:
            endline = self.endline
        # Create regex to match any variable in the associate clause:
        if(not self.associate_vars):
            no_associate = True
        else:
            # associate_vars is a dictionary { ptrname : variable}
            no_associate = False
            ptrname_list = [key for key in self.associate_vars.keys()]
            ptrname_str = '|'.join(ptrname_list)
            regex_associated_ptr = re.compile(f'({ptrname_str})',re.IGNORECASE) 

        # character class for regex needed to ignore '%'
        c = '[^a-zA-Z0-9_%]'  

        # Note: unneccessary?
        dtype_instance_dict = {}
        for dtype in dtype_dict.values():
            for inst in dtype.instances:
                dtype_instance_dict[inst.name] = dtype
        
        # dictonary to keep track of any derived types accessed
        # in the subroutine. 
        # {'inst%component : [ReadWrite] }
        #  where ReadWrite = namedtuple('ReadWrite',['status','ln'])
        dtype_accessed = {} 

        # Loop through subroutine line by line starting after the associate clause
        ct = startline
        while (ct < endline):

            # Take into account Fortran line continuations
            line, ct = line_unwrapper(lines,ct)
            line = line.strip().lower()
            
            # match subroutine call 
            match_call = re.search(r'^\s*(call) ',line)
            match_var = None 
            if(not match_call):
                # Get list of all global variables used in this line
                match_var = re.findall(r"\w+%\w+",line) 
                # There are derived types to analyze!
                if(match_var):
                    match_var = list(set(match_var))
                    dtype_accessed = determine_variable_status(match_var, line, ct, 
                                                               dtype_accessed,verbose=True)
                # Do the same for any variables in the associate clause
                if(not no_associate): 
                    match_ptrs = regex_associated_ptr.findall(line)
                    if(match_ptrs):
                        dtype_accessed = determine_variable_status(match_ptrs, line, 
                                                                   ct, dtype_accessed)
            ct += 1
        
        # Sort the variables based on complete read/write status
        # So ignoring line numbers 
        for key, values in dtype_accessed.items():
            # read-only: all values are 'r'
            # write-only: all values are 'w'
            # read-write: mixture of 'r' and 'w'
            status_list = [v.status for v in values]
            num_uses = len(status_list)
            num_reads = status_list.count('r')
            num_writes = status_list.count('w')
            if(not no_associate):
                if(key in ptrname_list):
                    varname = self.associate_vars[key]
                else:
                    varname = key
            else:
                varname = key
            if(num_uses == num_reads):
                # read-only
                self.elmtype_r[varname] = 'r'
            elif(num_uses == num_writes):
                # write-only
                self.elmtype_w[varname] = 'w'
            else:
                # read-write
                self.elmtype_rw[varname] = 'rw'
        
        return None 

    def parse_subroutine(self,dtype_dict,main_sub_dict,child=False,verbose=False):
        """
        This function parses subroutine to find which variables are ro,wo,rw
        elmvars is a list of DerivedType.
        This function is called in main() after process_for_unit_test
        currently varlist holds all derived types known to be used in ELM.
            self : subroutine object 
            dtype_dict : dictionary of derived types
            main_sub_dict : dictionary of all subroutines in files needed for unit testing
            child : boolean flag to indicate if subroutine is a child subroutine
        """
        # Get interfaces 
        interface_list = get_interface_list()
        elmvar = [dtype for dtype in dtype_dict.values()]
        
        # preprocess file so to get child subroutines
        self._preprocess_file(main_sub_dict=main_sub_dict,
                              dtype_dict=dtype_dict,
                              interface_list=interface_list,verbose=verbose)
        
        # Create list that holds the names of the derived types only
        elm_var_names = [] 
        for dtype in elmvar:
            for inst in dtype.instances:
                elm_var_names.append(inst.name)

        # If the subroutine has been called, then extra care must be taken
        # for any global variables passed as arguments to match the names
        # of dummy args to their actual name.
        if(child):
            for scall in self.subroutine_call:
                # Match the args to the variables.
                parent_sub = main_sub_dict[scall.subname]
                varg_dict = {} # variable instance of args
                for arg in scall.args:
                    if(arg in parent_sub.associate_vars.keys()):
                        varg_dict[arg] = parent_sub.associate_vars[arg]
                    elif(arg in parent_sub.Arguments.keys()):
                        varg_dict[arg] = parent_sub.Arguments[arg]
                    elif(arg in parent_sub.LocalVariables['arrays'].keys()):
                        varg_dict[arg] = parent_sub.LocalVariables['arrays'][arg]
                    elif(arg in parent_sub.LocalVariables['scalars']):
                        varg_dict[arg] = parent_sub.LocalVariables['scalars'][arg]
                
        # Determine read/write status of variables
        self._analyze_variables(dtype_dict=dtype_dict, verbose=verbose)
        # Update main_sub_dict with new parsing information?    
        main_sub_dict[self.name] = self 

        return None
            
    def child_subroutines_analysis(self,dtype_dict,main_sub_dict,verbose=False):
        """
        This function handles parsing child_subroutines and merging
        variable dictionaries
            self : parent subroutine 
            dtype_dict : dictionary of derived types
            main_sub_dict : dictionary of all subroutines in files needed for unit testing
        """
        interface_list = get_interface_list()
        func_name = "child_subroutines_analysis"

        # child_subroutine_list is a list of Subroutine instances 
        for child_sub in self.child_Subroutine.values():
            if(child_sub.library):
                print(f"{func_name}:: {child_sub.name} is a library function -- Skipping.")
                continue
            print("Analyzing child subroutine:",child_sub.name)
            if(child_sub.name in interface_list):
                print(f"{func_name}::Error: need to resolve interface for {child_sub.name}")
                sys.exit(1)

            child_sub.parse_subroutine(dtype_dict=dtype_dict,
                                    main_sub_dict=main_sub_dict,
                                    child=True,verbose=verbose)
            
            if(child_sub.child_Subroutine):
                if("_oacc" not in child_sub.name): 
                    child_sub.child_subroutines_analysis(dtype_dict=dtype_dict,
                                        main_sub_dict=main_sub_dict,verbose=verbose)
            
            # Add needed elmtypes to parent subroutine
            for varname, status in child_sub.elmtype_r.items():
                if(varname in self.elmtype_w.keys()):
                    # Check if previously write-only and change to read-write
                    self.elmtype_rw[varname] = 'rw'
                    self.elmtype_w.pop(varname) 
                elif(varname in self.elmtype_rw.keys()):
                    # No action needed, just continue
                    continue 
                elif(varname not in self.elmtype_r.keys()):
                    # Check if variable is present in parent at all and add if needed
                    self.elmtype_r[varname] = 'r'

            for varname, status in child_sub.elmtype_w.items():
                if(varname in self.elmtype_r.keys()):
                    self.elmtype_rw[varname] = 'rw'
                    self.elmtype_w.pop(varname) # remove from read-only
                elif(varname in self.elmtype_rw.keys()):
                    continue
                elif(varname not in self.elmtype_w.keys()):
                    self.elmtype_w[varname] = 'w'
            
            for varname in child_sub.elmtype_rw.keys():
                if(varname not in self.elmtype_rw.keys()):
                    self.elmtype_rw[varname] = 'rw'
                if(varname in self.elmtype_r.keys()):
                    self.elmtype_r.pop(varname)
                if(varname in self.elmtype_w.keys()):
                    self.elmtype_w.pop(varname) 

        for s in self.child_Subroutine.values():
            self.calltree.append(s.calltree)
            if(child_sub in interface_list): 
                continue
        self.status = True

        return None 

    def analyze_calltree(self,tree,casename):
        """
        returns unraveled calltree
        """
        tree_to_write = [[self.name,0]]
        for i in range(0,len(tree)):
            el = tree[i]
            tree_to_write = determine_level_in_tree(branch=el,tree_to_write=tree_to_write)

        ofile = open(f"{casename}/{self.name}CallTree.txt",'w')
        for branch in tree_to_write:
            level=branch[1];sub = branch[0]
            print(level*"|---->"+sub)
            ofile.write(level*"|---->"+sub+'\n')
        ofile.close()

    def generate_update_directives(self, elmvars_dict,verify_vars):
        """
        This function will create .F90 routine to execute the
        update directives to check the results of the subroutine
        """
        ofile = open(f"{home_dir}scripts/script-output/update_vars_{self.name}.F90",'w')

        spaces =" "*2
        ofile.write("subroutine update_vars_{}(gpu,desc)\n".format(self.name))

        replace_inst = ['soilstate_inst','waterflux_inst','canopystate_inst','atm2lnd_inst','surfalb_inst',
                        'solarabs_inst','photosyns_inst','soilhydrology_inst','urbanparams_inst']

        for dtype in verify_vars.keys():
            mod = elmvars_dict[dtype].declaration
            ofile.write(spaces + f"use {mod}, only : {dtype}\n")

        ofile.write(spaces+"implicit none\n")
        ofile.write(spaces+"integer, intent(in) :: gpu\n")
        ofile.write(spaces+"character(len=*), optional, intent(in) :: desc\n")
        ofile.write(spaces+"character(len=256) :: fn\n")
        ofile.write(spaces+"if(gpu) then\n")
        ofile.write(spaces+spaces+f'fn="gpu_{self.name}"\n')
        ofile.write(spaces+"else\n")
        ofile.write(spaces+spaces+f"fn='cpu_{self.name}'\n")
        ofile.write(spaces+'end if\n')
        ofile.write(spaces+"if(present(desc)) then\n")
        ofile.write(spaces+spaces+"fn = trim(fn) // desc\n")
        ofile.write(spaces+"end if\n")
        ofile.write(spaces+'fn = trim(fn) // ".txt"\n')
        ofile.write(spaces+'print *, "Verfication File is :",fn\n')
        ofile.write(spaces+"open(UNIT=10, STATUS='REPLACE', FILE=fn)\n")
        
        # First insert OpenACC update directives to transfer results from GPU-CPU
        ofile.write(spaces+"if(gpu) then\n")
        acc = "!$acc "

        for v,comp_list in verify_vars.items():
            ofile.write(spaces+acc+"update self(&\n")
            i = 0
            for c in comp_list:
                i +=1
                if i == len(comp_list) :
                    name = f"{v}%{c}"
                    c13c14 = bool('c13' in name or 'c14' in name)
                    if(c13c14):
                        ofile.write(spaces+acc+")\n")
                    else:
                        ofile.write(spaces+acc+f"{name} )\n")
                else:
                    name = f"{v}%{c}"
                    c13c14 = bool('c13' in name or 'c14' in name)
                    if(c13c14): 
                        continue
                    ofile.write(spaces+acc+f"{name}, &\n")

        ofile.write(spaces+"end if\n")
        ofile.write(spaces+"!! CPU print statements !!\n")
        # generate cpu print statements
        for v,comp_list in verify_vars.items():
            for c in comp_list:
                name = f"{v}%{c}"
                c13c14 = bool('c13' in name or 'c14' in name)
                if(c13c14):
                    continue
                ofile.write(spaces+f"write(10,*) '{name}',shape({name})\n")
                ofile.write(spaces+f"write(10,*) {name}\n")

        ofile.write(spaces+"close(10)\n")
        ofile.write("end subroutine ")
        ofile.close()
        return 
     
    def examineLoops(self,global_vars,varlist,main_sub_dict,add_acc=False,subcall=False,
                        verbose=False,adjust_allocation=False):
        """
        Function that will parse the loop structure of a subroutine
        Add loop parallel directives if desired
        """
        from interfaces import resolve_interface
        from mod_config import _bc
        from utilityFunctions import (determine_filter_access,
                                      find_file_for_subroutine,
                                      get_interface_list, getArguments,
                                      getLocalVariables,
                                      lineContinuationAdjustment)

        interface_list = get_interface_list() # move this to a global variable in mod_config?
        if(not subcall):
            associate_keys = self.associate_vars.keys()
            temp_global_vars = [key for key in associate_keys]
            global_vars = temp_global_vars[:]
        else: 
            if(self.name not in main_sub_dict): 
                main_sub_dict[self.name] = self
        
        # Check if associated derived types need to be analyzed 
        # convertAssociateDict(self.associate_vars,varlist)

        if(adjust_allocation): 
            # dict with 'arg' : Subroutine
            # where 'arg' is a local array, and 'sub' is child subroutine that uses it.
            passed_to_sub = {} 
            local_array_list = [v for v in self.LocalVariables['arrays']]
            print(f"local_array for {self.name}\n",local_array_list)

        if(verbose): print(f"Opening file {self.filepath} ")
        ifile = open(self.filepath,'r')
        lines = ifile.readlines() # read entire file
        ifile.close()
        
        loop_start = 0 
        loop_end = 0
        regex_do = re.compile(r'\s*(do)\s+\w+\s*(?=[=])',re.IGNORECASE)
        regex_dowhile = re.compile(f'\s*(do while)',re.IGNORECASE)
        regex_enddo = re.compile(r'^\s*(end)\s*(do)',re.IGNORECASE)
        regex_subcall = re.compile(r'^(call)',re.IGNORECASE)

        # Starting parsing lines at the subroutine start
        sublines = lines[self.startline-1:self.endline]
        loopcount = 0
        print(f"Examing Loops for {self.name}")
        dowhile = False 
        lines_to_skip = 0 
        for n,line in enumerate(sublines):
            if(lines_to_skip > 0):
               lines_to_skip -= 1 
               continue 
            l, lines_to_skip = lineContinuationAdjustment(sublines,n,verbose)
            
            # Use RegEx
            m_call = regex_subcall.search(l)
            m_do = regex_do.search(l)
            m_enddo = regex_enddo.search(l)
            m_dowhile = regex_dowhile.search(l)
            if(m_dowhile): 
                dowhile = True  # Inside do while loop 
                if(verbose): print("Inside do while loop")
            # If we match subroutine call we should analyze it now so that the 
            # DoLoops array has the Loops in order of use. 
            #
            if(m_call):
                x = l.replace('(',' ').replace(')',' ').split()
                child_sub_name = ''
                ignore_subs = ['cpu_time','get_curr_date','endrun','banddiagonal']
                if(x[1].lower() not in ignore_subs and 'update_vars' not in x[1].lower() and "_oacc" not in x[1].lower()):
                    child_sub_name = x[1]

                    args = getArguments(l)
                    
                    if(child_sub_name in interface_list):
                        print("Need to resolve interface!",child_sub_name)
                        sys.exit()
                        child_sub_name, childsub = resolve_interface(self,child_sub_name,args,
                                                                     varlist,verbose=verbose)
                    else:
                        file,startline,endline = find_file_for_subroutine(child_sub_name)
                        childsub = Subroutine(child_sub_name,file,[self.name],startline,endline)

                    # Note that these subroutines have specific versions for 
                    # using filter or not using a filter. 
                    dont_adjust = ['c2g','p2c','p2g','p2c','c2l','l2g','tridiagonal']
                    dont_adjust_string = '|'.join(dont_adjust)
                    regex_skip_string = re.compile(f"({dont_adjust_string})",re.IGNORECASE) 
                    m_skip = regex_skip_string.search(child_sub_name)

                    if(not m_skip): 
                        self.update_arg_tree(child_sub_name,args) 

                    getLocalVariables(childsub,verbose=verbose)
                    
                    if(adjust_allocation):
                        # To adjust memory allocation, need to keep track
                        # of if a Local variable is passed as an argument.
                        # If it's a subcall then must check the arguments as well.
                        for numarg,arg in enumerate(args):
                            if(arg in local_array_list):
                                passed_to_sub[arg] = [childsub,n+self.startline-1,numarg]
                                
                        if(subcall): # check if an argument is passed to another subroutine
                            arg_list = [v for v in self.Arguments]
                            for arg in args:
                                if(arg in arg_list):
                                    print(f"{arg} passed to {child_sub_name}")
                    #
                    # get global variable aliases 
                    # 
                    associate_keys = childsub.associate_vars.keys()
                    temp_global_vars = [key for key in associate_keys]
                    global_vars.extend(temp_global_vars)
                    global_vars = list(dict.fromkeys(global_vars).keys())
                    #
                    # Examine Do loops in child subs
                    #
                    if(verbose): 
                        print(f"Instantiated new Subroutine {child_sub_name}\n in file {file} L{startline}-{endline}")
                    
                    childloops = childsub.examineLoops(global_vars=global_vars,varlist=varlist,
                            main_sub_dict=main_sub_dict,subcall=True,
                            verbose=verbose,adjust_allocation=adjust_allocation,add_acc=False)
                    if(verbose): 
                        print(f"Adding {len(childloops)} loops from {childsub.name}")
                    self.DoLoops.extend(childloops)
                    self.child_subroutine_list.append(childsub)
                    self.child_Subroutine[child_sub_name] = childsub

            if(m_do): 
                #get index 
                index = m_do.group().split()[1]
                #outer most loop
                if(loopcount == 0):
                    if(verbose): print(f"============ {self.name} ===============")
                    if(verbose): print("New loop at line ",n+self.startline)
                    loop_start = n+self.startline
                    newloop = Loop(loop_start,index,self.filepath,self)
                else :
                    #Found an inner loop
                    newloop.index.append(index)
                    loop_start = n+self.startline; newloop.nested += 1
                    newloop.start.append(loop_start)
                    newloop.end.append(0)
                loopcount += 1
            
            if(m_enddo): 
                if(dowhile): 
                    dowhile = False
                    if(verbose): 
                        print(_bc.WARNING + f"Do while loop in {self.name} ends at {n+self.startline}"+_bc.ENDC) 
                    continue 
                loopcount -= 1
                if(loopcount == 0) :
                    if(verbose): print("end of outer loop at ",n+self.startline)
                    loop_end = n+self.startline
                    # append loop object:
                    newloop.end[loopcount] = loop_end
                    lstart = newloop.start[0] - self.startline 
                    lend = loop_end - self.startline
                    
                    newloop.lines = sublines[lstart:lend+1]
                    self.DoLoops.append(newloop)
                else:
                    loop_end = n+self.endline
                    newloop.end[loopcount] = loop_end 
        
        # Parse variables used in Loop
        print(f"Parsing variables for Loops in {self.name}")
        for n, loop in enumerate(self.DoLoops):
            if(loop.subcall.name is self.name):
                # loops in child subroutines have already been Parsed!
                loop.parseVariablesinLoop(verbose=verbose)
                if(loop.reduction): 
                    print("loop may contain a race condition:",loop.reduce_vars)

        if(adjust_allocation):
            determine_filter_access(self,verbose=False)
            # Check and fix !$acc enter/exit data directives for the subroutine
            self.generate_unstructured_data_regions()

        if(subcall):
            return self.DoLoops
        
        # Create dictionary to hold subroutines found so far 
        # and their initial startlines to help adjust for line insertions later.
        sub_dict = {}
        # dictionary of the loops to avoid adding OpenACC directives to the same 
        # Loop more than once 
        loop_dict = {} 
        num_reduction_loops = 0 
        ofile = open(f"loops-{self.name}.txt",'w')
        for loop in self.DoLoops: 
            loopkey = f"{loop.subcall.name}:L{loop.start[0]}"
            if(loopkey not in loop_dict):
                loop_dict[loopkey] = loop
                if(loop.reduction):
                    print(_bc.BOLD+_bc.WARNING+f"{loopkey} {loop.reduce_vars}"+ _bc.ENDC)
                    ofile.write(f"{loopkey} {loop.reduce_vars}"+"\n")
                    num_reduction_loops += 1 
                else:
                    print(loopkey)
                    ofile.write(loopkey+'\n')
            if(loop.subcall.name not in sub_dict):
                file,startline,endline = find_file_for_subroutine(loop.subcall.name)
                sub_dict[loop.subcall.name] = startline
        loopids = [k for k in loop_dict.keys()]
        print(_bc.OKGREEN+ f"{len(loopids)} | {num_reduction_loops} w/ Race Conditions"+_bc.ENDC)            
        ofile.write( f"{len(loopids)} | {num_reduction_loops} w/ Race Conditions"+"\n")

        ofile.close()
        count = 0
        for s in main_sub_dict.values(): 
            arrs = s.LocalVariables['arrays']
            for arr in arrs:
                v = arrs[arr] 
                if("num_" in v.declaration):
                    count += 1 
                    print(f"{count}  {s.name}::{v.name} -- {v.declaration}")
        if(add_acc): 
            lines_adjusted = {}
            for key, loop in loop_dict.items(): 
                if(loop.subcall.name not in lines_adjusted):
                    # This keeps track of the number of line adjustments
                    # inside a given subroutine.  The start of the subroutine 
                    # is rechecked inside addOpenACCFlags function
                    lines_adjusted[loop.subcall.name] = 0
                file,startline,endline = find_file_for_subroutine(loop.subcall.name)
                subline_adjust = startline - sub_dict[loop.subcall.name]
                loop.addOpenACCFlags(lines_adjusted,subline_adjust,key)

        #Note: Can't use List Comprehension here with class attributes
        var_list = []
        local_vars_only = []
        for loop in self.DoLoops:
            for key in loop.vars.keys():
                var_list.append(key) 
                if(key not in global_vars):
                    local_vars_only.append(key)

        var_list = list(dict.fromkeys(var_list).keys())
        local_vars_only = list(dict.fromkeys(local_vars_only).keys())


        # print only the global variable list:
        global_loop_vars = [] 
        all_array_vars = []
        for v in var_list:
            if(v in global_vars or "filter" in v):
                global_loop_vars.append(v)
        
        exportVariableDependency(self.name,var_list,global_loop_vars,local_vars_only,self.DoLoops,mode='')

        return None 

    def exportReadWriteVariables(self):
        """
        Writes the variables for read and write to a separate data file
        """
        spaces = "     "
        read_flat = [] 
        write_flat = []
        all_flat = [] 
        maxlen = 0
        #read variables
        print("============= exportReadWriteVariables ===================") 
        print(self.elmtype_r)
        for varname, components in self.elmtype_r.items():
            for c in components:
                var = f"{varname}%{c}"
                read_flat.append(var)
                all_flat.append(var)
                if(len(var) > maxlen): maxlen = len(var)

        for varname, components in self.elmtype_w.items():
            for c in components:
                var = f"{varname}%{c}"
                write_flat.append(var)
                if(len(var) > maxlen): maxlen = len(var)
                if(var not in all_flat): all_flat.append(var)
                
        
        output_list = [] 
        #header 
        ofile = open(f"{self.name}-ReadWriteVars.dat",'w')
        header = f"{'Variable':<{maxlen}} {'Status':5}"
        output_list.append(header)
        ofile.write(header+"\n")
        for var in all_flat:
            status = ''
            if(var in read_flat):
                status += 'r'
            if(var in write_flat):
                status +='w'
            if(len(status)<2): status +='o'
            string = f"{var:<{maxlen}} {status:5}\n"
            ofile.write(string)
        ofile.close()             

        return  None 
    
    def update_arg_tree(self,childsubname,args):
        """
        Checks if any of the subroutines arguments 
        or local variables are passed to any subroutines.
        """
        from mod_config import _bc 
        
        print(_bc.HEADER)
        print(f"update_arg_tree::{self.name} called {childsubname} w/ args {args}")
        print(_bc.ENDC)
        # self.printSubroutineInfo(long=True)

        arrays = self.LocalVariables['arrays']

        for v in args:
            if("=" in v):
                kw, var = v.split("=")
                kw = kw.strip() 
                var = var.strip()
                if(var not in arrays): continue
                self.LocalVariables['arrays'][var].keyword = kw
                self.LocalVariables['arrays'][var].subs.append(childsubname)
                self.VariablesPassedToSubs.setdefault(childsubname,[]).append(self.LocalVariables['arrays'][var])
            else:
                var = v.strip()
                if(var not in arrays): continue
                self.LocalVariables['arrays'][var].keyword = ''
                self.LocalVariables['arrays'][var].subs.append(childsubname)
                self.VariablesPassedToSubs.setdefault(childsubname,[]).append(self.LocalVariables['arrays'][var])
    
    def generate_unstructured_data_regions(self, remove=True): 
        """
        Function generates appropriate enter and exit data
        directives for the local variables of this Subroutine.

        First step is to remove any existing directives
        Next, create new directives from local variable list
        Compare new and old directives and overwrite if they are different
        """
        # Open File:
        if(os.path.exists(home_dir+"modified-files/"+self.filepath)):
            print("Modified file found")
            print(_bc.BOLD+_bc.WARNING+f"Opening file "+home_dir+"modified-files/"+self.filepath+_bc.ENDC)
            ifile = open(home_dir+"modified-files/"+self.filepath,'r')
        else:
            print(_bc.BOLD+_bc.WARNING+f"Opening file{self.filepath}"+_bc.ENDC)
            ifile = open(self.filepath,'r')
        
        lines = ifile.readlines() 

        ifile.close() 

        regex_enter_data = re.compile(r'^\s*\!\$acc enter data', re.IGNORECASE)
        regex_exit_data = re.compile(r'^\s*\!\$acc exit data', re.IGNORECASE)
        
        lstart = self.startline - 1
        lend = self.endline 
        old_enter_directives = []
        old_exit_directives = []
        if(remove): 
            ln = lstart 
            while(ln < lend):
                line = lines[ln]
                match_enter_data = regex_enter_data.search(line)
                match_exit_data  = regex_exit_data.search(line)
                if(match_enter_data):
                    directive_start = ln 
                    old_enter_directives.append(line) # start of enter data directive
                    line = line.rstrip('\n')
                    line = line.strip()
                    while(line.endswith('&')):
                        ln += 1 
                        line = lines[ln]
                        old_enter_directives.append(line) # end of enter data directive
                        line = line.rstrip('\n')
                        line = line.strip()
                    directive_end = ln
                    del(lines[directive_start:directive_end+1])
                    num_lines_removed = directive_end - directive_start + 1
                    lend -= num_lines_removed
                    ln -= num_lines_removed
                    print(f"Removed {num_lines_removed} enter data lines")
                if(match_exit_data):
                    directive_start = ln  # start of exit data directive 
                    old_exit_directives.append(line)
                    line = line.rstrip('\n')
                    line = line.strip()
                    while(line.endswith('&')):
                        ln += 1 
                        line = lines[ln]
                        old_exit_directives.append(line)
                        line = line.rstrip('\n')
                        line = line.strip()
                    directive_end = ln # end of exit data directive
                    del(lines[directive_start:directive_end+1])
                    num_lines_removed = directive_end - directive_start + 1
                    lend -= num_lines_removed
                    ln -= num_lines_removed
                    print(f"Removed {num_lines_removed} exit data lines")
                ln += 1
        
        # Create New directives
        vars = [] # list to hold all vars needed to be on the device
        arrays_dict = self.LocalVariables['arrays']
        for k,v in arrays_dict.items():
            varname = v.name 
            dim = v.dim 
            li_ = [":"]*dim
            dim_str = ",".join(li_)
            dim_str = "("+dim_str+")"
            print(f"adding {varname}{dim_str} to directives")
            vars.append(f"{varname}{dim_str}")

        # Only add scalars to if they are a reduction variables
        # Only denoting that by if it has "sum" in the name
        for v in self.LocalVariables['scalars']:
            varname = v.name
            for loop in self.DoLoops:
                if(loop.subcall.name == self.name):
                    if(varname in loop.reduce_vars and varname not in vars):
                        print(f"Adding scalar {varname} to directives")
                        vars.append(varname)

        num_vars = len(vars)
        if(num_vars == 0):
            print(f"No Local variables to make transfer to device, returning")
            return None
        else:
            print(f"Generating create directives for {num_vars} variables")

        # Get appropriate indentation for the new directives:
        padding = ""
        first_line = 0

        for ln in range(lstart,lend):
            line = lines[ln]
            # Before ignoring comments, check if it's an OpenACC directive
            m_acc = re.search(r"\s*(\!\$acc routine seq)",line)
            if(m_acc):
                sys.exit("Error: Trying to add data directives to an OpenACC routine")
            
            m_acc = re.search(r"\s*(\!\$acc)\s+(parallel|enter|update)",line,re.IGNORECASE)
            if(m_acc and first_line == 0):
                first_line = ln
            
            l = line.split("!")[0]
            l = l.strip()
            if(not l): continue

            m_use = re.search(r'^(implicit|use|integer|real|character|logical|type\()',line.lstrip())
            if(m_use and not padding):
                padding = " "*(len(line) - len(line.lstrip()))
            elif(padding and not m_use and first_line == 0):
                first_line = ln
            
            if(ln == lend-1 and not padding): 
                sys.exit("Error: Couldn't get spacing")

        new_directives = [] 
        
        for v in vars[0:num_vars-1]:
            new_directives.append(padding+f"!$acc {v}, &\n")
        new_directives.append(padding+f"!$acc {vars[num_vars-1]})\n\n")
        
        new_enter_data = [padding+"!$acc enter data create(&\n"]
        new_enter_data.extend(new_directives)
        #
        new_exit_data = [padding+"!$acc exit data delete(&\n"]
        new_exit_data.extend(new_directives)

        if(new_enter_data != old_enter_directives or new_exit_data != old_exit_directives):
            # Insert the enter data directives
            if(self.associate_end != 0):
                # insert new directives just after last associate statement: 
                for l in reversed(new_enter_data):
                    lines.insert(self.associate_end+1,l)
            else: # use first_line found above 
                for l in reversed(new_enter_data):
                    lines.insert(first_line,l)
            lend += len(new_enter_data)
            print(_bc.BOLD+_bc.WARNING+f"New Subroutine Ending is {lend}"+_bc.ENDC)
            # Inster the exit data directives
            if(self.associate_end !=0):
                end_associate_ln = 0
                regex_end = re.compile(r'^(end associate)',re.IGNORECASE)
                for ln in range(lend,lstart,-1):
                    m_end = regex_end.search(lines[ln].lstrip())
                    if(m_end):
                        end_associate_ln = ln
                        break
                for l in reversed(new_exit_data):
                    lines.insert(end_associate_ln,l)
            else:
                for l in reversed(new_exit_data):
                    lines.insert(lend-1,l)
            lend += len(new_exit_data)
            print(_bc.BOLD+_bc.WARNING+f"New Subroutine Ending is {lend}"+_bc.ENDC)

            # Overwrite File:
            if("modified-files" in self.filepath):
                print(_bc.BOLD+_bc.WARNING+f"Writing to file {self.filepath}"+_bc.ENDC)
                ofile = open(self.filepath,'w')
            else:
                print(_bc.BOLD+_bc.WARNING+f"Writing to file "+home_dir+"modified-files/"+self.filepath+_bc.ENDC)
                ofile = open(home_dir+"modified-files/"+self.filepath,'w')

            ofile.writelines(lines)
            ofile.close() 
        else:
            print(_bc.BOLD+_bc.WARNING+"NO CHANGE"+_bc.ENDC)
            
