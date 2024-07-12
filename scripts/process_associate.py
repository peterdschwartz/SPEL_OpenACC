import re
import sys
from utilityFunctions import line_unwrapper
def getAssociateClauseVars(sub, verbose=False):
    """
    Funtion to extract the associated variables in a subroutine 

    NOTE: Move to Subroutine Class?
    """
   
    func_name = "getAssociateClauseVars"
    iofile = open(sub.filepath, 'r')
    # status intitialized to False -- routine needs analysis
    lines = iofile.readlines()
    iofile.close()
    subroutine_name = sub.name
    subroutine_start_line = sub.startline
    subroutine_end_line = sub.endline

    associate_vars = {}

    associate_start = 0
    associate_end = 0
    ct = subroutine_start_line
    while (ct < subroutine_end_line):
        line = lines[ct]
        line = line.strip().split('!')[0]
        match = re.search(r'\b(associate)\b(?=\()' , line) #find start of assoicate(
        if(match and ct < subroutine_end_line):
            associate_start = ct
            break 
        ct = ct + 1

    if(associate_start !=0):
        # match = re.search(r'\s*\S+\s+=>\s*\S+', line)
        line , ct = line_unwrapper(lines, ct)
        line = line.strip()
        associate_end = ct
        regex_str = re.compile(r'(?<=\()(.+)(?=\))')
        associate_string = regex_str.search(line).group(0)
        
        regex_remove_index = re.compile(r'(\()(.+)(\))')
        for pair in associate_string.split(','):
            parsed = pair.split('=>')
            # find_ex = the ptr name to find in routine
            # repl_ex = the variable to replace it with
            find_ex = parsed[0].strip()
            repl_ex = parsed[1].strip()
            repl_ex = regex_remove_index.sub('',repl_ex)
            if(find_ex in associate_vars):
                print(f"{func_name}::Error! Multiple associations for {find_ex} in {subroutine_name}")
                sys.exit(1)
            associate_vars[find_ex] = repl_ex

        if(verbose):
            print(f"{func_name}:: Found associate variables for {subroutine_name}")
            for key in associate_vars:
                print(f"{key} => {associate_vars[key]}")
        
    return associate_vars, associate_start, associate_end
