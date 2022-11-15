def resolve_interface(sub,iname,args,varlist,verbose=False):
    """
    Determines which subroutine in an interface is being called.
    """
    import subprocess as sp 
    import re 
    import sys 
    from utilityFunctions import Variable,getLocalVariables
    from analyze_subroutines import find_file_for_subroutine, Subroutine
    from mod_config import _bc, elm_files

    if(verbose): print(_bc.FAIL+f"Resolving interface for {iname}\n with args: {args}")
    cmd = f'grep -in -E "^[[:space:]]+(interface {iname})" {elm_files}*.F90'
    output = sp.getoutput(cmd)

    # Get file and line number for interface
    _str = output.replace(elm_files,'') 

    # list that goes:  [filename, linenumber, interface {iname}]
    fn, ln, pattern = _str.split(':')
    if(verbose): print(fn,ln,pattern+_bc.ENDC)
    ln = int(ln) 

    # Read file:
    ifile = open(elm_files+fn,'r')
    lines = ifile.readlines() 
    ifile.close()
    # If one of the arguments is a derived type, then that will have to be analyzed:
    for arg in args: 
        if("%" in arg):
            print(_bc.WARNING+f"Encountered {arg} as an argument!!"+_bc.ENDC)
            sys.exit()
    
    # Get list of possible procedures within the interface 

    regex_end = re.compile(f"^\s*(end)\s+(interface)",re.IGNORECASE)
    regex_procedure = re.compile(r'^\s*(module)\s+(procedure)\s+',re.IGNORECASE)
    
    subroutines = [] # list of subroutine names in the interface 
    ct = ln-1
    in_interface = True
    while(in_interface):
        m_end = regex_end.search(lines[ct])
        if(m_end):
            in_interface = False
        else:
            m_proc = regex_procedure.search(lines[ct])
            if(m_proc):
                subname = lines[ct].replace(m_proc.group(),'').strip()
                subroutines.append(subname) 
        ct += 1 
    
    print(_bc.OKGREEN+f"Number of Args :",len(args))
    
    l_args = [] # list to hold arguments as Variables
    special = "xx" # Special data type used for arguments that are math expressions so either int or real

    # Go through each argument and create an appropiate Variable instance for it
    # to be compared to the dummy arguments of each subroutine in the list above.
    for arg in args:

        found = False # Flag to quickly go to next argument 

        # Check global associate variables
        # if arg is an associated global variable 
        # then the type is already known 
        if(arg in sub.associate_vars):
            vname, comp = sub.associate_vars[arg][0].split("%")
            for v in varlist:
                if(vname == v.name):
                    for c in v.components: 
                        if(comp == c[1]):
                            bounds = c[2] 
                            m = re.search(f"(?<=beg)[a-z]",bounds)
                            dim = bounds.count(',')+1
                            newvar = Variable(type=c[3],name=arg,subgrid=m.group(),ln=0,dim=dim)
                            l_args.append(newvar)
                            found = True
                            break 
        
        if(found): continue
        # Check for keyword argument -- will be matched below
        if('=' in arg):
            l_args.append(Variable(type="?",name=arg,subgrid="?",ln="?",dim="?"))
            continue 
        # Check arguments first:
        for vname,var in sub.Arguments.items():
            if(arg.lower() == var.name.lower()):
                print(f"Matched {arg} to {var.name}")
                l_args.append(var)
                found = True
                break
        if(found): continue

        # Check local variables, arrays :
        for vname, var in sub.LocalVariables['arrays'].items(): 
            if(arg.lower() == var.name.lower()):
                print(f"Matched {arg} to {var.name}")
                l_args.append(var)
                found = True 
                break
        if(found): continue 

        # Check local variables, scalars:
        for var in sub.LocalVariables['scalars']:
            if(arg.lower() == var.name.lower()):
                print(f"Match {arg} to {var.name}")
                l_args.append(var)
                found = True
                break 
        if(found): continue 
        
        if(not found):
            # Couldn't match so arg is assumed to be a math expression
            # Assuming it's equivalent to an integer or real then
            print(f"Couldn't match {arg} -- Setting to int/real")
            l_args.append(Variable(type=special,name=arg,subgrid='',ln=0,dim=0))
    
    num_input_args = len(l_args)
    
    resolved_sub_name = '' # subroutine name that is returned by this function.

    # Instantiate subroutines for interface procedures
    for s in subroutines:
        print("resolve_interface :: ")
        fn1,startline,endline = find_file_for_subroutine(name=s,fn=fn,ignore_interface=True)
        testsub = Subroutine(s,fn1,calltree=sub.calltree,start=startline,end=endline,ignore_interface=True)
        x = getLocalVariables(testsub,verbose=False)
        
        # Go through each argument and check if 
        # it can be matched to this subroutine's allowed args
        matched = match_input_arguments(l_args,testsub,special,verbose=verbose)
        
        # Check if this subroutine is a match or not 
        if(sum(matched) == num_input_args):
            if(verbose): print(f"Subroutine is {s}"+_bc.ENDC)
            resolved_sub_name = s
            child_sub = testsub

            break
    return resolved_sub_name, child_sub

