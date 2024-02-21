class FortranModule:
    """
    A class to represent a Fortran module. 
    Main purpose is to store other modules required to
    compile the given file. To be used to determine the 
    order in which to compile the modules.
    """
    def __init__(self, name, fname):
        self.name = name      # name of the module
        self.global_vars = [] # any variables declared in the module
        self.subroutines = [] # any subroutines declared in the module
        self.modules = []     # any modules used in the module
        self.filepath = fname # the file path of the module

    def display_info(self):
        print(f"Module Name: {self.name}")
        print("Variables:")
        for variable in self.variables:
            print(f"- {variable}")