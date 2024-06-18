import subprocess as sp
from mod_config import ELM_SRC,SHR_SRC, _bc

def get_module_name_from_file(fpath):
    """
    Given a file path, returns the name of the module
    """
    cmd = f'grep -rin -E "^[[:space:]]*module [[:space:]]*[[:alnum:]]+" {fpath}' 
    # the module declaration will be the first one. Any others will be interfaces
    module_name = sp.getoutput(cmd).split("\n")[0]
    linenumber, module_name = module_name.split(":") # grep will have pattern <line_number>:module <module_name>
    module_name = module_name.split(" ")[1] # split by space and get the module name
    
    return int(linenumber), module_name.lower()

def get_filename_from_module(module_name,verbose=False):
    """
    Given a module name, returns the file path of the module
    """
    cmd = f'grep -rin --exclude-dir=external_models/ "module {module_name}" {ELM_SRC}*'
    elm_output = sp.getoutput(cmd)
    if(not elm_output):
        if(verbose): print(f"Checking shared modules...")
        #
        # If file is not an ELM file, may be a shared module in E3SM/share/util/
        #
        cmd = f'grep -rin --exclude-dir=external_models/ "module {module_name}" {SHR_SRC}*'
        shr_output = sp.getoutput(cmd) 
        
        if(not shr_output):
            if(verbose): print(f"Couldn't find {module_name} in ELM or shared source -- adding to removal list")
            file_path = None
        else:
            file_path = shr_output.split('\n')[0].split(':')[0]
    else:
        file_path = elm_output.split('\n')[0].split(':')[0]
    return file_path

def unravel_module_dependencies(modtree,mod_dict,mod,depth=0):
    """
    Recursively go through module dependencies and 
    return an ordered list with the depth at which it is used.
    """
    depth += 1
    for m in mod.modules:
        modtree.append({'module':m,'depth':depth})
        dep_mod = mod_dict[m]
        if(dep_mod.modules):
            modtree = unravel_module_dependencies(modtree=modtree,
                                                  mod_dict=mod_dict,
                                                  mod=dep_mod,depth=depth)

    return modtree

def print_spel_module_dependencies(mod_dict,subs,depth=0):
    """
    Given a dictionary of modules needed for this unit-test
    this prints their dependencies with the modules containing 
    subs being the parents
    """
    arrow = '-->'
    modtree = []

    for sub in subs.values():
        depth = 0
        linenumber, module_name = get_module_name_from_file(sub.filepath)
        sub_module = mod_dict[module_name]
        modtree.append({'module':module_name,'depth':depth})
        print(f"1st module {module_name}")
        depth += 1
        for mod in sub_module.modules:
            modtree.append({'module':mod,'depth':depth})
            dep_mod = mod_dict[mod]
            if(dep_mod.modules):
                modtree = unravel_module_dependencies(modtree=modtree,
                                                      mod_dict=mod_dict,
                                                      mod=dep_mod,depth=depth)             
class FortranModule:
    """
    A class to represent a Fortran module. 
    Main purpose is to store other modules required to
    compile the given file. To be used to determine the 
    order in which to compile the modules.
    """
    def __init__(self, name, fname,ln):
        self.name = name        # name of the module
        self.global_vars = []   # any variables declared in the module
        self.subroutines = []   # any subroutines declared in the module
        self.modules = []       # any modules used in the module
        self.filepath = fname   # the file path of the module
        self.ln = ln            # line number of start module block
        self.defined_types = {} # user types defined in the module 

    def display_info(self,ofile=None):
        if(ofile):
            ofile.write(f"Module Name: {self.name}\n")
            ofile.write(f"Module Depedencies:\n")
        else:
            print(_bc.BOLD+_bc.HEADER+f"Module Name: {self.name}"+_bc.ENDC)
            print(_bc.BOLD+_bc.WARNING+f"Module Depedencies"+_bc.ENDC)

        for module in self.modules:
            if(ofile): 
                ofile.write(f"used {module}\n")
            else:
                print(_bc.WARNING+f"used {module}"+_bc.ENDC)
            
        if(not ofile):
            print(_bc.BOLD+_bc.OKBLUE+"Variables:"+_bc.ENDC)
        else: 
            ofile.write(f"Variables:\n")

        for variable in self.global_vars:
            variable.printVariable(ofile=ofile)
        
        if(ofile): 
            ofile.write(f"User Types:\n")
        else:
            print(_bc.BOLD+_bc.OKBLUE+"User Types:"+_bc.ENDC)
        for utype in self.defined_types:
            self.defined_types[utype].print_derived_type(ofile=ofile)