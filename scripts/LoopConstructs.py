"""
Module that holds the Loop Class 
that is used to parse subroutines
"""
import re  
import sys 
from utilityFunctions import lineContinuationAdjustment

def exportVariableDependency(subname, var_list,global_vars,local_vars,DoLoops,mode="LaTex"):
    """
    This function takes list of all collected DoLoops of a 
    subroutine (parent) and creates a readable table with
    the variables.  
    """
    from mod_config import _bc 

    #Initialize dictionary for variables across all Loops 
    num_loops = len(DoLoops)
    varsForAllLoops = {v : [" - "]*num_loops for v in var_list }
    current_name = subname
    old_name = subname
    if(mode == "LaTex"):
         # store subroutine name and how many columns they occupy
        header_tex = []

    header = []
    count = 0 
    for n, loop in enumerate(DoLoops):
        current_name = loop.subcall.name
        if(current_name is old_name):
            count += 1
            for v in var_list:
                varsForAllLoops[v][n] = f"{'-':4}"
        else: # New subroutine 
            for v in var_list:
                varsForAllLoops[v][n] = f"{'|-':4}"
            width = 4*count
            if(count == 0): continue 
            x = '|'+old_name[0:width-2]
            string  = f"{x:{width}}"
            header.append(string)
            
            # 
            if(mode == "LaTex"):
                header_tex.append([old_name,count])
            
            old_name = loop.subcall.name
            count = 1
        #end of Loops
        if(n == len(DoLoops)-1):
            width = 4*count
            x = '|'+current_name[0:width-2]            
            string = f"{x:{width}}"
            header.append(string)
            if(mode == "LaTex"): header_tex.append([current_name,int(width/4)])

    
    header_string = "".join(header)
    print(f'{" ":<20} {header_string}')

    ofile = open(f"./script-output/{subname}AllLoopVariables.dat",'w')
    ofile.write(f'{" ":<20} {header_string}'+'\n')
    #Update formatted status for each var
    current_name = subname
    old_name = subname
    for n, loop in enumerate(DoLoops):
        current_name = loop.subcall.name
        if(current_name is not old_name):
            #Loops are in a different subroutine 
            for v, status in loop.vars.items():
                if(v not in var_list): continue 
                status = "|"+status 
                varsForAllLoops[v][n] = f"{status:4}"
            old_name = loop.subcall.name
        else:
             for v, status in loop.vars.items():
                if(v not in var_list): continue 
                varsForAllLoops[v][n] = f"{status:4}"
    
    for key in varsForAllLoops:
        string = ''.join(varsForAllLoops[key])
        if(key in local_vars): 
            skey = _bc.WARNING+key+_bc.ENDC
        elif(key in global_vars): 
            skey = _bc.OKBLUE+key+_bc.ENDC
        
        print(f"{skey: <28} {string}")
        ofile.write(f"{skey: <28} {string}"+'\n')
    ofile.close()
    create_latex_table(header_tex,varsForAllLoops, DoLoops,subname)
    return 

