module verificationMod 
contains 
subroutine update_vars_vert(gpu,desc)
     use ColumnDataType, only : col_nf, col_ns 
     implicit none 
     integer, intent(in) :: gpu
     character(len=*), optional, intent(in) :: desc
     character(len=256) :: fn
     if(gpu) then
          fn="gpu_vert"
     else
          fn='cpu_vert'
     end if
     if(present(desc)) then
          fn = trim(fn) // desc
     end if
     fn = trim(fn) // ".txt"
     print *, "Verfication File is :",fn
     open(UNIT=10, STATUS='REPLACE', FILE=fn)
     if(gpu) then
     end if 
     !! CPU print statements !! 
     write(10,*) "col_ns%decomp_npools_vr"
     write(10,*) col_ns%decomp_npools_vr 
     close(10)
end subroutine 
end module verificationMod