def match_input_arguments(l_args, sub,special,verbose=False):
    """
    function that matches the args to the corresponding dummy args
    of the subroutine.
    """
    import sys 

    if(not sub.Arguments): 
        sys.exit(f"match_input_arguments:: Error - must first parse variables for {sub.name}")
    
    test_args = [v for v in sub.Arguments.values()]
    
    num_input_args = len(l_args)

    # Get number of optional arguments
    num_optional_args = 0 
    for arg in test_args:
        if(arg.optional): num_optional_args += 1
    if(verbose): print(f"\n{sub.name}:: {num_optional_args} Optional arguments found")
    
     # Keep track of which args can be matched.
    matched = [False]*num_input_args
    matching = True

    # Simple check regarding number of arguments first:
    num_dummy_args = len(test_args)
    if(num_input_args > num_dummy_args): 
        return matched  # Too many arguments 
    if(num_input_args < num_dummy_args - num_optional_args): 
        return matched # not enough arguments 
    
    # get list of arg names for keyword comparsions
    test_arg_names = [k for k in sub.Arguments.keys()]
   
    argn = 0 # argument number 
    skip = 0 # keep track of skipped optional arguments

    # Go through each input arg and see if it can be matched to a dummy arg
    while(matching and argn < num_input_args and argn+skip < num_dummy_args):
        input_arg = l_args[argn]
        
        if("=" in input_arg.name):
            # Note this is not sufficient for subroutines 
            # that are differentiated only by dummy arg type 
            # but have same names
            test = input_arg.name
            keyword, varname = test.split("=")
            keyword = keyword.strip()
            varname = varname.strip()
            if(keyword in test_arg_names):
                if(verbose): print(f"{sub.name} accepts {keyword} as keyword")
                matched[argn] = True
                argn += 1
                continue
            else:
                if(verbose): print(f"{sub.name} doesn't support {keyword} as keyword")
                matching = False 
                continue 

        dummy_arg = test_args[argn]
        # check type and dimension:
        same_type = bool(input_arg.type == dummy_arg.type)
        if(not same_type and input_arg.type == special): 
            if(dummy_arg.type in ['real','integer']):
                same_type = True 
        
        same_dim  = bool(input_arg.dim == dummy_arg.dim)
        if(same_type and same_dim):
            # This variable should correspond 
            # to this dummy argument
            if(verbose): print(f"{input_arg.name} matches {dummy_arg.name}")
            matched[argn] = True 
            argn += 1 # go to next argument
        else:
            if(verbose): print(f"{input_arg.name} {input_arg.type} {input_arg.dim}")
            if(verbose): print(f" does not match {dummy_arg.name} {dummy_arg.type} {dummy_arg.dim}")
            # Check to see if dummy_arg is optional 
            # If it is optional, then cycle through the
            # rest of the variables (which should all be optional right?)
            # Assuming no keywords are used
            if(dummy_arg.optional): 
                if(verbose): print(f"{dummy_arg.name} argument is optional and did not match -- Skipping")
                skip += 1 
            else: 
                # This subroutine is not a match 
                matching = False
    # return matched array
    return matched