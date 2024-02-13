import re
import sys
import write_routines as wr
import subprocess as sp 
from mod_config import ELM_SRC
## arrow and tab are strings for writing files or printing readable output
arrow = '|--->'
tab   = '    '
class derived_type(object):
    def __init__(self, vname, vmod   # name of variable and mod file
                , dtype  = None      # name of derived type
                , components = None  # list of type and component name
                ):
        self.name = vname
        self.mod = '' 
        cmd = f'find {ELM_SRC}  \( -path "*external_models*" \) -prune -o  -name "{vmod}.F90" '
        output = sp.getoutput(cmd)
        if(not output): 
            sys.exit(f"Couldn't locate file {vmod}")
        else:
            output = output.split('\n')
            for el in output: 
                if("external_models" not in el):
                    self.mod = el
        
        if(not self.mod): 
            sys.exit(f"Couldn't find file for {vname}\ncmd:{cmd}\n"
                     f"output: {output}\n")
        
        self.declaration = vmod
        if dtype == None:
            self.dtype = ''
        else:
            self.dtype = dtype
        if components == None:
            self.components = []
        else :
            self.components = components
        #
        # Flag to see if Derived Type has been analyzed
        #
        self.analyzed = False

    def _add_components(self,li, lines,array,ln,datatype,verbose=False):
        #
        name = li[1]
        n = '%'+name
        ct = 0
        if(verbose): 
            print(f"Adding component {datatype} {name} to {self.name}")
        # Need to find the allocation of component
        # to get the bounds.  Necessary for duplicateMod.F90 creation
        
        if(array):
            for line in lines:
                ct+=1
                #get rid of comments
                line = line.strip().split('!')[0]
                alloc = re.compile(f'^(allocate)\s*\(\s*this{n}( |\()')
                alloc_name = re.compile(f'^(allocate)\s*\({self.name}{n}( |\()')
                string_name = f'allocate({self.name}{n}'
                string = f'allocate(this{n}'
                match_alloc = alloc.search(line.lower())
                if match_alloc :
                    line = line.split(';')[0]
                    line = line[len(string):].strip()
                    l = line[0:len(line)-1]
                    if(verbose): print("matched alloc")
                    self.components.append([False,name,l,datatype])
                    break
                match_alloc_name = alloc_name.search(line.lower())
                if match_alloc_name :
                    line = line.split(';')[0]
                    line = line[len(string_name):].strip()
                    l = line[0:len(line)-1]
                    self.components.append([False,name,l,datatype])
                    break

        else:
          self.components.append([False,name,'',datatype])
        if(verbose): 
            print("self.components:",self.components)

    def _print_derived_type(self):
        print("-----------------------------")
        print("variable:",self.name, "from Mod:",self.mod)
        print("type:",self.dtype)
        print("has components:")
        for c in self.components:
            print(c[0],c[1],c[2])


    def analyzeDerivedType(self,verbose=False):
        #
        # This function will open each mod file, find the variable type
        # and fill out the components of the variable
        #
        import subprocess as sp
        import sys 

        found_declaration = False
        # First need to check if declaration is in elm_instMod
        name = self.name
        cmd = f'grep -in -E "::[[:space:]]*({name})" {ELM_SRC}/main/elm_instMod.F90'
        cmd2 = f'grep -in -E "::[[:space:]]*({name})" {ELM_SRC}/dyn_subgrid/dynSubgridDriverMod.F90'
        output1 = sp.getoutput(cmd)
        output2 = sp.getoutput(cmd2)
        output = ''
        if(output1): output = output1; self.declaration = 'elm_instMod'
        if(output2 and not (output1) and 'intent' not in output2): output = output2; self.declaration = 'dynSubgridDriverMod'
        if (output):
            output = output.replace(':',' ')
            output = output.split()
            dec_linenum = output[0]
            #find what's in the parentheses
            par = re.compile("(?<=\()(\w+)(?=\))")
            m = par.search(output[1])
            if(not m): print(output)
            inner_str = m.group()
            self.dtype = inner_str
            found_declaration = True
            clminst = True
            print(f"declaration in {self.declaration}")
        try:
            if(verbose): 
                print(f"{self.name} Opening file: {self.mod}")
            ifile = open(self.mod)
        except:
            print("ERROR: file ",self.mod, "not found")
            exit(1)

        # Find declaration of variable
        lines = ifile.readlines()
        var = self.name
        if(not found_declaration):
            for l in lines:
                line = l.split("!")[0] 
                line = line.strip() 
                m_type = re.search(f"^(type)",line)
                match = re.search(f'::\s*({var})', line)
                if(match and m_type):
                    #find what's in the parentheses
                    par = re.compile("(?<=\()(\w+)(?=\))")
                    m = par.search(line)
                    if(not m): 
                        print("Error in analyzeDerivedType")
                        print(line);
                        print(f"var : {var} , file = {self.mod} ")
                        sys.exit() 
                    inner_str = m.group()
                    self.dtype = inner_str
                    if(verbose): print(f"{self.name} -- Found type {self.dtype}")
                    found_declaration = True
                    break

        if(not found_declaration):
            print("ERROR:  Couldn't find declaration of", var)
            print("in file",self.mod)
            exit(1)

        # Now find definition of type to find components!
        type_start_line = 0
        type_end_line = 0
        ct = 0
        print("============ ",self.name," =================================================")
        regex_type = re.compile(f"^\s*(type)",re.IGNORECASE)
        regex_dtype = re.compile(f'(::)\s*({self.dtype})',re.IGNORECASE)
        for line in lines:
            l = line.split("!")[0] 
            l = l.strip() 
            ct += 1
            match_type = regex_type.search(l)
            if(match_type):
                match_dtype = regex_dtype.search(l)
                if(match_dtype):
                    type_start_line = ct
                    if(verbose): print(f"{self.name} -- Type start line is {ct}")
            array = False
            if(type_start_line != 0):
                #test to see if we exceeded type definition
                _end1 = re.search(f"^\s*(contains)",l)
                _end  = re.search(f'^\s*(end type)',l)
                if(not _end and not _end1):
                    data_type = re.compile(f'^\s*(real|integer|logical|character)')
                    m = data_type.search(line)
                    if(m):
                        datatype = m.group()
                        l = l.replace(',',' ')
                        l = l.replace('pointer','')
                        l = l.replace('private','')
                        l = l.replace('public','')
                        l = l.replace('allocatable','')
                        x    = l.split()
                        x[2] = re.sub(r'[^\w]','',x[2])
                        l = l.replace('::',' ')
                        if ':' in l: array = True
                        self._add_components([x[0],x[2]],lines,array,ln=type_start_line,datatype=datatype,verbose=verbose)
                else:
                    type_end_line = ct
                    break
        ifile.close()
        if(type_start_line == 0) :
            print(f"Error couldn't analyze type {self.name} {self.dtype}")
            
            sys.exit()
        self.analyzed = True

    def _create_write_read_functions(self, rw,ofile,gpu=False):
        #
        # This function will write two .F90 functions
        # that write read and write statements for all
        # components of the derived type
        #
        # rw is a variable that holds either read or write mode
        #
        spaces = "     "
        fates_list = ["veg_pp%is_veg","veg_pp%is_bareground","veg_pp%wt_ed"]
        if(rw.lower() == 'write' or rw.lower() == 'w'):
            ofile.write(spaces+'\n')
            ofile.write(spaces+'!====================== {} ======================!\n'.format(self.name))
            ofile.write(spaces+'\n')
            if(gpu):
                ofile.write(spaces+"!$acc update self(& \n")
                vars = [] 
            for n, component in enumerate(self.components):
                if component[0] == False:  continue
                c13c14 = bool('c13' in component[1] or 'c14' in component[1])
                if(c13c14): continue
                fname = self.name+'%'+component[1]
                if(fname in fates_list): continue
                if(gpu):
                    vars.append(fname)
                else:
                    str1 = f'write (fid, "(A)") "{fname}" \n'
                    str2 = f'write (fid, *) {fname}\n'
                    ofile.write(spaces + str1)
                    ofile.write(spaces + str2)
            if(gpu):
                for n, v in enumerate(vars):
                    if(n+1 < len(vars)):
                        ofile.write(spaces+f"!$acc {v}, &\n")
                    else:
                        ofile.write(spaces+f"!$acc {v} )\n") 

        elif(rw.lower() == 'read' or rw.lower() =='r'):
            ofile.write(spaces+'\n')
            ofile.write(spaces+'!====================== {} ======================!\n'.format(self.name))
            ofile.write(spaces+'\n')

            for component in self.components:

                if component[0] == False: continue
                c13c14 = bool('c13' in component[1] or 'c14' in component[1])
                if(c13c14): continue
                fname = self.name+'%'+component[1]
                if(fname in fates_list): continue

                dim = component[2]
                dim1 = wr.get_delta_from_dim(dim,'y'); dim1 = dim1.replace('_all','')
                str1 = "call fio_read(18,'{}', {}{}, errcode=errcode)\n".format(fname,fname,dim1)
                str2 = 'if (errcode .ne. 0) stop\n'
                ofile.write(spaces + str1)
                ofile.write(spaces + str2)



