import sys
import os
from mod_config import home_dir, elm_files

def get_delta_from_dim(dim,delta):
    """
    this function will parse the dimension string to find if it's
    a patch, col, land, topo, or grid index
    """
    newdim=[]
    bool = False
    if (not dim):
        newdim = ''
        return newdim

    dim = dim.replace('(','');
    dim = dim.replace(')','');
    dim_li = dim.split(',')

    ct = 0

    if(delta == 'y'):
        for el in dim_li:
            if('begp' in el and 'endp' in el):
                newdim.append("begp:endp") #newdim.append('nc*deltap+1:(nc+1)*deltap')
            elif('begc' in el and 'endc' in el):
                newdim.append('begc:endc')
            elif('begl' in el and 'endl' in el):
                newdim.append('begl:endl')
            elif('begg' in el and 'endg' in el):
                newdim.append('begg:endg')
            elif('begt' in el and 'endt' in el):
                newdim.append('begt:endt')
            else:
                newdim.append(':')

    if(delta == 'n'):
        for el in dim_li:
            if('begp' in el and 'endp' in el):
                newdim.append("begp_copy:endp_copy")
            elif('begc' in el and 'endc' in el):
                newdim.append("begc_copy:endc_copy")
            elif('begl' in el and 'endl' in el):
                newdim.append("begl_copy:endl_copy")
            elif('begg' in el and 'endg' in el):
                newdim.append("begg_copy:endg_copy")
            elif('begt' in el and 'endt' in el):
                newdim.append("begt_copy:endt_copy")
            else:
                newdim.append(':')

    newdim = ','.join(newdim)
    newdim = '('+newdim+')'

    return newdim

def generate_makefile(files,casename):
    from mod_config import preproc_list,unit_test_files
    """
    This function takes the list of needed files
    and makes a makefile and stores it in the case dir
    """
    noF90 = [f.replace('.F90','') for f in files]
    #preproc_dict = {k : False for k in preproc_list}
    FC = "nvfortran"
    FC_FLAGS_ACC = " -ta=tesla:deepcopy -Minfo=accel -acc -Mcuda\n"
    FC_FLAGS_DEBUG = " -g -O0 -Mbounds -Mchkptr -Mchkstk\n"
    MODEL_FLAGS = " -DMODAL_AER -DCPL_BYPASS"

    #Get complete preproccesor flags:
    print(noF90)
    for f in noF90:
        if f in preproc_list:
            temp = f.upper()
            MODEL_FLAGS = MODEL_FLAGS + ' -D'+temp
    
    MODEL_FLAGS = MODEL_FLAGS+'\n'
    object_file = open(f'{home_dir}list_of_object_files.txt','r')
    obj_list = object_file.readlines()
    object_file.close()
    ordered_list = []
    for f in obj_list:
        if f.strip('\n') in noF90:
            ordered_list.append(f.strip('\n')+'.o')

    for f in unit_test_files:
        ordered_list.append(f)

    ofile = open(f"{casename}/Makefile",'w')
    ofile.write("FC= "+FC+"\n")
    ofile.write("FC_FLAGS_ACC= "+ FC_FLAGS_ACC)
    ofile.write("FC_FLAGS_DEBUG = "+FC_FLAGS_DEBUG)
    ofile.write("MODEL_FLAGS= "+MODEL_FLAGS)
    ofile.write("FC_FLAGS = $(FC_FLAGS_DEBUG) $(MODEL_FLAGS)"+"\n")
    ofile.write("TEST = $(findstring acc,$(FC_FLAGS))\n")
    objs = ' '.join(ordered_list)
    ofile.write("objects = "+objs+'\n')

    ofile.write("elmtest.exe : $(objects)"+"\n")
    ofile.write("\t"+"$(FC) $(FC_FLAGS) -o elmtest.exe $(objects)"+"\n")
    ofile.write("\n \n")
    ofile.write("#.SUFFIXES: .o .F90"+"\n")
    # These files do not need to be compiled with ACC flags or optimizations
    # Can cause errors or very long compile times
    noopt_list = ["fileio_mod","readConstants","readMod","duplicateMod"]
    for f in noopt_list:
        ofile.write(f"{f}.o : {f}.F90"+"\n")
        ofile.write("\t"+f"$(FC) -O0 -c $({MODEL_FLAGS}) $<"+"\n")

    ofile.write("%.o : %.F90"+"\n")
    ofile.write("\t"+"$(FC) $(FC_FLAGS) -c $<"+"\n")

    ofile.write("ifeq (,$(TEST))\n")
    ofile.write("verificationMod.o : verificationMod.F90\n")
    ofile.write("\t"+"$(FC) -O0 -c $<\n")
    ofile.write("else\n")
    ofile.write("\t"+"$(FC) -O0 -ta=tesla:deepcopy -acc -c $<\n")
    ofile.write("endif\n")
    
    ofile.write("\n\n"+".PHONY: clean"+"\n")
    ofile.write("clean:"+"\n")
    ofile.write("\t"+"rm -f *.mod *.o *.exe"+"\n")
    ofile.close()

