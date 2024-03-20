"""
This python file is setup to parse global variable information of ELM code.
"""
public = 1
private = 0

class GlobalVariable(object):
    def __init__ (self,
                  var,       #variable name
                  type,      #variable type
                  dim,       #dimension (scalar = 0)
                  parameter, #bool for if it is parameter
                  access,    #public or private (1,0)
                  file       #file variable is declared in
                  ):
        self.var = var
        self.type = type
        self.dim  = dim
        self.parameter = parameter
        self.access = access
        self.file = file
    def _print_var(self):
        if(self.parameter):
            print(f"{self.file}::{self.type} parameter {self.var}")
        else:
            if(self.dim>0):
                print(f"{self.file}::{self.type} {self.var} {self.dim}-D")
            else:
                print(f"{self.file}::{self.type} {self.var}")


def find_global_variables(file, vars_d ):
    import re
    from mod_config import elm_files
    #open and read in file:
    ifile = open(elm_files+file,'r')
    lines = ifile.readlines()
    print(f"find_global_variables::Opening File {elm_files+file}")
    type_start = False
    for l in lines:
        line = l.split('!')[0] #don't regex Comments
        line = line.strip() #remove leading/trailing whitespace
        line = line.lower()
        match_contains = re.search(r'(^contains)',line)
        if(match_contains): break
        match_type = re.search(r'(^type)', line)
        if(match_type):
            type_start = True
            continue
        if(type_start):
            match_end_type = re.search(r'(^end type)',line)
            if(match_end_type):
                type_start = False
                continue
            continue
        if(not type_start):
            data_type = re.compile(r'^(real|integer|logical|character)')
            match_var = data_type.search(line)
            if(match_var):
                type = match_var.group()
                #split variable declaration
                temp = line.split('::')
                decl = temp[0] #declaration info
                vars  = temp[1] #variable(s) and initilization
                #check if public/private; assume public is default
                if('private' in decl):
                    access = private
                else:
                    access = public
                #check if parameter
                if('parameter' in decl):
                    parameter = True
                else:
                    parameter = False

                #check for arrays
                var_array = re.compile(r'\w+\s*\((.*?)\)')
                check_vars = re.compile(r'[a-zA-Z0-9_]+')
                m = var_array.search(vars)
                if(m):
                    #there is at least one array present
                    while(m):
                        #v is the new variable, need to get dimension info
                        v_with_dims = m.group()
                        dim = v_with_dims.count(':')
                        if(dim == 0):
                            dim = v_with_dims.count(',')+1
                        v = check_vars.search(v_with_dims).group()
                        v = v.strip()
                        if ('null' != v):
                            vars_d[v] = GlobalVariable(
                                      var=v,type=type,
                                      dim=dim, parameter=parameter,
                                      access=access,file=file
                                      )
                        vars = vars.replace(v_with_dims,'')
                        m = var_array.search(vars)

                    m_var = check_vars.findall(vars)
                    if(m_var):
                        #still some variables to collect
                        for v in m_var:
                            if(v in vars_d):
                                print(line)
                                raise NameError(f"ERROR: {v} already exists in dictionary")

                            vars_d[v] = GlobalVariable(
                                          var=v,type=type,
                                          dim=0,parameter=parameter,
                                          access=access,file=file
                                          )

                #end of array if statement
                # get scalar variables
                alnum = '[a-zA-Z0-9_]'
                dec   = '[a-zA-Z0-9._\(\)\s/*+-]'
                assignments = re.compile(f'{alnum}+[\s]*(=)[\s]*{dec}+')
                m_vars = check_vars.search(vars)
                while(m_vars):
                    print(vars)
                    if('=' in vars):
                        # This matches an initialization
                        if(type == 'character'):
                            v = vars.split('=')[0]
                            vars = ''
                            v = v.strip()
                        else:
                            initialization = assignments.search(vars).group()
                            vars = vars.replace(initialization,'')
                            v = initialization.split('=')[0]
                            v = v.strip()
                        if(v in vars_d):
                            print(line)
                            raise NameError(f"ERROR: {v} already exists in dictionary")
                        vars_d[v] = GlobalVariable(
                                  var=v,type=type,dim=0,
                                  parameter=parameter,
                                  access=access,file=file
                                  )
                        m_vars =  check_vars.search(vars)
                    else:
                        # No initialization present
                        v = m_vars.group()
                        if(v in vars_d):
                            print(line)
                            raise NameError(f"ERROR: {v} already exists in dictionary")
                        vars_d[v] = GlobalVariable(
                                  var=v,
                                  type=type,
                                  dim=0,
                                  parameter=parameter,
                                  access=access,
                                  file=file
                                  )
                        vars = vars.replace(v,'')
                        m_vars = check_vars.search(vars)

def find_elm_global_variables():
    """
    This subroutine will go through elm files and
    get the global variables.
    Provides info needed for GPU declarations an generation
    of update routines.
    """
    file = "LakeTemperatureMod"+".F90"
    global_variables = {}
    find_global_variables(file=file,vars_d=global_variables)
    for v in global_variables.values():
        v._print_var()

if __name__ == '__main__':
    find_elm_global_variables()
