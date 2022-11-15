from array import array
import re
import sys
import os.path
from process_associate import getAssociateClauseVars
from mod_config import elm_files,home_dir,_bc
from LoopConstructs import Loop, exportVariableDependency
from utilityFunctions import adjust_array_access_and_allocation, find_file_for_subroutine,getLocalVariables

def debug_print(str_debug, verbose):
    if (verbose <= DEBUG_PRINT_VERBOSE):
        print(str_debug)

def error_print(str_error, verbose):
    if (verbose <= DEBUG_PRINT_VERBOSE):
        print(str_error)

def test_bit(int_type, offset):
    mask = 1 << offset
    return(int_type & mask)

def replace_key(key):

    if(key == 'vegcf'):
        return 'veg_cf'
    elif(key == 'colcf'):
        return 'col_cf'
    elif(key == 'colcs'):
        return 'col_cs'
    elif(key == 'vegcs'):
        return 'veg_cs'
    elif(key == 'vegpf'):
        return 'veg_pf'
    elif(key == 'colpf'):
        return 'col_pf'
    elif(key == 'colps'):
        return 'col_ps'
    elif(key == 'vegps'):
        return 'veg_ps'
    elif(key == 'vegnf'):
        return 'veg_nf'
    elif(key == 'colnf'):
        return 'col_nf'
    elif(key == 'colns'):
        return 'col_ns'
    elif(key == 'vegns'):
        return 'veg_ns'
    else:
        return key    
    

