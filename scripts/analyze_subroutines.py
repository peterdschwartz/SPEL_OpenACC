import os.path
import re
import sys

from helper_functions import (ReadWrite, SubroutineCall,
                              determine_argvar_status, determine_level_in_tree,
                              determine_variable_status,
                              summarize_read_write_status,
                              trace_derived_type_arguments)
from interfaces import determine_arg_name, resolve_interface
from log_functions import center_print
from LoopConstructs import Loop, exportVariableDependency
from mod_config import _bc, spel_dir
from process_associate import getAssociateClauseVars
from utilityFunctions import (find_file_for_subroutine, get_interface_list,
                              getArguments, getLocalVariables, line_unwrapper)


class Subroutine(object):
    """
    Class object that holds relevant metadata on a subroutine

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

    def __init__(
        self,
        name,
        file="",
        calltree=[],
        start=0,
        end=0,
        cpp_start=None,
        cpp_end=None,
        cpp_fn=None,
        ignore_interface=False,
        verbose=False,
        lib_func=False,
    ):
        """
        Initalizes the subroutine object:
            1) file for the subroutine is found if not given
            2) calltree is assigned
            3) the associate clause is processed.
        """

        self.name = name
        self.library = lib_func
        if lib_func:
            print(f"Creating Subroutine {self.name} in {file} L{start}-{end}")
        # Find subroutine
        if not ignore_interface:
            if not file and start == 0 and end == 0:
                file, start, end = find_file_for_subroutine(name=name)
                # grep isn't zero indexed so subtract 1 from start and end
                start -= 1
                end -= 1

        self.filepath = file
        self.startline = start
        self.endline = end
        if self.endline == 0 or self.startline == 0 or not self.filepath:
            print(
                f"Error in finding subroutine {self.name} {self.filepath} {self.startline} {self.endline}"
            )
            sys.exit()

        # Initialize call tree
        self.calltree = list(calltree)
        self.calltree.append(name)

        # Initialize arguments and local variables
        self.Arguments = {}  # Order is important here
        self.LocalVariables = {}
        self.LocalVariables["arrays"] = {}
        self.LocalVariables["scalars"] = {}
        self.class_method = False
        self.class_type = None

        # Create another argument dict that stores the read,write status of them:
        self.arguments_read_write = {}

        # Store when the arguments/local variable declarations start and end
        self.var_declaration_startl = 0
        self.var_declaration_endl = 0

        # Compiler preprocessor flags
        self.cpp_startline = cpp_start
        self.cpp_endline = cpp_end
        self.cpp_filepath = cpp_fn

        # Process the Associate Clause
        self.associate_vars = {}
        if not lib_func:
            self.associate_vars, jstart, jend = getAssociateClauseVars(self)
            self.associate_start = jstart
            self.associate_end = jend

        # Retrieve dummy arguments and parse variables
        if not lib_func:
            self.dummy_args_list = self._get_dummy_args()
            getLocalVariables(self, verbose=verbose)

        if self.Arguments:
            if(self.name == "checkdates"):
                print("self.Arguments:",self.Arguments)
            sort_args = {}
            for arg in self.dummy_args_list:
                sort_args[arg] = self.Arguments[arg]
            self.Arguments = sort_args.copy()

        # These 3 dictionaries will be summaries of ReadWrite Status for
        # the FUT subroutines as a whole
        self.elmtype_r = {}
        self.elmtype_w = {}
        self.elmtype_rw = {}
        # This dict holds "global var" : list[ReadWrite] with no processing.
        self.elmtype_access_by_ln = {}

        self.subroutine_call = []
        self.child_Subroutine = {}

        self.acc_status = False
        self.DoLoops = []
        self.analyzed_child_subroutines = False
        self.active_global_vars = {} # non-derived type variables used in the subroutine

    def __repr__(self) -> str:
        return f"Subroutine({self.name})"

    def print_subroutine_info(self, ofile=sys.stdout, long=False):
        """
        Prints the current subroutine metadata that has been collected.
        If `long` is True, then local scalar variables are printed as well.
        """
        tab = "  "
        base_path = "/".join(self.filepath.split("/")[-2:])
        ofile.write(
            _bc.HEADER
            + f"Subroutine {self.name} in {base_path} L{self.startline}-{self.endline}\n"
            + _bc.ENDC
        )

        ofile.write(_bc.WARNING + "Has Arguments:\n" + _bc.ENDC)
        for arg in self.Arguments.values():
            if arg.optional:
                _str = "~" * len(tab)
            else:
                _str = tab
            ofile.write(_bc.OKBLUE + _str + f"{arg}\n" + _bc.ENDC)

        # Print local variables
        ofile.write(_bc.WARNING + "Local Arrays:\n" + _bc.ENDC)
        array_dict = self.LocalVariables["arrays"]
        for arg in array_dict:
            var = array_dict[arg]
            ofile.write(_bc.OKGREEN + f"{tab}{var}\n" + _bc.ENDC)
        if long:
            ofile.write(_bc.WARNING + "Local Scalars:\n")
            for arg in self.LocalVariables["scalars"]:
                ofile.write(f"{tab}{arg}\n")

        # print Child Subroutines
        if self.child_Subroutine:
            ofile.write(_bc.WARNING + "Child Subroutines:\n")
            for s in self.child_Subroutine.values():
                ofile.write(f"{tab}{s.name}\n")
        ofile.write(_bc.ENDC)
        return None

    def _get_dummy_args(self):
        """
        This function returns the arguments the subroutine takes
        for the s
        And then passes it to the getArguments function
        """
        from utilityFunctions import getArguments

        ifile = open(self.filepath, "r")
        lines = ifile.readlines()
        ifile.close()

        ln = self.startline
        full_line,ln = line_unwrapper(lines=lines,ct=ln)

        args = getArguments(full_line)
        return args

    def _get_global_constants(self, constants):
        """
        NOTE: Need to revisit this function
        This function will loop through an ELM F90 file,
        collecting all constants
        """
        const_mods = [
            "elm_varcon",
            "elm_varpar",
            "landunit_varcon",
            "column_varcon",
            "pftvarcon",
            "elm_varctl",
        ]
        file = open(self.filepath, "r")
        lines = file.readlines()
        print(f"opened file {self.filepath}")
        ct = 0
        while ct < len(lines):
            line = lines[ct]
            l = line.strip()
            match_use = re.search(r"^use ", l.lower())
            if match_use:
                l = l.replace(",", " ").replace(":", " ").replace("only", "").split()
                m = l[1]
                if m in const_mods:
                    for c in l[2:]:
                        if c.lower() not in constants[m]:
                            constants[m].append(c.lower())

            ct += 1
        print(constants)

    def _preprocess_file(
        self, main_sub_dict, dtype_dict, interface_list, verbose=False
    ):
        """
        This function will find child subroutines and variables used
        in the associate clause to be used for parsing for ro and wr derived types
            * main_sub_dict : dict of all subroutines for FUT
            * dtype_dict : dict of user type defintions
            * interface_list : contains names of known interfaces
        """
        from mod_config import _bc

        func_name = "_preprocess_file"

        if self.cpp_filepath:
            fn = self.cpp_filepath
        else:
            fn = self.filepath

        file = open(fn, "r")
        lines = file.readlines()
        file.close()
        regex_ptr = re.compile(r"\w+\s*(=>)\s*\w+(%)\w+")
        # Set up dictionary of derived type instances
        global_vars = {}
        for argname, arg in self.Arguments.items():
            if arg.type in dtype_dict.keys():
                global_vars[argname] = dtype_dict[arg.type]

        for typename, dtype in dtype_dict.items():
            for inst in dtype.instances:
                if inst.name not in global_vars:
                    global_vars[inst.name] = dtype

        # Loop through subroutine and find any child subroutines
        if self.cpp_startline:
            if self.associate_end == 0:
                ct = self.cpp_startline
            else:
                # Note: don't differentiate between cpp files and regular files
                #       for location of the associate clause.
                ct = self.associate_end
            endline = self.cpp_endline
        else:
            if self.associate_end == 0:
                ct = self.startline
            else:
                ct = self.associate_end
            endline = self.endline

        # Loop through the routine and find any child subroutines

        while ct < endline:
            line = lines[ct]
            # get rid of comments
            line = line.split("!")[0].strip()
            if not line:
                ct += 1
                continue
            match_ptr = regex_ptr.search(line)
            if match_ptr:
                # A pointer may be mapped to multiple difference global variables (i.e., a case switch)
                # So, each gv is stored as a list instead. This requires extra care when extracting
                # the read/write status.
                ptrname, gv = match_ptr.group().split("=>")
                ptrname = ptrname.strip()
                gv = gv.strip()
                self.associate_vars.setdefault(ptrname, []).append(gv)

            match_call = re.search(r"^call ", line.strip())
            if match_call:
                x = line.strip().replace("(", " ").replace(")", " ").split()
                child_sub_name = x[1].lower()
                ignore = bool(
                    child_sub_name
                    in [
                        "cpu_time",
                        "get_curr_date",
                        "t_start_lnd",
                        "t_stop_lnd",
                        "endrun",
                    ]
                    or "update_vars" in child_sub_name
                    or "_oacc" in child_sub_name
                )
                if ignore:
                    ct += 1
                    continue

                # Get the arguments passed to the subroutine
                l_unwrp, ct = line_unwrapper(lines=lines, ct=ct)

                # args is a list of arguments passed to subroutine
                args = getArguments(l_unwrp)

                # If child sub name is an interface, then
                # find the actual subroutine name corresponding
                # to the main subroutine dictionary
                if child_sub_name in interface_list:
                    child_sub_name, childsub = resolve_interface(
                        self,
                        iname=child_sub_name,
                        args=args,
                        dtype_dict=global_vars,
                        sub_dict=main_sub_dict,
                        verbose=verbose,
                    )
                    if not child_sub_name:
                        print(
                            f"{func_name}::Error couldn't resolve interface for {x[1]}"
                        )
                        self.print_subroutine_info()
                        sys.exit(1)
                    print(f"{func_name}::New child sub name is:", child_sub_name)
                elif "%" in child_sub_name:
                    # TODO: in DerivedType module, add logic to capture any `Alias` => 'function`
                    #       statements to more easily resolve class methods called with
                    #       `call <var>%<alias>()` syntax.
                    print(
                        _bc.WARNING
                        + f"{func_name}::WARNING CALLING CLASS METHOD at {self.name}:L{ct}!\n{l_unwrp}"
                        + _bc.ENDC
                    )
                    var_name, method_name = child_sub_name.split("%")
                    class_type = global_vars[var_name].type_name
                    for test_sub in main_sub_dict.values():
                        if test_sub.class_type == class_type:
                            if method_name in test_sub.name:
                                child_sub_name = test_sub
                                break
                    print(f"{func_name}::Class method is {child_sub_name}")
                else:
                    if child_sub_name not in main_sub_dict:
                        print(
                            _bc.WARNING
                            + f"Warning: {child_sub_name} not in main_sub_dict."
                            + "\nCould be library function?"
                            + _bc.ENDC
                        )
                        childsub = Subroutine(
                            name=child_sub_name,
                            calltree=[],
                            file="lib.F90",
                            start=-999,
                            end=-999,
                            lib_func=True,
                        )
                    else:
                        childsub: Subroutine = main_sub_dict[child_sub_name]

                # Transform args to list of PointerAlias with dummy_arg => passed_var
                if not childsub.library:
                    args_matched = determine_arg_name(
                        matched_vars=args, child_sub=childsub, args=args,
                    )
                    # Store the subroutine call information (name of parent and the arguments passed)
                    subcall = SubroutineCall(self.name, args_matched)
                    if subcall not in childsub.subroutine_call:
                        childsub.subroutine_call.append(subcall)

                # Add child subroutine to the dict if not already present
                child_sub_names = [s for s in self.child_Subroutine.keys()]
                if child_sub_name not in child_sub_names:
                    childsub.calltree = self.calltree.copy()
                    childsub.calltree.append(child_sub_name)
                    self.child_Subroutine[child_sub_name] = childsub
            ct += 1
        return None

    def _check_acc_status(self):
        """
        checks if subroutine already has !$acc directives
        """
        filename = self.filepath
        file = open(filename, "r")
        lines = file.readlines()  # read entire file
        for ct in range(self.startline, self.endline):
            line = lines[ct]
            # checks for any !$acc directives
            match_acc = re.search(r"^[\s]+(\!\$acc)", line)
            if match_acc:
                self.acc_status = True
                return None

    def _analyze_variables(self, sub_dict, global_vars, interface_list, verbose=False):
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
            - Part 3, check rw status of global vars
        """
        func_name = "_analyze_variables"

        if self.cpp_filepath:
            fn = self.cpp_filepath
        else:
            fn = self.filepath

        file = open(fn, "r")
        lines = file.readlines()
        file.close()
        if self.associate_end == 0:
            if self.cpp_startline:
                startline = self.cpp_startline
            else:
                startline = self.startline
        else:
            startline = self.associate_end

        if self.cpp_endline:
            endline = self.cpp_endline
        else:
            endline = self.endline
        # Create regex to match any variable in the associate clause:
        if not self.associate_vars:
            no_associate = True
            ptrname_list = []
        else:
            # associate_vars is a dictionary { ptrname : variable}
            no_associate = False
            ptrname_list = [key for key in self.associate_vars.keys()]
            ptrname_str = "|".join(ptrname_list)
            regex_associated_ptr = re.compile(
                r"\b({})\b".format(ptrname_str), re.IGNORECASE
            )

        regex_dtype_var =  re.compile(r"\w+(?:\(\w+\))?%\w+")
        regex_paren = re.compile(r"\((.+)\)")

        # dtype_accessed is a dictonary to keep track of derived type vars accessed in the subroutine.
        #        {'inst%component' : [ list of ReadWrite ] }
        #  where ReadWrite = namedtuple('ReadWrite',['status','ln'])
        dtype_accessed = {}
        user_type_args = {}
        ct = startline
        while ct < endline:
            line, ct = line_unwrapper(lines, ct)
            line = line.strip().lower()

            # match subroutine call
            match_call = re.search(r"^\s*(call) ", line)
            # Get list of all global variables used in this line and for array of structs, remove index
            match_var = regex_dtype_var.findall(line)
            arr_of_structs = [regex_paren.sub('',mvar) for mvar in match_var]

            # Solution to avoid replacing regex in other functions for now?
            for i,mvar in enumerate(match_var):
                line = line.replace(mvar,arr_of_structs[i])
            match_var = arr_of_structs.copy()

            if not match_call:
                # There are derived types to analyze!
                if match_var:
                    match_var = list(set(match_var))

                    this_var = [v for v in match_var if "this" in v]
                    if this_var:
                        split_map = map(lambda v: v.split("%")[0], match_var)
                        temp = {
                            v: self.Arguments[v]
                            for v in split_map
                            if v in self.Arguments and v not in user_type_args
                        }
                        user_type_args.update(temp)

                    dtype_accessed = determine_variable_status(
                        match_var, line, ct, dtype_accessed, verbose=verbose
                    )

                # Do the same for any variables in the associate clause
                if not no_associate:
                    match_ptrs = regex_associated_ptr.findall(line)
                    if match_ptrs:
                        dtype_accessed = determine_variable_status(
                            match_ptrs, line, ct, dtype_accessed
                        )
            else:
                # Found child subroutine!
                # Dictionary that holds the global variables passed in as arguments
                #       { 'dummy_arg' : 'global variable'}
                vars_passed_as_args = {}
                subname = line.split()[1].split("(")[0]
                if match_var:
                    # Remove duplicates and make regex string for all matched variables
                    match_var = list(set(match_var))
                    # args is a list of values passed to subroutine.
                    args = getArguments(line)

                    # Match Subroutine to name. Resolve interface if necessary
                    if subname in interface_list:
                        subname, child_sub = resolve_interface(
                            self,
                            iname=subname,
                            args=args,
                            dtype_dict=global_vars,
                            sub_dict=sub_dict,
                            verbose=verbose,
                        )
                        if not subname:
                            print(f"{func_name}::Error unresolved interface {subname}")
                            self.print_subroutine_info()
                            sys.exit(1)
                    else:
                        child_sub = sub_dict[subname]

                    # arg_to dtype is a list of PointerAlias(ptr=argname,obj=varname)
                    arg_to_dtype = determine_arg_name(match_var, child_sub, args)
                    vars_passed_as_args = {arg.ptr: arg.obj for arg in arg_to_dtype}

                # Do the same for any variables in the associate clause
                if not no_associate:
                    match_ptrs = regex_associated_ptr.findall(line)
                    if match_ptrs:
                        match_ptrs = list(set(match_ptrs))
                        args = getArguments(line)
                        child_sub = sub_dict[subname]
                        arg_to_dtype = determine_arg_name(match_ptrs, child_sub, args)
                        vars_passed_as_args.update(
                            {arg.ptr: arg.obj for arg in arg_to_dtype}
                        )

                # This function will parse the dummy arguments of child subroutines
                # so that the status of the dtypes matched above can be updated.
                if vars_passed_as_args:
                    updated_var_status = determine_argvar_status(
                        vars_as_arguments=vars_passed_as_args,
                        subname=subname,
                        sub_dict=sub_dict,
                        linenum=ct,
                    )
                    vars_to_update = {
                        key: dtype_accessed[key] + updated_var_status[key]
                        for key in updated_var_status
                        if key in dtype_accessed
                    }

                    dtype_accessed.update(vars_to_update)
                    dtype_accessed.update(
                        {
                            key: val
                            for key, val in updated_var_status.items()
                            if key not in dtype_accessed
                        }
                    )
            ct += 1

        if user_type_args:
            keys_to_replace = [
                key for key in dtype_accessed if key.split("%")[0] in user_type_args
            ]
            passed_args = {key: [] for key in user_type_args}
            for type_arg in user_type_args:
                for subcall in self.subroutine_call:
                    temp = list(
                        {
                            ptrobj.obj: True
                            for ptrobj in subcall.args
                            if ptrobj.ptr == type_arg
                            and ptrobj.obj not in passed_args[type_arg]
                        }
                    )
                    passed_args[type_arg].extend(temp)

            for key in keys_to_replace:
                save_val = dtype_accessed.pop(key)
                var_to_replace = key.split("%")[0]
                for sub_val in passed_args[var_to_replace]:
                    new_key = key.replace(var_to_replace, sub_val)
                    print(key, "=>", new_key)
                    dtype_accessed[new_key] = save_val

        if dtype_accessed:
            for key, values in dtype_accessed.items():
                status_list = [v.status for v in values]
                num_uses = len(status_list)
                num_reads = status_list.count("r")
                num_writes = status_list.count("w")
                var_name_list = []
                if key in ptrname_list:
                    if isinstance(self.associate_vars[key], list):
                        var_name_list = self.associate_vars[key].copy()
                    else:
                        var_name_list.append(self.associate_vars[key])
                else:
                    var_name_list.append(key)
                for varname in var_name_list:
                    if(varname == "solarabs_vars%tlai_patch"):
                        print(f"Subroutine {self.name} Adding {varname}:")
                        sys.exit(0)
                    self.elmtype_access_by_ln[varname] = values
                    if "%" not in varname:
                        print(f"Adding { varname } to elmtype!")
                    if num_uses == num_reads:
                        # read-only
                        self.elmtype_r[varname] = "r"
                    elif num_uses == num_writes:
                        # write-only
                        self.elmtype_w[varname] = "w"
                    else:
                        # read-write
                        self.elmtype_rw[varname] = "rw"

        return None

    def parse_subroutine(self, dtype_dict, main_sub_dict, child=False, verbose=False):
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
        func_name = "parse_subroutine::"

        # Get interfaces
        interface_list = get_interface_list()

        self._preprocess_file(
            main_sub_dict=main_sub_dict,
            dtype_dict=dtype_dict,
            interface_list=interface_list,
            verbose=verbose,
        )

        global_vars = {}
        for argname, arg in self.Arguments.items():
            if arg.type in dtype_dict.keys():
                global_vars[argname] = dtype_dict[arg.type]

        for typename, dtype in dtype_dict.items():
            for inst in dtype.instances:
                if inst.name not in global_vars:
                    global_vars[inst.name] = dtype

        # Determine read/write status of variables
        self._analyze_variables(
            sub_dict=main_sub_dict,
            global_vars=global_vars,
            interface_list=interface_list,
            verbose=verbose,
        )

        # Update main_sub_dict with new parsing information?
        main_sub_dict[self.name] = self

        return None

    def child_subroutines_analysis(self, dtype_dict, main_sub_dict, verbose=False):
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
            if child_sub.library:
                print(
                    f"{func_name}::{child_sub.name} is a library function -- Skipping."
                )
                continue
            if child_sub.name in interface_list:
                print(
                    f"{func_name}::Error: need to resolve interface for {child_sub.name}"
                )
                sys.exit(1)

            child_sub.parse_subroutine(
                dtype_dict=dtype_dict,
                main_sub_dict=main_sub_dict,
                child=True,
                verbose=verbose,
            )

            if child_sub.child_Subroutine:
                if "_oacc" not in child_sub.name:
                    child_sub.child_subroutines_analysis(
                        dtype_dict=dtype_dict,
                        main_sub_dict=main_sub_dict,
                        verbose=verbose,
                    )

            # Figure out if child subroutine is called with derived type arguments
            trace_derived_type_arguments(self, child_sub, verbose=verbose)

            for varname, status in child_sub.elmtype_r.items():
                if(varname == "solarabs_vars%tlai_patch"):
                    print(f"Child Subroutine {child_sub.name} Adding {varname}:")
                    sys.exit(0)
                if varname in self.elmtype_w.keys():
                    # Check if previously write-only and change to read-write
                    self.elmtype_rw[varname] = "rw"
                    self.elmtype_w.pop(varname)
                elif varname in self.elmtype_rw.keys():
                    # No action needed, just continue
                    continue
                elif varname not in self.elmtype_r.keys():
                    # Check if variable is present in parent at all and add if needed
                    self.elmtype_r[varname] = "r"

            for varname, status in child_sub.elmtype_w.items():
                if varname in self.elmtype_r.keys():
                    self.elmtype_rw[varname] = "rw"
                    self.elmtype_w.pop(varname)  # remove from read-only
                elif varname in self.elmtype_rw.keys():
                    continue
                elif varname not in self.elmtype_w.keys():
                    self.elmtype_w[varname] = "w"

            for varname in child_sub.elmtype_rw.keys():
                if varname not in self.elmtype_rw.keys():
                    self.elmtype_rw[varname] = "rw"
                if varname in self.elmtype_r.keys():
                    self.elmtype_r.pop(varname)
                if varname in self.elmtype_w.keys():
                    self.elmtype_w.pop(varname)

        for s in self.child_Subroutine.values():
            self.calltree.append(s.calltree)
            if child_sub in interface_list:
                continue
        self.analyzed_child_subroutines = True

        return None

    def analyze_calltree(self, tree, casename):
        """
        returns unraveled calltree
        """
        tree_to_write = [[self.name, 0]]
        for i in range(0, len(tree)):
            el = tree[i]
            tree_to_write = determine_level_in_tree(
                branch=el, tree_to_write=tree_to_write
            )

        ofile = open(f"{casename}/{self.name}CallTree.txt", "w")
        for branch in tree_to_write:
            level = branch[1]
            sub = branch[0]
            print(level * "|---->" + sub)
            ofile.write(level * "|---->" + sub + "\n")
        ofile.close()

    def generate_update_directives(self, elmvars_dict, verify_vars):
        """
        This function will create .F90 routine to execute the
        update directives to check the results of the subroutine
        """
        ofile = open(
            f"{spel_dir}scripts/script-output/update_vars_{self.name}.F90", "w"
        )

        spaces = " " * 2
        ofile.write("subroutine update_vars_{}(gpu,desc)\n".format(self.name))

        replace_inst = [
            "soilstate_inst",
            "waterflux_inst",
            "canopystate_inst",
            "atm2lnd_inst",
            "surfalb_inst",
            "solarabs_inst",
            "photosyns_inst",
            "soilhydrology_inst",
            "urbanparams_inst",
        ]

        for dtype in verify_vars.keys():
            mod = elmvars_dict[dtype].declaration
            ofile.write(spaces + f"use {mod}, only : {dtype}\n")

        ofile.write(spaces + "implicit none\n")
        ofile.write(spaces + "integer, intent(in) :: gpu\n")
        ofile.write(spaces + "character(len=*), optional, intent(in) :: desc\n")
        ofile.write(spaces + "character(len=256) :: fn\n")
        ofile.write(spaces + "if(gpu) then\n")
        ofile.write(spaces + spaces + f'fn="gpu_{self.name}"\n')
        ofile.write(spaces + "else\n")
        ofile.write(spaces + spaces + f"fn='cpu_{self.name}'\n")
        ofile.write(spaces + "end if\n")
        ofile.write(spaces + "if(present(desc)) then\n")
        ofile.write(spaces + spaces + "fn = trim(fn) // desc\n")
        ofile.write(spaces + "end if\n")
        ofile.write(spaces + 'fn = trim(fn) // ".txt"\n')
        ofile.write(spaces + 'print *, "Verfication File is :",fn\n')
        ofile.write(spaces + "open(UNIT=10, STATUS='REPLACE', FILE=fn)\n")

        # First insert OpenACC update directives to transfer results from GPU-CPU
        ofile.write(spaces + "if(gpu) then\n")
        acc = "!$acc "

        for v, comp_list in verify_vars.items():
            ofile.write(spaces + acc + "update self(&\n")
            i = 0
            for c in comp_list:
                i += 1
                if i == len(comp_list):
                    name = f"{v}%{c}"
                    c13c14 = bool("c13" in name or "c14" in name)
                    if c13c14:
                        ofile.write(spaces + acc + ")\n")
                    else:
                        ofile.write(spaces + acc + f"{name} )\n")
                else:
                    name = f"{v}%{c}"
                    c13c14 = bool("c13" in name or "c14" in name)
                    if c13c14:
                        continue
                    ofile.write(spaces + acc + f"{name}, &\n")

        ofile.write(spaces + "end if\n")
        ofile.write(spaces + "!! CPU print statements !!\n")
        # generate cpu print statements
        for v, comp_list in verify_vars.items():
            for c in comp_list:
                name = f"{v}%{c}"
                c13c14 = bool("c13" in name or "c14" in name)
                if c13c14:
                    continue
                ofile.write(spaces + f"write(10,*) '{name}',shape({name})\n")
                ofile.write(spaces + f"write(10,*) {name}\n")

        ofile.write(spaces + "close(10)\n")
        ofile.write("end subroutine ")
        ofile.close()
        return

    def examineLoops(
        self,
        global_vars,
        varlist,
        main_sub_dict,
        add_acc=False,
        subcall=False,
        verbose=False,
        adjust_allocation=False,
    ):
        """
        Function that will parse the loop structure of a subroutine
        Add loop parallel directives if desired
        """
        from mod_config import _bc
        from utilityFunctions import (determine_filter_access,
                                      find_file_for_subroutine,
                                      get_interface_list, getArguments,
                                      getLocalVariables,
                                      lineContinuationAdjustment)

        interface_list = (
            get_interface_list()
        )  # move this to a global variable in mod_config?
        if not subcall:
            associate_keys = self.associate_vars.keys()
            temp_global_vars = [key for key in associate_keys]
            global_vars = temp_global_vars[:]
        else:
            if self.name not in main_sub_dict:
                main_sub_dict[self.name] = self

        # Check if associated derived types need to be analyzed
        # convertAssociateDict(self.associate_vars,varlist)

        if adjust_allocation:
            # dict with 'arg' : Subroutine
            # where 'arg' is a local array, and 'sub' is child subroutine that uses it.
            passed_to_sub = {}
            local_array_list = [v for v in self.LocalVariables["arrays"]]
            print(f"local_array for {self.name}\n", local_array_list)

        if verbose:
            print(f"Opening file {self.filepath} ")
        ifile = open(self.filepath, "r")
        lines = ifile.readlines()  # read entire file
        ifile.close()

        loop_start = 0
        loop_end = 0
        regex_do = re.compile(r"\s*(do)\s+\w+\s*(?=[=])", re.IGNORECASE)
        regex_dowhile = re.compile(f"\s*(do while)", re.IGNORECASE)
        regex_enddo = re.compile(r"^\s*(end)\s*(do)", re.IGNORECASE)
        regex_subcall = re.compile(r"^(call)", re.IGNORECASE)

        # Starting parsing lines at the subroutine start
        sublines = lines[self.startline - 1 : self.endline]
        loopcount = 0
        print(f"Examing Loops for {self.name}")
        dowhile = False
        lines_to_skip = 0
        for n, line in enumerate(sublines):
            if lines_to_skip > 0:
                lines_to_skip -= 1
                continue
            l, lines_to_skip = lineContinuationAdjustment(sublines, n, verbose)

            # Use RegEx
            m_call = regex_subcall.search(l)
            m_do = regex_do.search(l)
            m_enddo = regex_enddo.search(l)
            m_dowhile = regex_dowhile.search(l)
            if m_dowhile:
                dowhile = True  # Inside do while loop
                if verbose:
                    print("Inside do while loop")
            # If we match subroutine call we should analyze it now so that the
            # DoLoops array has the Loops in order of use.
            #
            if m_call:
                x = l.replace("(", " ").replace(")", " ").split()
                child_sub_name = ""
                ignore_subs = ["cpu_time", "get_curr_date", "endrun", "banddiagonal"]
                if (
                    x[1].lower() not in ignore_subs
                    and "update_vars" not in x[1].lower()
                    and "_oacc" not in x[1].lower()
                ):
                    child_sub_name = x[1]

                    args = getArguments(l)

                    if child_sub_name in interface_list:
                        print("Need to resolve interface!", child_sub_name)
                        sys.exit()
                        child_sub_name, childsub = resolve_interface(
                            self, child_sub_name, args, varlist, verbose=verbose
                        )
                    else:
                        file, startline, endline = find_file_for_subroutine(
                            child_sub_name
                        )
                        childsub = Subroutine(
                            child_sub_name, file, [self.name], startline, endline
                        )

                    # Note that these subroutines have specific versions for
                    # using filter or not using a filter.
                    dont_adjust = [
                        "c2g",
                        "p2c",
                        "p2g",
                        "p2c",
                        "c2l",
                        "l2g",
                        "tridiagonal",
                    ]
                    dont_adjust_string = "|".join(dont_adjust)
                    regex_skip_string = re.compile(
                        f"({dont_adjust_string})", re.IGNORECASE
                    )
                    m_skip = regex_skip_string.search(child_sub_name)

                    if not m_skip:
                        self.update_arg_tree(child_sub_name, args)

                    getLocalVariables(childsub, verbose=verbose)

                    if adjust_allocation:
                        # To adjust memory allocation, need to keep track
                        # of if a Local variable is passed as an argument.
                        # If it's a subcall then must check the arguments as well.
                        for numarg, arg in enumerate(args):
                            if arg in local_array_list:
                                passed_to_sub[arg] = [
                                    childsub,
                                    n + self.startline - 1,
                                    numarg,
                                ]

                        if (
                            subcall
                        ):  # check if an argument is passed to another subroutine
                            arg_list = [v for v in self.Arguments]
                            for arg in args:
                                if arg in arg_list:
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
                    if verbose:
                        print(
                            f"Instantiated new Subroutine {child_sub_name}\n in file {file} L{startline}-{endline}"
                        )

                    childloops = childsub.examineLoops(
                        global_vars=global_vars,
                        varlist=varlist,
                        main_sub_dict=main_sub_dict,
                        subcall=True,
                        verbose=verbose,
                        adjust_allocation=adjust_allocation,
                        add_acc=False,
                    )
                    if verbose:
                        print(f"Adding {len(childloops)} loops from {childsub.name}")
                    self.DoLoops.extend(childloops)
                    self.child_subroutine_list.append(childsub)
                    self.child_Subroutine[child_sub_name] = childsub

            if m_do:
                # get index
                index = m_do.group().split()[1]
                # outer most loop
                if loopcount == 0:
                    if verbose:
                        print(f"============ {self.name} ===============")
                    if verbose:
                        print("New loop at line ", n + self.startline)
                    loop_start = n + self.startline
                    newloop = Loop(loop_start, index, self.filepath, self)
                else:
                    # Found an inner loop
                    newloop.index.append(index)
                    loop_start = n + self.startline
                    newloop.nested += 1
                    newloop.start.append(loop_start)
                    newloop.end.append(0)
                loopcount += 1

            if m_enddo:
                if dowhile:
                    dowhile = False
                    if verbose:
                        print(
                            _bc.WARNING
                            + f"Do while loop in {self.name} ends at {n+self.startline}"
                            + _bc.ENDC
                        )
                    continue
                loopcount -= 1
                if loopcount == 0:
                    if verbose:
                        print("end of outer loop at ", n + self.startline)
                    loop_end = n + self.startline
                    # append loop object:
                    newloop.end[loopcount] = loop_end
                    lstart = newloop.start[0] - self.startline
                    lend = loop_end - self.startline

                    newloop.lines = sublines[lstart : lend + 1]
                    self.DoLoops.append(newloop)
                else:
                    loop_end = n + self.endline
                    newloop.end[loopcount] = loop_end

        # Parse variables used in Loop
        print(f"Parsing variables for Loops in {self.name}")
        for n, loop in enumerate(self.DoLoops):
            if loop.subcall.name is self.name:
                # loops in child subroutines have already been Parsed!
                loop.parseVariablesinLoop(verbose=verbose)
                if loop.reduction:
                    print("loop may contain a race condition:", loop.reduce_vars)

        if adjust_allocation:
            determine_filter_access(self, verbose=False)
            # Check and fix !$acc enter/exit data directives for the subroutine
            self.generate_unstructured_data_regions()

        if subcall:
            return self.DoLoops

        # Create dictionary to hold subroutines found so far
        # and their initial startlines to help adjust for line insertions later.
        sub_dict = {}
        # dictionary of the loops to avoid adding OpenACC directives to the same
        # Loop more than once
        loop_dict = {}
        num_reduction_loops = 0
        ofile = open(f"loops-{self.name}.txt", "w")
        for loop in self.DoLoops:
            loopkey = f"{loop.subcall.name}:L{loop.start[0]}"
            if loopkey not in loop_dict:
                loop_dict[loopkey] = loop
                if loop.reduction:
                    print(
                        _bc.BOLD
                        + _bc.WARNING
                        + f"{loopkey} {loop.reduce_vars}"
                        + _bc.ENDC
                    )
                    ofile.write(f"{loopkey} {loop.reduce_vars}" + "\n")
                    num_reduction_loops += 1
                else:
                    print(loopkey)
                    ofile.write(loopkey + "\n")
            if loop.subcall.name not in sub_dict:
                file, startline, endline = find_file_for_subroutine(loop.subcall.name)
                sub_dict[loop.subcall.name] = startline
        loopids = [k for k in loop_dict.keys()]
        print(
            _bc.OKGREEN
            + f"{len(loopids)} | {num_reduction_loops} w/ Race Conditions"
            + _bc.ENDC
        )
        ofile.write(f"{len(loopids)} | {num_reduction_loops} w/ Race Conditions" + "\n")

        ofile.close()
        count = 0
        for s in main_sub_dict.values():
            arrs = s.LocalVariables["arrays"]
            for arr in arrs:
                v = arrs[arr]
                if "num_" in v.declaration:
                    count += 1
                    print(f"{count}  {s.name}::{v.name} -- {v.declaration}")
        if add_acc:
            lines_adjusted = {}
            for key, loop in loop_dict.items():
                if loop.subcall.name not in lines_adjusted:
                    # This keeps track of the number of line adjustments
                    # inside a given subroutine.  The start of the subroutine
                    # is rechecked inside addOpenACCFlags function
                    lines_adjusted[loop.subcall.name] = 0
                file, startline, endline = find_file_for_subroutine(loop.subcall.name)
                subline_adjust = startline - sub_dict[loop.subcall.name]
                loop.addOpenACCFlags(lines_adjusted, subline_adjust, key)

        # Note: Can't use List Comprehension here with class attributes
        var_list = []
        local_vars_only = []
        for loop in self.DoLoops:
            for key in loop.vars.keys():
                var_list.append(key)
                if key not in global_vars:
                    local_vars_only.append(key)

        var_list = list(dict.fromkeys(var_list).keys())
        local_vars_only = list(dict.fromkeys(local_vars_only).keys())

        # print only the global variable list:
        global_loop_vars = []
        all_array_vars = []
        for v in var_list:
            if v in global_vars or "filter" in v:
                global_loop_vars.append(v)

        exportVariableDependency(
            self.name,
            var_list,
            global_loop_vars,
            local_vars_only,
            self.DoLoops,
            mode="",
        )

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
        # read variables
        print("============= exportReadWriteVariables ===================")
        print(self.elmtype_r)
        for varname, components in self.elmtype_r.items():
            for c in components:
                var = f"{varname}%{c}"
                read_flat.append(var)
                all_flat.append(var)
                if len(var) > maxlen:
                    maxlen = len(var)

        for varname, components in self.elmtype_w.items():
            for c in components:
                var = f"{varname}%{c}"
                write_flat.append(var)
                if len(var) > maxlen:
                    maxlen = len(var)
                if var not in all_flat:
                    all_flat.append(var)

        output_list = []
        # header
        ofile = open(f"{self.name}-ReadWriteVars.dat", "w")
        header = f"{'Variable':<{maxlen}} {'Status':5}"
        output_list.append(header)
        ofile.write(header + "\n")
        for var in all_flat:
            status = ""
            if var in read_flat:
                status += "r"
            if var in write_flat:
                status += "w"
            if len(status) < 2:
                status += "o"
            string = f"{var:<{maxlen}} {status:5}\n"
            ofile.write(string)
        ofile.close()

        return None

    def update_arg_tree(self, childsubname, args):
        """
        Checks if any of the subroutines arguments
        or local variables are passed to any subroutines.
        """
        from mod_config import _bc

        print(_bc.HEADER)
        print(f"update_arg_tree::{self.name} called {childsubname} w/ args {args}")
        print(_bc.ENDC)

        arrays = self.LocalVariables["arrays"]

        for v in args:
            if "=" in v:
                kw, var = v.split("=")
                kw = kw.strip()
                var = var.strip()
                if var not in arrays:
                    continue
                self.LocalVariables["arrays"][var].keyword = kw
                self.LocalVariables["arrays"][var].subs.append(childsubname)
                self.VariablesPassedToSubs.setdefault(childsubname, []).append(
                    self.LocalVariables["arrays"][var]
                )
            else:
                var = v.strip()
                if var not in arrays:
                    continue
                self.LocalVariables["arrays"][var].keyword = ""
                self.LocalVariables["arrays"][var].subs.append(childsubname)
                self.VariablesPassedToSubs.setdefault(childsubname, []).append(
                    self.LocalVariables["arrays"][var]
                )

    def generate_unstructured_data_regions(self, remove=True) -> None:
        """
        Function generates appropriate enter and exit data
        directives for the local variables of this Subroutine.

        First step is to remove any existing directives
        Next, create new directives from local variable list
        Compare new and old directives and overwrite if they are different
        """
        # Open File:
        if os.path.exists(spel_dir + "modified-files/" + self.filepath):
            print("Modified file found")
            print(
                _bc.BOLD
                + _bc.WARNING
                + f"Opening file "
                + spel_dir
                + "modified-files/"
                + self.filepath
                + _bc.ENDC
            )
            ifile = open(spel_dir + "modified-files/" + self.filepath, "r")
        else:
            print(_bc.BOLD + _bc.WARNING + f"Opening file{self.filepath}" + _bc.ENDC)
            ifile = open(self.filepath, "r")

        lines = ifile.readlines()

        ifile.close()

        regex_enter_data = re.compile(r"^\s*\!\$acc enter data", re.IGNORECASE)
        regex_exit_data = re.compile(r"^\s*\!\$acc exit data", re.IGNORECASE)

        lstart = self.startline - 1
        lend = self.endline
        old_enter_directives = []
        old_exit_directives = []
        if remove:
            ln = lstart
            while ln < lend:
                line = lines[ln]
                match_enter_data = regex_enter_data.search(line)
                match_exit_data = regex_exit_data.search(line)
                if match_enter_data:
                    directive_start = ln
                    old_enter_directives.append(line)  # start of enter data directive
                    line = line.rstrip("\n")
                    line = line.strip()
                    while line.endswith("&"):
                        ln += 1
                        line = lines[ln]
                        old_enter_directives.append(line)  # end of enter data directive
                        line = line.rstrip("\n")
                        line = line.strip()
                    directive_end = ln
                    del lines[directive_start : directive_end + 1]
                    num_lines_removed = directive_end - directive_start + 1
                    lend -= num_lines_removed
                    ln -= num_lines_removed
                    print(f"Removed {num_lines_removed} enter data lines")
                if match_exit_data:
                    directive_start = ln  # start of exit data directive
                    old_exit_directives.append(line)
                    line = line.rstrip("\n")
                    line = line.strip()
                    while line.endswith("&"):
                        ln += 1
                        line = lines[ln]
                        old_exit_directives.append(line)
                        line = line.rstrip("\n")
                        line = line.strip()
                    directive_end = ln  # end of exit data directive
                    del lines[directive_start : directive_end + 1]
                    num_lines_removed = directive_end - directive_start + 1
                    lend -= num_lines_removed
                    ln -= num_lines_removed
                    print(f"Removed {num_lines_removed} exit data lines")
                ln += 1

        # Create New directives
        vars = []  # list to hold all vars needed to be on the device
        arrays_dict = self.LocalVariables["arrays"]
        for k, v in arrays_dict.items():
            varname = v.name
            dim = v.dim
            li_ = [":"] * dim
            dim_str = ",".join(li_)
            dim_str = "(" + dim_str + ")"
            print(f"adding {varname}{dim_str} to directives")
            vars.append(f"{varname}{dim_str}")

        # Only add scalars to if they are a reduction variables
        # Only denoting that by if it has "sum" in the name
        for v in self.LocalVariables["scalars"]:
            varname = v.name
            for loop in self.DoLoops:
                if loop.subcall.name == self.name:
                    if varname in loop.reduce_vars and varname not in vars:
                        print(f"Adding scalar {varname} to directives")
                        vars.append(varname)

        num_vars = len(vars)
        if num_vars == 0:
            print(f"No Local variables to make transfer to device, returning")
            return None
        else:
            print(f"Generating create directives for {num_vars} variables")

        # Get appropriate indentation for the new directives:
        padding = ""
        first_line = 0

        for ln in range(lstart, lend):
            line = lines[ln]
            # Before ignoring comments, check if it's an OpenACC directive
            m_acc = re.search(r"\s*(\!\$acc routine seq)", line)
            if m_acc:
                sys.exit("Error: Trying to add data directives to an OpenACC routine")

            m_acc = re.search(
                r"\s*(\!\$acc)\s+(parallel|enter|update)", line, re.IGNORECASE
            )
            if m_acc and first_line == 0:
                first_line = ln

            l = line.split("!")[0]
            l = l.strip()
            if not l:
                continue

            m_use = re.search(
                r"^(implicit|use|integer|real|character|logical|type\()", line.lstrip()
            )
            if m_use and not padding:
                padding = " " * (len(line) - len(line.lstrip()))
            elif padding and not m_use and first_line == 0:
                first_line = ln

            if ln == lend - 1 and not padding:
                sys.exit("Error: Couldn't get spacing")

        new_directives = []

        for v in vars[0 : num_vars - 1]:
            new_directives.append(padding + f"!$acc {v}, &\n")
        new_directives.append(padding + f"!$acc {vars[num_vars-1]})\n\n")

        new_enter_data = [padding + "!$acc enter data create(&\n"]
        new_enter_data.extend(new_directives)
        #
        new_exit_data = [padding + "!$acc exit data delete(&\n"]
        new_exit_data.extend(new_directives)

        if (
            new_enter_data != old_enter_directives
            or new_exit_data != old_exit_directives
        ):
            # Insert the enter data directives
            if self.associate_end != 0:
                # insert new directives just after last associate statement:
                for l in reversed(new_enter_data):
                    lines.insert(self.associate_end + 1, l)
            else:  # use first_line found above
                for l in reversed(new_enter_data):
                    lines.insert(first_line, l)
            lend += len(new_enter_data)
            print(
                _bc.BOLD + _bc.WARNING + f"New Subroutine Ending is {lend}" + _bc.ENDC
            )
            # Inster the exit data directives
            if self.associate_end != 0:
                end_associate_ln = 0
                regex_end = re.compile(r"^(end associate)", re.IGNORECASE)
                for ln in range(lend, lstart, -1):
                    m_end = regex_end.search(lines[ln].lstrip())
                    if m_end:
                        end_associate_ln = ln
                        break
                for l in reversed(new_exit_data):
                    lines.insert(end_associate_ln, l)
            else:
                for l in reversed(new_exit_data):
                    lines.insert(lend - 1, l)
            lend += len(new_exit_data)
            print(
                _bc.BOLD + _bc.WARNING + f"New Subroutine Ending is {lend}" + _bc.ENDC
            )

            # Overwrite File:
            if "modified-files" in self.filepath:
                print(
                    _bc.BOLD
                    + _bc.WARNING
                    + f"Writing to file {self.filepath}"
                    + _bc.ENDC
                )
                ofile = open(self.filepath, "w")
            else:
                print(
                    _bc.BOLD
                    + _bc.WARNING
                    + f"Writing to file "
                    + spel_dir
                    + "modified-files/"
                    + self.filepath
                    + _bc.ENDC
                )
                ofile = open(spel_dir + "modified-files/" + self.filepath, "w")

            ofile.writelines(lines)
            ofile.close()
        else:
            print(_bc.BOLD + _bc.WARNING + "NO CHANGE" + _bc.ENDC)
        return None

    def parse_arguments(self, sub_dict, verbose=False):
        """
        Function that will analyze the variable status for only the arguments
            'sub.arguments_read_write' : { `arg` : `list of ReadWrite status`}
        where,
            ReadWrite = namedtuple("ReadWrite", ["status", "ln"])

        NOTE: Ideally, this should just be a mode of the original _analyze_variables function
              as much of it is duplicated. 1st, get this working for as intended.
              Then do the re-factor taking care that nothing is broken in the process.
        """
        func_name = "parse_args::"

        # intrinsic_types = ["real", "integer", "character", "logical"]
        args_to_match = [
            arg for arg, var in self.Arguments.items()  # if var.type in intrinsic_types
        ]
        arg_match_string = "|".join(args_to_match)
        regex_args = re.compile(r"\b({})\b".format(arg_match_string), re.IGNORECASE)
        regex_ptr = re.compile(r"\w+\s*(=>)\s*({})(%)\w+".format(arg_match_string))

        arg_line_numbers = [var.ln for var in self.Arguments.values()]
        max_arg_ln = max(arg_line_numbers)

        # loop through subroutine lines
        if self.cpp_filepath:
            fn = self.cpp_filepath
        else:
            fn = self.filepath

        file = open(fn, "r")
        lines = file.readlines()
        file.close()
        if self.associate_end == 0:
            if self.cpp_startline:
                delta_ln = self.startline - self.cpp_startline
                startline = max_arg_ln - delta_ln + 1
            else:
                startline = max_arg_ln + 1
        else:
            startline = self.associate_end

        if self.cpp_endline:
            endline = self.cpp_endline
        else:
            endline = self.endline

        debug = False 

        args_accessed = {}
        line_num = startline
        while line_num < endline:
            line, line_num = line_unwrapper(lines, line_num)
            line = line.strip().lower()

            # match subroutine call - will require recursive `parse_arguments`
            match_call = re.search(r"^\s*(call) ", line)
            match_arg_use = regex_args.findall(line)

            # Need checks to make sure we are
            if match_arg_use:
                if not match_call:
                    # check if a Derived Type argument is being associated with another ptr
                    # I do not _think_ that we need to capture this alias as in this routine
                    # we are interested in how the argument in used.
                    match_ptr = regex_ptr.search(line)
                    if(match_ptr):
                        line_num +=1
                        continue

                    match_arg_use = list(set(match_arg_use))
                    args_accessed = determine_variable_status(
                        match_arg_use, line, line_num, args_accessed, verbose=verbose
                    )
                    if not args_accessed:
                        print(_bc.FAIL+f"{func_name}::Failed to finds args ", match_arg_use,_bc.ENDC)
                        print(self.name,line_num, line)
                        sys.exit(1)

                else:
                    # Case of argument being passed to another subroutine:
                    subname: str = line.split()[1].split("(")[0]
                    child_sub: Subroutine = sub_dict[subname]
                    if not child_sub.arguments_read_write:
                        child_sub.parse_arguments(sub_dict, verbose=verbose)

                    new_passed_args = getArguments(line)

                    arg_to_dtype = determine_arg_name(
                        match_arg_use, child_sub, new_passed_args
                    )

                    inactive_args = [
                        arg_var.ptr
                        for arg_var in arg_to_dtype
                        if arg_var.ptr not in child_sub.arguments_read_write.keys()
                    ]
                    if inactive_args:
                        arg_to_dtype = [
                            arg for arg in arg_to_dtype 
                            if arg.ptr not in inactive_args
                        ]
                    for arg_var in arg_to_dtype:
                        argname = arg_var.ptr
                        dtypename = arg_var.obj
                        arg_status = child_sub.arguments_read_write[argname].status
                        if(isinstance(arg_status, ReadWrite)):
                            print(f"ERROR:{argname} has nested ReadWrite from {child_sub.name}")
                            sys.exit()
                        arg_status = ReadWrite(status=arg_status, ln=line_num)
                        args_accessed.setdefault(dtypename, []).append(arg_status)
            line_num += 1

        # All args should have been processed. Store information into Subroutine
        arg_status_summary = summarize_read_write_status(args_accessed)
        for arg, status in arg_status_summary.items():
            self.arguments_read_write[arg] = ReadWrite(status, -999)

        # Make sure arguments were found
        if not self.arguments_read_write:
            print(f"{func_name}::ERROR: Failed to analyze arguments for {self.name}")
            sys.exit(1)
        return None
    
    def print_elmtype_access(self):
        """
        Function to print the read/write status of all derived type members
        """
        func_name = "print_elmtype_access"
        print(_bc.OKGREEN + f"Derived Type Analysis for {self.name}")
        print(f"{func_name}::Read-Only")
        for key in self.elmtype_r.keys():
            print(key, self.elmtype_r[key])
        print(f"{func_name}::Write-Only")
        for key in self.elmtype_w.keys():
            print(key, self.elmtype_w[key])
        print(f"{func_name}::Read-Write")
        for key in self.elmtype_rw.keys():
            print(key, self.elmtype_rw[key])
        print(_bc.ENDC)
        return None 