def create_latex_table(header,varsForAllLoops,doloops,subname):
    """
    Take dependency data and generate a LaTeX table 
    """

    ofile = open(f"./script-output/{subname}Table.tex",'w')
    ofile.write("\\begin{table*}[]\n")
    ofile.write("\centering\n")
    ofile.write("\caption{}\n")
    ofile.write("\label{tab:my-table}\n")
    # create string for number of columns:
    individual = True 
    compressed_vars_loops = {v:[] for v in varsForAllLoops}

    num_sections = len(header)
    num_loops = 0 
    running_loop_tally = []
    for section in header: 
        num_loops += section[1]
        running_loop_tally.append(num_loops-1) 
    
    print(running_loop_tally)
    num_removed = 0
    for l in range(0,num_loops):
        count = 0
        for var in varsForAllLoops:
            status = varsForAllLoops[var][l].strip()
            if(status != "-"):
                count += 1 
        if(count >= 2): # add to the new dict
            for var in varsForAllLoops:
                status = varsForAllLoops[var][l] 
                compressed_vars_loops[var].append(status)
        else:
            
            # skipping this loop -- need to decrement section count as well
            print(f"Skipping loop {l}")
            section = 0
            found = False
            while(not found):
                if(l <= running_loop_tally[section]):
                    found = True
                    header[section][1] -= 1 # decrement this section
                else:
                    section +=1
            # recalculate num_loops and running loop tally:
            num_loops = 0 
            # running_loop_tally = []
            for section in header: 
                num_loops += section[1]
                # running_loop_tally.append(num_loops-1)
            print("New num_loops,tally,header:",num_loops,header)
    

    # cols = "|p{1cm}|"
    cols = "|p{0.1\\textwidth}|"
    const = 0.
    for section in header:
        count = section[1]
        width = 0.08/num_loops
        width = round(width,3)
        if(individual):
            temp = 'p{'+f"{width}"+"\\textwidth}"
            cols += temp*count            
        cols += '|'

    ofile.write("\\begin{tabular}{"+cols+"}\n")
    ofile.write("\hline\n")
    # create string for headers 
    hstring = " &"
    num_sections = len(header) 
    for section in header[:-1]:
        sname = section[0]
        if("_" in sname): sname = sname.replace("_","\_")
        count = section[1]
        if(individual):
            hstring += "\multicolumn{"+f"{count}"+"}{c|}{"+f"{sname}"+"}&"
        else:
            hstring += sname+'&'
    
    section = header[num_sections-1]; 
    sname, count = section 
    if("_" in sname): sname = sname.replace("_","\_")
    if(individual):
        hstring += "\multicolumn{"+f"{count}"+"}{c|}{"+f"{sname}"+"}\\\\ \n"
    else:
        hstring += sname+'\\\\ \n'

    ofile.write(hstring)
    ofile.write("\hline\n")

    # Make string for each table row:
    rows = [] 
    print(header) 
    for var in compressed_vars_loops:
        loop_status = compressed_vars_loops[var]
        row = var.replace("_","\_")+'&'
        
        # Add '&' after each section
        section_num = 0 
        count = header[section_num][1]

        for n, loop in enumerate(loop_status):
            loop = loop.replace('|',' ')
            if(individual): 
                loop = loop.strip()
                row += loop
                if(n == len(loop_status)-1):
                    row += " \\\\ [0.5ex]"
                else: 
                    row += '&'
            else:           
                row += f"{loop}"
                if(n+1 == count):
                    section_num += 1
                    count += header[section_num][1]
                if(n == len(loop_status)-1):
                    row += " \\\\"
                else:
                    row += '&'

        rows.append(row)
    
    for row in rows:
        ofile.write(row+'\n')
    
    ofile.write("\hline\n")
    ofile.write("\end{tabular}\n\end{table*}\n")
    ofile.close()