def determine_level_in_tree(branch,tree_to_write):
    """
    will be called recursively
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

    file = open(elm_files+filename,'r')
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
    lines.insert(first_use,'      !$acc routine seq \n')
    print(f"Added !$acc to {sub.name} in {filename}")
    with open(elm_files+filename,'w') as ofile:
        ofile.writelines(lines)

class Subroutine(object):
    def __init__(self, name,file='',calltree=[],start=0,end=0,ignore_interface=False):
        self.name = name
        
        # find subroutine
        if(not ignore_interface):
            file, start, end = find_file_for_subroutine(name)

        self.filepath = file
        self.startline = start
        self.endline = end
        if(self.endline == 0 or self.startline == 0 or not self.filepath):
            print(f"Error in finding subroutine {self.name} {self.filepath} {self.startline} {self.endline}")
            sys.exit()
        
        if(os.path.exists(home_dir+f"modified-files/{file}")):
            # print(file,"has already been modified -- setting new filepath")
            self.filepath = f"../modified-files/{file}"
            # Have to get subroutine start and endline just in case it's different:
            f, self.startline, self.endline = find_file_for_subroutine(name,fn=self.filepath)
        
        self.calltree = list(calltree)
        self.calltree.append(name)
        print(f"CallTree for {self.name} is {self.calltree}")
        self.associate_vars = {}

        # Get associate vars 
        self.associate_vars, self.status, jstart,jend = getAssociateClauseVars(self)
        self.associate_start = jstart; self.associate_end = jend
        
        self.dummy_args_list = self._get_dummy_args()

        self.subroutine_init = None
        self.elmtype_r = {}
        self.elmtype_w = {}
        self.elmtype_rw = {}
        self.child_subroutine_list = []
        self.child_Subroutine = {}
        self.acc_status = False

        self.elmtypes = []
        self.DoLoops = []
        self.Arguments = {} # Order is important here 
        self.LocalVariables = {}
        self.LocalVariables['arrays'] = {}; self.LocalVariables['scalars'] = []
        self.VariablesPassedToSubs = {} # {'var' : [Subroutine, 'keyword', Variable?]} maybe extend Variable class to an Argument class?
        self.status = False

    def printSubroutineInfo(self,long=False):
        from mod_config import _bc

        print(_bc.OKCYAN+f"Subroutine {self.name} in {self.filepath} L{self.startline}-{self.endline}")
        print(f"Has Arguments: ")
        for vname,arg in self.Arguments.items():
            if(arg.optional): 
                _str = "OPTIONAL "
            else:
                _str = ""
            print(_str+f"{arg.type} {arg.name} {arg.dim}-D {arg.subgrid} {arg.ln}")
        print(f"+++++ Local Variables ++++++")
        print(f"+++++++++ Arrays  ++++++++++")
        array_dict = self.LocalVariables['arrays']
        for arg in array_dict:
            var = array_dict[arg]
            print(f"{var.type} {var.name} {var.dim}-D {var.subgrid} {var.ln}")
        if(long):
            print(f"+++++++++ Scalars ++++++++++")
            for arg in self.LocalVariables['scalars']:
                print(f"{arg.type} {arg.name} {arg.subgrid} {arg.ln}")
        print("+++++++++++++++++++++++++++++")
        print(f"+++++ Child Subroutines +++++")
        for s in self.child_subroutine_list:
            print(f"{s.name}")
        print("+++++++++++++++++++++++++++++"+_bc.ENDC)

    def _get_dummy_args(self):
        """
        This function gets the full dummy args list 
        for the subroutine.
        """
        from utilityFunctions import getArguments

        ifile = open(elm_files+self.filepath,'r')
        lines = ifile.readlines()
        ifile.close() 
        ln = self.startline-1 
        l = lines[ln].strip('\n')
        l = l.strip()
        # print(_bc.BOLD+_bc.HEADER,lines[ln],_bc.ENDC)
        # print(_bc.BOLD+_bc.HEADER,lines[ln+1],_bc.ENDC)

        while(l.endswith('&')):
            ln += 1 
            l = l[:-1] + lines[ln].strip('\n').strip()
        l = l.strip() 
        # print(f"For subroutine {self.name}",l)
        args = getArguments(l)
        return args


    def _get_global_constants(self,constants):
        """
        This function will loop through an ELM F90 file,
        collecting all constants -- derived types must be included in the
        usemod.txt file manually
        """
        const_mods = ['elm_varcon','elm_varpar',
                      'landunit_varcon','column_varcon','pftvarcon',
                      'elm_varctl']
        file = open(elm_files+self.filepath,'r')
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

    def _preprocess_file(self,varlist,interface_list,verbose=False):
        """
        This function will find child subroutines and variables used
        in the associate clause to be used for parsing for ro and wr derived types
        """
        from mod_config import _bc,regex_skip_string
        from utilityFunctions import getArguments,convertAssociateDict, getLocalVariables
        from interfaces import resolve_interface 

        # Logical that tracks if subroutine file needs to be overwritten.
        rewrite = False
        
        #Doesn't actaully get rid of associate (can though) should rename .
        self.associate_vars, self.status, associate_start, associate_end = getAssociateClauseVars(self)

        self._check_acc_status()
        m_skip = regex_skip_string.search(self.name)
        if(not self.acc_status and not m_skip):
            print(f"Must Add Acc Routine Directive to {self.name}")
            add_acc_routine_info(self)
             
        file = open(elm_files+self.filepath,'r')
        lines = file.readlines()
        file.close()

        # Check if associated derived types need to be analyzed 
        convertAssociateDict(self.associate_vars,varlist)
        getLocalVariables(self)

        ct = self.startline
        while(ct < self.endline):
            line = lines[ct]
            match_call = re.search(r'^call ',line.strip())
            if(match_call) :
                method = False
                x = line.strip().replace('(',' ').replace(')',' ').split()
                child_sub_name = ''
                ignore = bool(x[1].lower() in ['cpu_time','get_curr_date'] or 'update_vars' in x[1].lower())
                if(not ignore):
                    child_sub_name = x[1]
                    if(child_sub_name.lower() in interface_list):
                        l = lines[ct].strip('\n')
                        l = l.strip()
                        while(l.endswith('&')):
                            ct += 1
                            l = l[:-1] + lines[ct].strip('\n').strip()
                        l = l.strip()
                        args = getArguments(l)

                        child_sub_name, childsub = resolve_interface(self,child_sub_name,args,varlist,verbose=True)
                        if(not child_sub_name): 
                            print(f"Error couldn't resolve interface for {x[1]}")
                            self.printSubroutineInfo(long=True)
                            sys.exit()
                        print("New child sub name is:", child_sub_name)
                    else:
                        childsub = Subroutine(child_sub_name,calltree=self.calltree)

                    if('%' in child_sub_name):
                        print(f"WARNING CALLING CLASS METHOD at LINE {ct}!")
                        print(line)
                        method = True

                    child_sub_names = [s.name for s in self.child_subroutine_list ]

                    if(child_sub_name not in child_sub_names and not method):
                        self.child_subroutine_list.append(childsub)

            ct+=1

        if(rewrite):
            with open(elm_files+self.filepath,'w') as ofile:
                ofile.writelines(lines)

        # cover case where no derived types but still has child
        # subroutines to analyze
        if(self.child_subroutine_list):
            self.status = False

        return associate_end

    def _check_acc_status(self):
        """
        checks if subroutine already has !$acc directives
        """
        filename = self.filepath
        file = open(elm_files+filename,'r')
        lines = file.readlines() # read entire file
        for ct in range(self.startline, self.endline):
            line = lines[ct]
            # checks for any !$acc directives
            match_acc = re.search(r'^[\s]+(\!\$acc)',line)
            if(match_acc): 
                self.acc_status = True; 
                return

    def _analyze_variables(self,associate_end,vars, class_routine_info):
        """
        function used to determine read and write variables
        If var is written to first, then rest of use is ignored.
        Vars determined to be read are read-in from a file generated by
        full E3SM run.
        Vars that are determined to be written to must be checked to verify
        results of unit-testing.
        """
        #dictionary to be returned
        file = open(elm_files+self.filepath,'r')
        lines = file.readlines()
        file.close()

        if(class_routine_info["bool"]):
            print(f"In class routine ",class_routine_info["var"])

        vardict = {} # dictionary where key is the variable and values are read/write status.
        c = '[^a-zA-Z0-9_%]'  #character class for regex needed to ignore '%'
        
        for v in vars:
            variable_used = False
            ct = associate_end
            first_match = True
            while (ct < self.endline):
                line = lines[ct]
                #get rid of comments
                line = line.split('!')[0]

                #take into account line continuations
                line = line.rstrip('\n')
                while line.endswith('&'):
                    ct+=1
                    line = line[:-1] + lines[ct].strip().rstrip('\n')

                if(class_routine_info["bool"]):
                    vname = class_routine_info["var"]
                    line = re.sub("this%",vname+"%",line)

                #search line for variable:
                matchv     =  re.search(f'(?<={c}){v}(?=\W)',line) #match variable
                matcheq    =  re.search(r'[^<>=/]=[^><=]', line) #match assignment
                match_doif = re.search(r'^\s*(do |if|else if).',line) #match do and if statements
                match_call = re.search(r'^\s*call ',line)
                if((not match_doif) and matchv and matcheq and not(match_call)):
                    variable_used = True
                    l = line.replace('(',' ').replace(',',' ').replace(')',' ').replace('=',' = ')
                    split_line = l.split('=')
                    if (len(split_line) > 2 ):
                        print(line);
                        split_line[1] = split_line[1]+"=="+split_line[3]
                        print(split_line)
                        if(len(split_line) > 4): sys.exit("too many equals")
                    # if on left-hand side of '=' it's an output variable
                    # ignore rest for now -- USING elmtype_rw for NOW
                    lhs = split_line[0]
                    rhs = split_line[1]
                    match_lhs = re.search(f'(?<={c}){v}(?=\W)', lhs)
                    if(match_lhs):
                        vardict.setdefault(v,[]).append('w')
                        #if the first_match is write then it doesn't
                        # need to be read in from file
                        if(first_match): first_match = False; ct = self.endline

                    match_rhs = re.search(f'(?<={c}){v}(?=\W)', rhs)
                    if(match_rhs):
                        if(first_match): first_match = False;
                        vardict.setdefault(v,[]).append('r')

                    if(not(match_lhs or match_rhs)):
                        print(self.name, ct, v); print(line)
                        print(lhs, rhs)
                        sys.exit('Must be rhs or lhs')

                #count if and do statements as being read variables
                if(match_doif and matchv):
                    variable_used = True
                    if(first_match): first_match = False;
                    vardict.setdefault(v,[]).append('r')

                if(matchv and match_call): #assume read and write
                    variable_used = True
                    vardict.setdefault(v,[]).append('r');  vardict.setdefault(v,[]).append('w')

                ct += 1

        ##clean up vardict:
        for key in vardict.keys():  vardict[key] = list(set(vardict[key]))
        return vardict

    def parse_subroutine(self,elmvar,verbose=False):
        """
        This function parses temp.F90 to find which variables are ro,wo,rw
        elmvars is a list of derived_type variables.
        This function is called in main() after process_for_unit_test
        currently varlist holds all derived types known to be used in ELM.
        """
        from utilityFunctions import get_interface_list # just make this a global variable? 

        ignoreList = ['this','self','colpf','colnf','colps','colcf','colns',
                      'vegcf','vegcs','vegps','vegpf','vegns','vegnf','bounds',
                      'spm','spm_d','spm_p','isocol_cs', 'isoveg_cs','colcs',
                      'isocol_cf', 'isoveg_cf','cs','cf','col_cf_input']

        interface_list = get_interface_list()

        self.printSubroutineInfo()

        # preprocess file so to get child subroutines
        associate_end = self._preprocess_file(elmvar,interface_list,verbose=verbose)

        associated_list = [ key for key in self.associate_vars.keys() ]
        temp_dtype_names = []
        dtype_var_list = []
        class_routine_info = {"bool":False, "var" : ""}
        for val in self.associate_vars.values():
            for x in val:
                dtype = x.split('%')[0]
                temp_dtype_names.append(dtype)
        #
        #Create list that holds the names of the derived types only
        elm_var_names = [v.name for v in elmvar]
        if(associate_end == 0):
            ct = self.startline
        else:
            ct = associate_end

        fname = elm_files+self.filepath
        file = open(elm_files+self.filepath,'r')
        lines = file.readlines()
        file.close()
        class_routine = False
        class_routine_info["bool"] = False
        
        while( ct < self.endline ):
            line = lines[ct]
            #get rid of comments
            line = line.strip().split('!')[0]

            #take into account line continuations
            line = line.rstrip('\n')
            while line.endswith('&'):
                ct+=1
                line = line[:-1] + lines[ct].strip().rstrip('\n')

            # Check for derived types but not class methods
            # derived type arguments to subroutines handled elsewhere
            match = bool('%' in line and not('call' in line))
            if(match):
                match_var = re.findall(r"\w+%\w+",line)
                for dtype in match_var:
                    typename = dtype.split('%')[0]
                    if(typename.lower() in ['this'] and not class_routine ):
                        if(verbose): print(f"Inside 'class' routine {self.name}")
                        class_routine = True
                        class_routine_info["bool"] = True
                        #
                        var_type, varname = getLocalVariables(self,class_var=True)
                        err = True
                        for vname in elmvar:
                            if(vname.name == varname):
                                err = False
                                if(verbose): print(f"{typename} is {vname.name}")
                                typename = vname.name
                                dtype = re.sub("this%",vname.name +"%",dtype)
                                if(verbose): print(f"var is {dtype}")
                                class_routine_info["var"] = vname.name

                        if(err): sys.exit(f"Couldn't find {varname} in list")
                        
                    if(typename.lower() not in ignoreList):
                        temp_dtype_names.append(typename)
                        dtype_var_list.append(dtype)
            #end of if(match)
            ct+=1
        dtype_var_list = list(set(dtype_var_list))
        self.elmtypes  = list(set(temp_dtype_names))

        if(verbose): print(f"analyzing associate list variables for sub {self.name}")
        vardict_associate = self._analyze_variables(associate_end,associated_list, class_routine_info)

        # Need to match read/write status of associate pointer to the derived type:
        for key, values in vardict_associate.items():
            dtypes_li = self.associate_vars[key] #list of derivedtypes pointed to by key
            for var in dtypes_li:
                varname   = var.split('%')[0]
                varname = replace_key(varname)
                if(varname == 'vegcf'): varname = 'veg_cf'
                if(varname == 'col_cf_input'): varname = 'col_cf'
                try:
                    component = var.split('%')[1]
                except:
                    print('Error:',var)

                if( varname.lower() in ['this']):
                    if(verbose): print(f"adjusting class procedure associate list")
                    for vname in elm_var_names:
                        match_class_var = re.search(f'{vname}',self.name)
                        if (match_class_var):
                            if(verbose): print(f"{varname} is {vname}")
                            varname = vname

                if('r' in values): self.elmtype_r.setdefault(varname,[]).append(component)
                if('w' in values): self.elmtype_w.setdefault(varname,[]).append(component)


        print(f"analyzing other list variables for sub {self.name}")
        vardict_dtypes = self._analyze_variables(associate_end, dtype_var_list,class_routine_info)
        for key, values in vardict_dtypes.items():
            varname   = key.split('%')[0]
            component = key.split('%')[1]
            if('r' in values): self.elmtype_r.setdefault(varname,[]).append(component)
            if('w' in values): self.elmtype_w.setdefault(varname,[]).append(component)

        #clean up!
        for key in self.elmtype_r.keys(): self.elmtype_r[key] = list(set(self.elmtype_r[key]))
        for key in self.elmtype_w.keys(): self.elmtype_w[key] = list(set(self.elmtype_w[key]))
            

    def child_subroutines_analysis(self,elmvar):
        """
        This function handles parsing child_subroutines and merging
        variable dictionaries...
        """
        from utilityFunctions import get_interface_list
        #print(self.elmtype_ro)
        interface_list = get_interface_list()
        # child_subroutine_list is a list of Subroutine instances 
        for child_sub in self.child_subroutine_list:
            print(f"child_sub = {child_sub.name}")

            local_vars = getLocalVariables(child_sub,verbose=False)

            # Switch to a dictionary here. Maybe it's better to only use dictionaries?
            self.child_Subroutine[child_sub.name] = child_sub
            sub = self.child_Subroutine[child_sub.name]
            
            if(child_sub.name in interface_list):  continue

            self.child_Subroutine[child_sub.name].parse_subroutine(elmvar)

            if(sub.child_subroutine_list):
                sub.child_subroutines_analysis(elmvar)

            #add needed elmtypes to parent subroutine
            self.elmtypes.extend(sub.elmtypes)
            self.elmtypes = list(set(self.elmtypes))

            for key, values in sub.elmtype_r.items():
                for var in values:
                    self.elmtype_r.setdefault(key,[]).append(var)
                self.elmtype_r[key] = list(set(self.elmtype_r[key]))
            for key, values in sub.elmtype_w.items():
                for var in values:
                    self.elmtype_w.setdefault(key,[]).append(var)
                self.elmtype_w[key] = list(set(self.elmtype_w[key]))
                
        for s in self.child_Subroutine.values():
            self.calltree.append(s.calltree)
            if(child_sub in interface_list): continue

        self.status = True

    def analyze_calltree(self,tree):
        """
        returns unraveled calltree
        """
        tree_to_write = [[self.name,0]]
        #added = ['clm_drv',self.name]
        for i in range(0,len(tree)):
            el = tree[i]
            tree_to_write = determine_level_in_tree(branch=el,tree_to_write=tree_to_write)

        ofile = open(f"{self.name}CallTree.dat",'w')
        for branch in tree_to_write:
            level=branch[1];sub = branch[0]
            print(level*"|---->"+sub)
            ofile.write(level*"|---->"+sub+'\n')
        ofile.close()

    def generate_update_directives(self, clmvars_dict):
        """
        This function will create .F90 routine to execute the
        update directives to check the results of the subroutine
        """
        ofile = open(f"{home_dir}scripts/script-output/update_vars_{self.name}.F90",'w')

        spaces ="     "
        ofile.write("subroutine update_vars_{}(gpu,desc)\n".format(self.name))

        replace_inst = ['soilstate_inst','waterflux_inst','canopystate_inst','atm2lnd_inst','surfalb_inst',
                        'solarabs_inst','photosyns_inst','soilhydrology_inst','urbanparams_inst']

        for v in self.elmtype_w.keys():
            if(v in replace_inst): v = v.replace('_inst','_vars')

            mod = clmvars_dict[v].declaration
            ofile.write(spaces + f"use {mod}, only : {v} \n")

        ofile.write(spaces+"implicit none \n")
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

        ofile.write(spaces+"if(gpu) then\n")
        acc = "!$acc "

        for v,comp_list in self.elmtype_w.items():
            if(v in replace_inst): v = v.replace('_inst','_vars')
            ofile.write(spaces+acc+"update self(& \n")
            i = 0
            for c in comp_list:
                i +=1
                if i == len(comp_list) :
                    name = f"{v}%{c}"
                    c13c14 = bool('c13' in name or 'c14' in name)
                    if(c13c14):
                        ofile.write(spaces+acc+f")\n")
                    else:
                        ofile.write(spaces+acc+f"{name} )\n")
                else:
                    name = f"{v}%{c}"
                    c13c14 = bool('c13' in name or 'c14' in name)
                    if(c13c14): continue
                    ofile.write(spaces+acc+f"{name}, & \n")


        ofile.write(spaces+"end if \n")
        ofile.write(spaces+"!! CPU print statements !! \n")
        ## generate cpu print statements
        for v,comp_list in self.elmtype_w.items():
            if(v in replace_inst): v = v.replace('_inst','_vars')
            for c in comp_list:
                name = f"{v}%{c}"
                c13c14 = bool('c13' in name or 'c14' in name)
                if(c13c14): continue
                ofile.write(spaces+f"write(10,*) '{name}' \n")
                ofile.write(spaces+f"write(10,*) {name}\n")

        ofile.write(spaces+"close(10)\n")
        ofile.write("end subroutine ")
        ofile.close()
    
    
    def examineLoops(self,global_vars,varlist,add_acc=False,subcall=False,
                        verbose=False,adjust_allocation=False):
        """
        Function that will parse the loop structure of a subroutine
        Add loop parallel directives if desired
        """
        from mod_config import _bc
        from utilityFunctions import lineContinuationAdjustment,getLocalVariables
        from utilityFunctions import find_file_for_subroutine, getArguments, get_interface_list
        from utilityFunctions import convertAssociateDict, determine_filter_access
        from interfaces import resolve_interface

        interface_list = get_interface_list() # move this to a global variable in mod_config?
        if(not subcall):
            associate_keys = self.associate_vars.keys()
            temp_global_vars = [key for key in associate_keys]
            global_vars = temp_global_vars[:]
        
        # Check if associated derived types need to be analyzed 
        convertAssociateDict(self.associate_vars,varlist)

        if(adjust_allocation): 
            # dict with 'arg' : Subroutine
            # where 'arg' is a local array, and 'sub' is child subroutine that uses it.
            passed_to_sub = {} 
            local_array_list = [v for v in self.LocalVariables['arrays']]
            print(f"local_array for {self.name} \n",local_array_list)

        if(verbose): print(f"Opening file {elm_files+self.filepath} ")
        ifile = open(elm_files+self.filepath,'r')
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
                if(x[1].lower() not in ['cpu_time','get_curr_date','endrun'] and 'update_vars' not in x[1].lower()):
                    child_sub_name = x[1]

                    args = getArguments(l)
                    
                    if(child_sub_name in interface_list):
                        child_sub_name, childsub = resolve_interface(self,child_sub_name,args,varlist,verbose=True)
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
                    
                    childloops = childsub.examineLoops(global_vars=global_vars,varlist=varlist,subcall=True,
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
                #Found an inner loop
                else :
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
        
        if(add_acc): 
            # Create dictionary to hold subroutines found so far 
            # and their initial startlines to help adjust for line insertions later.
            sub_dict = {}

            # dictionary of the loops to avoid adding OpenACC directives to the same 
            # Loop more than once 
            loop_dict = {} 
            for loop in self.DoLoops: 
                loopkey = f"{loop.subcall.name}:L{loop.start[0]}"
                if(loopkey not in loop_dict):
                    loop_dict[loopkey] = loop
                    loop.printLoop(long=False)
                if(loop.subcall.name not in sub_dict):
                    file,startline,endline = find_file_for_subroutine(loop.subcall.name)
                    sub_dict[loop.subcall.name] = startline
            
            print("Final subroutine dictionary:",sub_dict)
            lines_adjusted = {}
            for key, loop in loop_dict.items(): 
                loop.printLoop(long=False)
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
        
        exportVariableDependency(self.name,var_list,global_loop_vars,local_vars_only,self.DoLoops)

        return

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
        print("exportReadWriteVariables ===================") 
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

        return 
    
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
            print(_bc.BOLD+_bc.WARNING+f"Opening file {elm_files}{self.filepath}"+_bc.ENDC)
            ifile = open(elm_files+self.filepath,'r')
        
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
            return
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
                print(_bc.BOLD+_bc.WARNING+f"Writing to file {elm_files}{self.filepath}"+_bc.ENDC)
                ofile = open(elm_files+self.filepath,'w')
            else:
                print(_bc.BOLD+_bc.WARNING+f"Writing to file "+home_dir+"modified-files/"+self.filepath+_bc.ENDC)
                ofile = open(home_dir+"modified-files/"+self.filepath,'w')

            ofile.writelines(lines)
            ofile.close() 
        else:
            print(_bc.BOLD+_bc.WARNING+"NO CHANGE"+_bc.ENDC)
            