def write_elminstMod(vardict, type_list,casename):
    """
    Writes elm_instMod since all variable declarations
    """
    file = open(f"{casename}/elm_instMod.F90",'w')
    spaces = "     "
    file.write("module elm_instMod\n")
    #use statements
    for name, v in vardict.items():
        mod = v.mod
        vname = v.name
        if(v.name not in type_list): continue
        if("_vars" in vname):
            file.write(spaces+'use {}, only : {} \n'.format(mod,v.dtype))

    file.write(spaces+"implicit none\n")
    file.write(spaces+"save\n")
    file.write(spaces+"public\n")
    for name, v in vardict.items():
        mod = v.mod
        vname = v.name
        if(v.name not in type_list): continue
        if("_vars" in vname):
            file.write(spaces+f"type({v.dtype}) :: {v.name} \n")

    file.write("end module elm_instMod\n")
    file.close()


def clean_use_statements(mod_list, file,casename):
    from edit_files import comment_line

    """
     function that will clean both initializeParameters
     and readConstants
    """
    ifile = open(f"{elm_files}{file}.F90",'r')
    lines = ifile.readlines()
    ifile.close()
    noF90 = [f.replace('.F90','') for f in mod_list]
    start = "!#USE_START"; end = "!#USE_END"
    analyze = False
    ct = 0
    while ct < len(lines):
        line = lines[ct]
        if(line.strip() == start):
            analyze = True
            ct += 1; continue;
        if(line.strip() == end):
            analyze = False
            break
        if(analyze):
            l = line.split('!')[0]
            mod = l.split()[1]
            if(mod not in noF90):
                lines, ct = comment_line(lines=lines,ct=ct,verbose=False)
        ct +=1
    with open(f"{casename}/{file}.F90",'w') as ofile:
        ofile.writelines(lines)

######################################################3


def clean_main_elminstMod(vardict,type_list,files,casename):
    from edit_files import comment_line
    from analyze_subroutines import find_file_for_subroutine
    import re
    """
    This function will clean the use lists of main, initializeParameters,
    and readConstants.  It will also clean the variable initializations and
    declarations in main and elm_instMod
    """
    clean_use_statements(mod_list=files, file="readConstants",casename=casename)
    clean_use_statements(mod_list=files, file="initializeParameters",casename=casename)
    clean_use_statements(mod_list=files, file="main",casename=casename)
    clean_use_statements(mod_list=files, file="elm_initializeMod",casename=casename)
    clean_use_statements(mod_list=files, file="update_accMod",casename=casename)

    ifile = open(f"{casename}/elm_initializeMod.F90",'r')
    lines = ifile.readlines()
    ifile.close()
    noF90 = [f.replace('.F90','') for f in files]
    file2,startline,endline = find_file_for_subroutine('elm_init')
    ct = startline
    start = "!#VAR_INIT_START"
    stop = "!#VAR_INIT_STOP"
    analyze = False
    while ct < endline:
        line = lines[ct]
        ##Adjusting variable init
        if(line.strip() == start):
            analyze = True
            ct += 1; continue;
        if(line.strip() == stop):
            analyze = False
            break
        if(analyze):
            l = line.split('!')[0]
            match_call = re.search(f'^(call)[\s]+',l.strip())
            if(match_call):
                #should be derived type init:
                if('%' not in l.strip()): print("ERROR")
                l = l.strip()
                temp = l.split()[1].split('%')
                varname = temp[0].lower()
                if(varname not in type_list):
                    lines, ct = comment_line(lines=lines,ct=ct)
        ct += 1
    #write adjusted main to file in case dir
    with open(f"{casename}/elm_initializeMod.F90","w") as of:
        of.writelines(lines)

    write_elminstMod(vardict,type_list,casename)
#####################################################