class Loop(object):
    def __init__(self, start,index,ifile,sub):
        self.start = [start]
        self.end = [0]
        self.index = [index]
        self.nested = 0
        self.innerloops = [] 
        self.vars = {} 
        self.reduction = False
        self.reduce_vars = []
        self.subcall = sub
        self.scalar_vars = {}
        self.lines = []
        self.file = ifile 
        self.filter = []

    
    def printLoop(self,substartline=0,long=True):
        """
        Function to print a Loop instance
        """
        from mod_config import _bc 
        lstart = self.start[0]
        lend = self.end[0]
        if(not self.reduction):
            print(f"Loop at {lstart}-{lend} of {self.file}::{self.subcall.name}")
        else:
            print(_bc.WARNING+f"Loop at {lstart}-{lend} of {self.file}::{self.subcall.name}"+_bc.ENDC)

        slice = self.lines[:]
        if(long):
            print(f"It is nested {self.nested} times with indices {self.index}")
            for ln,line in enumerate(slice):
                print(lstart+ln,line.strip('\n'))
    
    def removeArraysAsIndices(self,vdict,line,arrays,verbose): 
        """
        Removes arrays such as snl(c) used as indices and sets them as read-only 
        """
        regex_var = re.compile(r'\w+')
        temp = line 
        keep_removing = False 
        regex_indices = re.compile(r'(?<=\()(.+)(?=\))')

        for var in arrays:
            # only get var name 
            v = regex_var.search(var).group()
            
            regex_check_index = re.compile(f"\w+\([,a-z0-9*-]*(({v})\(.\))[,a-z+0-9-]*\)",re.IGNORECASE)
            match = regex_check_index.search(temp)
            if(match):
                if(verbose): print(f"found array {v} used as index")
                # Add to dict as read-only: 
                vdict.setdefault(v,[]).append('r')
                # substitute from the entire line 
                i = regex_indices.search(var).group() 
                i = f"\({i}\)"
                temp = re.sub(f"{v}{i}",v,temp)
                if(verbose):
                    print(var,v) 
                    print("new line is: ",temp)
                keep_removing = True

        return temp, keep_removing

    def parseVariablesinLoop(self,verbose=False):
        """
        Goes through loop line by line and
        returns the self.vars dictionary that 
        holds the variables modified by this Loop
        """
        from mod_config import _bc 
        # non-greedy capture
        # ng_regex_array = re.compile(f'\w+?\({cc}+?\)')
        ng_regex_array = re.compile("\w+\s*\([,\w+\*-]+\)",re.IGNORECASE)

        regex_if = re.compile(r'^(if|else if|elseif)')
        regex_cond = re.compile(r'\((.+)\)')
        regex_subcall = re.compile(r'^(call)')
        # 
        #regex to match code that should be ignored 
        regex_skip = re.compile(r'^(write)')
        regex_dowhile = re.compile(f'\s*(do while)',re.IGNORECASE)

        # regex for scalar variables:
        # since SPEL already has the loop indices, no need to hardcode this?
        indices = ['i','j','k','g','l','t','c','p','fc','fp','fl','ci','pi','n','m','s'] 
        if(self.subcall.LocalVariables['scalars']):
            list_of_scalars = [v.name for v in self.subcall.LocalVariables['scalars'] if v.name not in indices]
            # print(_bc.OKBLUE+f"list of scalars for {self.subcall.name}\n {list_of_scalars}"+_bc.ENDC)
            str_ = "|".join(list_of_scalars)
            regex_scalars = re.compile(f"(?<!\w)({str_})(?!\w)",re.IGNORECASE)
        else:
            list_of_scalars = [] 
        
        # Initialize dictionary that will 
        # hold array variables used in the loop
        variable_dict = {}

        slice = self.lines[:]
        lines_to_skip = 0
        reprint=True
        for ln,line in enumerate(slice):
            if(lines_to_skip > 0):
               lines_to_skip -= 1 
               continue 
            l, lines_to_skip = lineContinuationAdjustment(slice,ln,verbose)

            #match any functions or statements to be ignored
            match_skip = regex_skip.search(l)
            if(match_skip): continue 

            # match if statements 
            match_if = regex_if.search(l);
            match_dowhile = regex_dowhile.search(l)
            if(match_if):
                m = regex_cond.findall(l);
                if("then" not in l):
                    if(verbose): print("single line if statement")
                else:
                    if(verbose): print(ln,m)
            elif(not match_dowhile):

                # Currently ignore subroutines called inside loops 
                match_subcall = regex_subcall.search(l)
                if(match_subcall): continue

                #Find all array variables in the line
                m_arr = ng_regex_array.findall(l);
                if(m_arr): 
                    lnew = l
                    # assume that there are some arrays used as indices
                    removing = True  
                    while(removing):
                        temp, removing = self.removeArraysAsIndices(vdict=variable_dict, line=lnew,arrays=m_arr,verbose=verbose)
                        lnew = temp 
                        m_arr = ng_regex_array.findall(lnew)
                        if(verbose): print("New findall is: ",m_arr)
                    
                    if(m_arr):
                        variable_dict, reprint = self._getArrayVariables(ln,l,m_arr,variable_dict,reprint=reprint,verbose=verbose)
                
                # Find all local scalar variables
                if(list_of_scalars):
                    m_scalars = regex_scalars.findall(l)
                    if(m_scalars):
                        self._get_scalars(ln,l,m_scalars,variable_dict,verbose=verbose)
        
        if(self.reduction): 
            print(_bc.WARNING+"This Loop may contain a race-condition for the variables \n",f"{self.reduce_vars}"+_bc.ENDC)

        #clarify read/write status of each variable in the loop
        for var, status in variable_dict.items():
            #remove duplicates
            status = list(set(status))
            #set read-only, write-only, rw status:
            if('r' in status and 'w' not in status):
                variable_dict[var] = 'ro' #read only 
            elif('w' in status and 'r' not in status):
                variable_dict[var] = 'wo' #write only
            elif('w' in status and 'r' in status):
                variable_dict[var] = 'rw' #read-write
        self.vars = variable_dict.copy()
        return 

    def addOpenACCFlags(self, lines_adjusted, subline_adjust,id,verbose=False):
        """
        Function that will add openACC directives to loop
        
        lines_adjusted is a dictionary to keep track of line insertions into a subroutine
        to appropriately adjust where the loops start.
        """
        from mod_config import elm_files, _bc
        
        total_loops = self.nested + 1 
        ifile = open(f"{elm_files}{self.file}",'r')
        mod_lines = ifile.readlines() 
        ifile.close() 
        
        outer_lstart = self.start[0] + subline_adjust + lines_adjusted[self.subcall.name]
        # First check if OpenACC flags have already been added.
        if("!$acc" in mod_lines[outer_lstart-2]): 
            print("Loop already has OpenACC flags, Skipping")
            return
        if(self.reduction):
            print(_bc.WARNING + f"Reduction in {self.file}::{id} for:\n {self.reduce_vars}"+_bc.ENDC)
            return

        tightly_nested = 1
        for loop in range(0,total_loops):
            # Loop through every loop that isn't this one and test to
            # see if they are nested. 
            # Increment counter for the collapse clause
            if(tightly_nested >1): 
                tightly_nested -= 1 
                continue  
            acc_parallel_directive = f" "
            for innerloops in range(loop,total_loops):
                diff = self.start[innerloops] - self.start[loop] 
                if(diff==tightly_nested): 
                    tightly_nested += 1
            
            if(loop == 0):
                # only put data clause on outermost loop 
                acc_parallel_directive = "!$acc parallel loop independent gang vector default(present)"
            else : 
                # for inner loops just default to sequential for now
                # and allow the developer to increase parallelism based on profiling results 
                acc_parallel_directive = "!$acc loop seq"
            if(tightly_nested> 1):
                acc_parallel_directive = acc_parallel_directive + f" collapse({tightly_nested}) "
            acc_parallel_directive = acc_parallel_directive + '\n'
            lstart = self.start[loop]-1+lines_adjusted[self.subcall.name]+subline_adjust
            line = mod_lines[lstart]
            padding = " "*(len(line) - len(line.lstrip()))
            acc_parallel_directive = padding+acc_parallel_directive
            print(f"Inserting :\n {acc_parallel_directive}")
            mod_lines.insert(lstart,acc_parallel_directive)
            lines_adjusted[self.subcall.name] += 1 
        
        lend = self.end[0] + lines_adjusted[self.subcall.name] + subline_adjust
        for ln in range(outer_lstart-1,lend): 
            print(ln,mod_lines[ln].strip('\n'))
        overwrite = input(f"Overwrite {self.file}?")
        if(overwrite == 'y' ): 
            with open(f"{elm_files}{self.file}",'w') as ofile:
                ofile.writelines(mod_lines)
        else:
            sys.exit()

    def _getArrayVariables(self,ln,l,m_arr,variable_dict,reprint=True,verbose=False,interact=False):
        """
        This function takes a given line in of a Loop 
        and identifies the read/write status of each array 
        variable present
        """
        # split the about the assignment
        if("=" not in l):
            print(f"Line does not contain an assignment -- Bug in code or regex?")
            print(l)
            sys.exit()

        assignment = l.split("=")
        
        if(len(assignment)>2):
            print(l) 
            sys.exit("getArrayVariables::Too many equals in this case!")
        lhs = assignment[0] 
        rhs = assignment[1]
        #
        regex_indices = re.compile(r'(?<=\()(.+)(?=\))')
        regex_var = re.compile(r'\w+')

        vars_already_examined = []
        for var in m_arr:
            # This means only the first instance of the variable is catalogued as 
            # write, read or reduction. 
            # get subgrid index from filter 
            varname = regex_var.search(var).group() 
            if(varname in ["min","max"]): continue 
            if(varname.lower() in vars_already_examined): continue
            vars_already_examined.append(varname.lower())
            
            # matches only exactly "varname"
            regex_varname = re.compile(f"(?<!\w)({varname})(?!\w)",re.IGNORECASE)

            if("filter" in var): 
                if("filter" in rhs):
                    subgrid_indx = lhs.strip()
                    fvar = regex_var.search(rhs).group()
                    filter_indx = regex_indices.search(rhs).group()
                    self.filter = [fvar,subgrid_indx,filter_indx]
                else:
                    # filter is being assigned -- no need to consider
                    subgrid_indx = rhs.strip()
                    fvar = regex_var.search(lhs).group()
                    filter_indx = regex_indices.search(lhs).group()
                    self.filter = [fvar,subgrid_indx,filter_indx]
            
            in_lhs = regex_varname.search(lhs)
            in_rhs = regex_varname.search(rhs)
            if(varname == "tx"): 
                print(f"in LHS:", bool(in_lhs))
                print(f"in RHS: {bool(in_rhs)}\n Line: {l}")
            # check if var is only on assigned
            if(in_lhs and not in_rhs): 
                variable_dict.setdefault(varname,[]).append('w')
                            
            elif(in_rhs and not in_lhs): 
                variable_dict.setdefault(varname,[]).append('r')

            # Now check if variable appears on both sides
            # Requires additional checking for reduction operation
            elif(in_lhs and in_rhs):
                m_indices = regex_indices.search(var).group()
                indices = m_indices.split(',')

                # variable appears on both sides and is missing at least one loop index 
                # Need to ask if the variable is being reduced
                if(verbose): print(indices,self.index)

                # Since inner loops may not be tightly nested, we need to 
                # find out how many loops this line of code is inside. 
                loopcount = 0 
                for n, loopstart in enumerate(self.start):
                    loopend = self.end[n]
                    linecount = ln + self.start[0]
                    if(linecount > loopstart and linecount < loopend):
                        loopcount += 1 
                if(verbose) : print(f"This line {ln} is inside {loopcount} Loops!")
                
                if(loopcount < 1): 
                    print(l)
                    for n, loopstart in enumerate(self.start):
                        print(loopstart, self.end[n])
                    sys.exit("Error: Not in a Loop!?")

                if(len(indices) < loopcount):
                    if(reprint and interact):
                        self.printLoop()
                        reprint = False
                    if(var in self.reduce_vars): continue
                    if(interact):
                        reduction = input(f"is {var} at line {ln} being reduced in this loop?")
                    else:
                        reduction='y'
                    if(reduction=='y'):
                        self.reduction = True
                        self.reduce_vars.append(var)
                elif(len(indices) == loopcount): 
                    # Check if it's a lower-level subgrid to a higher level 
                    loopindex = False 
                    for i in self.index:
                        if(indices[0] in i):
                            loopindex = True
                    
                    if(not loopindex): 
                        print(f"reduction occuring between subgrids",l)
                        self.reduction = True; 
                        self.reduce_vars.append(var)
                    else:
                        # Check that both indices are the same 
                        # catch scenarios like (c,j) = (c,j-1) 
                        # where the order matters 
                        same_indices = True 
                        print(f"checking for same indices for :",l)
                        # using varname here didn't work for some reason
                        ng_regex_array = re.compile("\w+\s*\([,\w+\*-]+\)",re.IGNORECASE)

                        # Get lhs indices:
                        lhs_var = ng_regex_array.search(lhs).group() 
                        lhs_indx = regex_indices.search(lhs_var).group()
                        lhs_indx = [m.replace(' ','').lower() for m in lhs_indx]
                        # get indices for all rhs instances:
                        rhs_vars = ng_regex_array.findall(rhs) 
                        for rv in rhs_vars:
                            rvname = regex_var.search(rv).group() 
                            if(rvname != varname): continue 
                            
                            rhs_indx = regex_indices.search(rv).group() 
                            if(len(rhs_indx) != len(lhs_indx)):
                                same_indices = False 
                                break
                            # compare the lists. Does this need regex for robustness?
                            rhs_indx = [m.replace(' ','').lower() for m in rhs_indx]
                            if(rhs_indx != lhs_indx): 
                                same_indices = False
                                break 
                        # May be an order dependent calculation. Flag as reduction
                        if(not same_indices):  
                            print(f"Order dependent calculation",l)
                            self.reduction = True
                            self.reduce_vars.append(var)

                # variable_dict.setdefault(varname,[]).append('rw')
                variable_dict.setdefault(varname,[]).extend(['r','w'])
        
        return variable_dict, reprint

    def _get_scalars(self,ln,l,m_scalars,variable_dict,verbose=True):
        """
        function that takes the local scalars matched in m_scalars 
        and determines the write/read status and reduction status
        """
        lhs = l.split('=')[0]
        rhs = l.split('=')[1]

        m_scalars = list(dict.fromkeys(m_scalars).keys()) # remove duplicate but keep order
        for lcl_var in m_scalars:
            regex = re.compile(f"(?<![\w]){lcl_var}(?![\w])")
            m_lhs = regex.search(lhs)
            m_rhs = regex.search(rhs)
            if(m_lhs and not m_rhs): # only assigned
                variable_dict.setdefault(lcl_var,[]).append('w')
            elif(m_rhs and not m_lhs):
                variable_dict.setdefault(lcl_var,[]).append('r')
            elif(m_lhs and m_rhs):
                self.reduction = True
                self.reduce_vars.append(lcl_var)
                variable_dict.setdefault(lcl_var,[]).extend(['r','w'])
                print(f"{lcl_var} needs reduction operation in this Loop")
        return



