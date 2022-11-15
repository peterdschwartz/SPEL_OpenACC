import re
from mod_config import elm_files
import write_routines as wr 
## arrow and tab are strings for writing files or printing readable output
arrow = '|--->'
tab   = '    '
class derived_type(object):
    def __init__(self, vname, vmod   ##name of variable and mod file
                , dtype  = None      ## name of derived type
                , components = None  ##list of type and component name
                ):
        self.name = vname
        self.mod  = vmod
        self.declaration = vmod
        if dtype == None:
            self.dtype = ''
        else:
            self.dtype = dtype

        if components == None:
            self.components = []
        else :
            self.components = components
        # Flag to see if Derived Type has been analyzed
        self.analyzed = False

    def _add_components(self,li, lines,array,datatype):

        name = li[1]
        n = '%'+name
        ct = 0
        # Need to find the allocation of component
        # to get the bounds.  Necessary for duplicateMod.F90 creation
        if(array):
            for line in lines:
                ct+=1
                #get rid of comments
                line = line.strip().split('!')[0]
                alloc = re.compile(f'^allocate\(this{n}( |\()')
                alloc_name = re.compile(f'^allocate\({self.name}{n}( |\()')
                string_name = f'allocate({self.name}{n}'
                string = f'allocate(this{n}'
                match_alloc = alloc.search(line.lower())
                if match_alloc :
                    line = line.split(';')[0]
                    line = line[len(string):].strip()
                    l = line[0:len(line)-1]
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

    def _print_derived_type(self):
        print("-----------------------------")
        print("variable:",self.name, "from Mod:",self.mod)
        print("type:",self.dtype)
        print("has components:")
        for c in self.components:
            print(c[0],c[1],c[2])


    def analyzeDerivedType(self):
        #
        # This function will open each mod file, find the variable type
        # and fill out the components of the variable
        #
        import subprocess as sp

        found_declartion = False
        clminst = False
        #first need to check if declaration is in elm_instMod
        name = self.name
        cmd = f'grep -in -E "::[[:space:]]*({name})" {elm_files}elm_instMod.F90'
        cmd2 = f'grep -in -E "::[[:space:]]*({name})" {elm_files}dynSubgridDriverMod.F90'
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
            found_declartion = True
            clminst = True
            print(f"declaration in {self.declaration}")
        try:
            ifile = open(elm_files+self.mod+'.F90')
        except:
            print("ERROR: file ",self.mod+'.F90', "not found")
            exit(1)

        ## must find declaration of var
        lines = ifile.readlines()
        var = self.name
        if(not found_declartion):
            for l in lines:
                line = l.strip()
                match = re.search(r'::\s*\b%s\b' %var, line)
                if(match):
                    #find what's in the parentheses
                    par = re.compile("(?<=\()(\w+)(?=\))")
                    m = par.search(line)
                    if(not m): print(line);
                    inner_str = m.group()
                    self.dtype = inner_str
                    found_declartion = True
                    break

        if(not found_declartion):
            print("ERROR:  Couldn't find declaration of", var)
            print("in file",self.mod+'.F90')
            exit(1)

        # Now find definition of type to find components!
        type_start_line = 0
        type_end_line = 0
        contains = "contains"
        ct = 0
        print("============ ",self.name," =================================================")
        for l in lines:
            ct += 1
            match = re.search(r'::\s*\b%s\b' %self.dtype, l.lower())
            if(match):
                type_start_line = ct
            array = False
            if(type_start_line != 0):
                #test to see if we exceeded type definition
                _end1 = re.search(r'\b%s\b' %contains,l)
                _end  = re.search(r'end type',l)
                if(not _end and not _end1):
                    line = l.split('!')[0].strip()
                    data_type = re.compile(r'^(real|integer|logical|character)')
                    m = data_type.search(line)
                    if(m):
                        datatype = m.group()
                        line = line.replace(',',' ')
                        line = line.replace('pointer','')
                        line = line.replace('private','')
                        line = line.replace('public','')
                        line = line.replace('allocatable','')
                        x    = line.split()
                        x[2] = re.sub(r'[^\w]','',x[2])
                        line = line.replace('::',' ')
                        if ':' in line: array = True
                        self._add_components([x[0],x[2]],lines,array,datatype=datatype)
                else:
                    type_end_line = ct
                    break
        ifile.close()
        self.analyzed = True

    def _create_write_read_functions(self, rw,ofile):
        #
        # This function will write two .F90 functions
        # that write read and write statements for all
        # components of the derived type
        #
        # rw is a variable that holds either read or write mode
        #
        spaces = "     "
        fates_list = ["veg_pp\%is_veg","veg_pp\%is_bareground","veg_pp%wt_ed"]
        if(rw.lower() == 'write' or rw.lower() == 'w'):
            ofile.write(spaces+'\n')
            ofile.write(spaces+'!====================== {} ======================!\n'.format(self.name))
            ofile.write(spaces+'\n')

            for component in self.components:
                if component[0] == False:  continue
                c13c14 = bool('c13' in component[1] or 'c14' in component[1])
                if(c13c14): continue
                fname = self.name+'%'+component[1]
                if(fname in fates_list): continue

                str1 = 'write (fid, "(A)") "{}" \n'.format(fname)
                str2 = 'write (fid, *) {}\n'.format(fname)
                ofile.write(spaces + str1)
                ofile.write(spaces + str2)

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