def duplicate_clumps(vardict,types_list):

    file = open("duplicateMod.F90",'w')
    spaces = "   "
    file.write("module duplicateMod\n")
    file.write("contains\n")
    
    file.write("subroutine duplicate_weights(unique_sites,total_gridcells)\n")
    file.write(spaces+"use elm_varsur, only : wt_lunit, urban_valid\n")
    file.write(spaces+"implicit none\n")
    file.write(spaces+"integer, intent(in) :: unique_sites\n")
    file.write(spaces+"integer, intent(in) :: total_gridcells\n")
    file.write(spaces+"integer :: g, dim2, l, gcopy\n")
    file.write(spaces+"dim2 = size(wt_lunit,2)\n")
    file.write(spaces+"print *, 'dim2 = ',dim2 \n")
    file.write(spaces+"do g = unique_sites+1, total_gridcells\n") 
    file.write(spaces+spaces+"gcopy = mod(g-1,unique_sites)+1\n")
    file.write(spaces+spaces+"do l=1,dim2\n")  
    file.write(spaces*3+"wt_lunit(g,l) = wt_lunit(gcopy,l)\n")
    file.write(spaces*2+"end do\n")  
    file.write(spaces*2+"urban_valid(g) = urban_valid(gcopy)\n") 
    file.write(spaces+"end do\n") 
    file.write("end subroutine duplicate_weights\n")

    file.write("subroutine duplicate_clumps(mode,unique_sites,num_sites)\n")

    #use statements
    for name, v in vardict.items():
        mod = v.declaration
        vname = v.name
        if(v.name not in types_list): continue
        file.write(spaces+'use {}, only : {} \n'.format(mod,vname))

    file.write(spaces+'use decompMod, only : bounds_type, get_clump_bounds, procinfo \n')
    file.write(spaces+'use elm_varcon \n')
    file.write(spaces+'use elm_varpar \n')
    file.write(spaces+'use elm_varctl \n')
    file.write(spaces+'use landunit_varcon \n')
    file.write(spaces+'implicit none \n')
    file.write(spaces+'integer, intent(in) :: mode, unique_sites, num_sites \n')
    file.write(spaces+'type(bounds_type)  :: bounds_copy, bounds\n')
    file.write(spaces+'integer :: errcode, nc,nc_copy, nclumps \n')
    file.write(spaces+'integer :: begp_copy, endp_copy, begp, endp \n')
    file.write(spaces+'integer :: begc_copy, endc_copy, begc, endc \n')
    file.write(spaces+'integer :: begg_copy, endg_copy, begg, endg \n')
    file.write(spaces+'integer :: begt_copy, endt_copy, begt, endt \n')
    file.write(spaces+'integer :: begl_copy, endl_copy, begl, endl \n')
    file.write(spaces+'nclumps = num_sites \n')
    #
    file.write(spaces+"if(mode == 0) then\n")
    li = ['veg_pp','col_pp','lun_pp','grc_pp','top_pp']
    file.write(spaces+spaces+'do nc=unique_sites+1, num_sites \n')
    file.write(spaces*3+"nc_copy = mod(nc-1,unique_sites)+1\n")
    file.write(spaces*3+"call get_clump_bounds(nc,bounds)\n")
    file.write(spaces*3+"call get_clump_bounds(nc_copy,bounds_copy)\n")

    file.write(spaces*3+'begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg\n')
    file.write(spaces*3+'begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt\n')
    file.write(spaces*3+'begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl\n')
    file.write(spaces*3+'begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc\n')
    file.write(spaces*3+'begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp\n')

    file.write(spaces*3+'begg=bounds%begg; endg=bounds%endg\n')
    file.write(spaces*3+'begt=bounds%begt; endt=bounds%endt\n')
    file.write(spaces*3+'begl=bounds%begl; endl=bounds%endl\n')
    file.write(spaces*3+'begc=bounds%begc; endc=bounds%endc\n')
    file.write(spaces*3+'begp=bounds%begp; endp=bounds%endp\n')

    ignore_list = ['is_veg','is_bareground','wt_ed']
    for var in vardict.values():
        if var.name not in li: continue
        for c in var.components:
            if(not c[0]): continue
            if(c[1] in ignore_list): continue 
            fname = var.name+'%'+c[1]
            dim = c[2]
            newdim = get_delta_from_dim(dim,'y')
            dim1 = get_delta_from_dim(dim,'n'); dim1 = dim1.replace('_all','')
            if(newdim == '(:)' or newdim == ''): continue
            file.write(spaces*3+fname+newdim+' &'+'\n')
            file.write(spaces+spaces+spaces+spaces+'= '+fname+dim1+'\n')

    file.write(spaces*2+'end do\n')

    file.write(spaces+"else\n")
    file.write(spaces*2+'do nc=unique_sites+1, num_sites \n')
    file.write(spaces*3+"nc_copy = mod(nc-1,unique_sites)+1\n")
    file.write(spaces*3+"call get_clump_bounds(nc,bounds)\n")
    file.write(spaces*3+"call get_clump_bounds(nc_copy,bounds_copy)\n")

    file.write(spaces*3+'begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg\n')
    file.write(spaces*3+'begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt\n')
    file.write(spaces*3+'begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl\n')
    file.write(spaces*3+'begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc\n')
    file.write(spaces*3+'begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp\n')

    file.write(spaces*3+'begg=bounds%begg; endg=bounds%endg\n')
    file.write(spaces*3+'begt=bounds%begt; endt=bounds%endt\n')
    file.write(spaces*3+'begl=bounds%begl; endl=bounds%endl\n')
    file.write(spaces*3+'begc=bounds%begc; endc=bounds%endc\n')
    file.write(spaces*3+'begp=bounds%begp; endp=bounds%endp\n')

    for var in vardict.values():
        if var.name in li: continue
        for c in var.components:
            if(not c[0]): continue
            if(c[1] in ignore_list): continue 
            fname = var.name+'%'+c[1]
            dim = c[2]
            newdim = get_delta_from_dim(dim,'y')
            dim1 = get_delta_from_dim(dim,'n'); dim1 = dim1.replace('_all','')
            if(newdim == '(:)' or newdim == ''): continue
            file.write(spaces*3+fname+newdim+' &'+'\n')
            file.write(spaces+spaces+spaces+spaces+'= '+fname+dim1+'\n')

    file.write(spaces+'end do\n')
    file.write(spaces+'end if \n')

    file.write("end subroutine duplicate_clumps \n")
    file.write("end module \n")
    file.close()

def create_write_vars(vardict,read_types,subname,use_isotopes=False):
    """
    This function generates the subroutine write_vars that is to be called from
    E3SM prior to execution of the desired subroutine
    """
    print("Creating: writeMod.F90")
    spaces = "     " #holds tabs indentations without using \t
    ofile = open('writeMod.F90','w')
    ofile.write('module writeMod\n')
    ofile.write('contains\n')
    ofile.write('subroutine write_vars()\n')
    ofile.write(spaces + "use fileio_mod, only : fio_open, fio_close\n")
    ofile.write(spaces+"use elm_varsur, only : wt_lunit, urban_valid\n")
    #use statements
    print(read_types)

    for key in vardict.keys():
        if(vardict[key].name not in read_types): continue
        mod = vardict[key].declaration
        vname = vardict[key].name
        c13c14 = bool('c13' in vname or 'c14' in vname)
        if(c13c14): continue
        ofile.write(spaces+'use {}, only : {} \n'.format(mod,vname))

    ofile.write(spaces + 'implicit none \n')
    ofile.write(spaces +' integer :: fid \n')
    ofile.write(spaces + f'character(len=256) :: ofile = "output_{subname}_vars.txt" \n')
    ofile.write(spaces + 'fid = 23 \n')
    ofile.write(spaces + "call fio_open(fid,ofile, 2) \n\n")
    li = ['veg_pp','col_pp','lun_pp','grc_pp','top_pp']
    ofile.write(spaces+'write(fid,"(A)") "wt_lunit"\n')
    ofile.write(spaces+'write(fid,*) wt_lunit\n')
    ofile.write(spaces+'write(fid,"(A)") "urban_valid"\n')
    ofile.write(spaces+'write(fid,*) urban_valid\n\n')

    for key in vardict.keys():
        if(key in li):
            vardict[key]._create_write_read_functions('w',ofile)

    for key in vardict.keys():
        c13c14 = bool('c13' in key or 'c14' in key)
        if(key not in li and not(c13c14)):
            if(vardict[key].name not in read_types): continue
            vardict[key]._create_write_read_functions('w',ofile)

    ofile.write(spaces+"call fio_close(fid) \n")
    ofile.write("end subroutine write_vars\n")
    ofile.write("end module writeMod\n")
    ofile.close()

def create_read_vars(vardict,read_types):
    ##======================= READ VARS ==================================#
    print("Creating subroutine read_vars / read_weights in readMod.F90")
    spaces = "     " #holds tabs indentations without using \t
    ofile = open('readMod.F90','w')
    ofile.write('module readMod \n')
    #use statements
    for key in vardict.keys():
        if(vardict[key].name not in read_types): continue
        mod = vardict[key].declaration
        vname = vardict[key].name
        c13c14 = bool('c13' in vname or 'c14' in vname)
        if(c13c14): continue
        ofile.write('use {}, only : {} \n'.format(mod,vname))
    ofile.write('use decompMod, only : bounds_type \n')
    ofile.write('use elm_varcon \n')
    ofile.write('use elm_varpar \n')
    ofile.write('use elm_varctl \n')
    ofile.write('use landunit_varcon \n')
    ofile.write('contains \n')

    # read_weights
    ofile.write('subroutine read_weights(in_file,numg)\n')
    ofile.write(spaces+'use fileio_mod, only : fio_open, fio_read, fio_close\n')
    ofile.write(spaces+'use elm_varsur, only : wt_lunit, urban_valid\n')
    ofile.write(spaces+"implicit none\n")
    ofile.write(spaces+"character(len=256), intent(in) :: in_file\n")
    ofile.write(spaces+"integer, intent(in) :: numg\n")
    ofile.write(spaces+"integer :: errcode = 0\n\n")
    ofile.write(spaces+"call fio_open(18,in_file,1)\n") 
    ofile.write(spaces+"call fio_read(18,'wt_lunit',wt_lunit(1:numg,:),errcode=errcode)\n")
    ofile.write(spaces+"if(errcode .ne. 0) stop\n")
    ofile.write(spaces+"call fio_read(18,'urban_valid',urban_valid(1:numg),errcode=errcode)\n")
    ofile.write(spaces+"if(errcode .ne. 0) stop\n\n")
    ofile.write(spaces+"end subroutine read_weights\n\n")

    # read_vars 
    ofile.write('subroutine read_vars(in_file,bounds,mode,nsets)\n')
    ofile.write(spaces + "use fileio_mod, only : fio_open, fio_read, fio_close\n")
    ofile.write(spaces+'implicit none \n')

    # Dummy Variables 
    ofile.write(spaces+'character(len=256),intent(in) :: in_file \n')
    ofile.write(spaces+'type(bounds_type), intent(in) :: bounds \n')
    ofile.write(spaces+'integer, intent(in) :: mode\n')
    ofile.write(spaces+'integer, intent(in) :: nsets\n')

    # Local Variables 
    ofile.write(spaces+'integer :: errcode = 0 \n')
    ofile.write(spaces+'integer :: begp,  endp  \n')
    ofile.write(spaces+'integer :: begc,  endc  \n')
    ofile.write(spaces+'integer :: begg,  endg; \n')
    ofile.write(spaces+'integer :: begl,  endt; \n')
    ofile.write(spaces+'integer :: begt,  endl; \n')
    #
    ofile.write(spaces+"begp = bounds%begp; endp = bounds%endp/nsets \n")
    ofile.write(spaces+"begc = bounds%begc; endc = bounds%endc/nsets \n")
    ofile.write(spaces+"begl = bounds%begl; endl = bounds%endl/nsets \n")
    ofile.write(spaces+"begt = bounds%begt; endt = bounds%endt/nsets \n")
    ofile.write(spaces+"begg = bounds%begg; endg = bounds%endg/nsets \n")
    
    ofile.write(spaces+'print *,"begp range :",begp, endp\n')
    ofile.write(spaces+'print *,"begc range :",begc, endc\n')
    ofile.write(spaces+'print *,"begl range :",begl, endl\n')
    ofile.write(spaces+'print *,"begt range :",begt, endt\n')
    ofile.write(spaces+'print *,"begg range :",begg, endg\n')

    ofile.write(spaces +"call fio_open(18,in_file, 1) \n")
    ofile.write(spaces+"if(mode == 1) then\n")
    ofile.write(spaces+"print *, 'reading in physical properties'\n")
    li = ['veg_pp','col_pp','lun_pp','grc_pp','top_pp']
    for key in vardict.keys():
        if(key in li):
            vardict[key]._create_write_read_functions('r',ofile)
    ofile.write(spaces+"else\n")
    for key in vardict.keys():
        c13c14 = bool('c13' in key or 'c14' in key)
        if(key not in li and not(c13c14)):
            if(vardict[key].name not in read_types): continue
            vardict[key]._create_write_read_functions('r',ofile)
    ofile.write(spaces+"end if \n")
    
    ofile.write(spaces+"call fio_close(18) \n")
    ofile.write("end subroutine read_vars \n")
    ofile.write('end module \n')
    ofile.close()
