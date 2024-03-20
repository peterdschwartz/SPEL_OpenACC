module write_filterMod
   implicit none 
   use fileio_mod, only : fio_open, fio_close
   ! This should be changed  if using proc-filters 
   #ifdef proc
      use filterMod, only : procfilter
      #define filtertype procfilter
   #else 
      use filterMod, only : clumpfilter
      #define filtertype clumpfilter 
   #endif

   subroutine write_filter(filter,desc)
      ! use with clump_pproc = 1 
      type(filtertype), intent(in) :: filter
      character(len=*), intent(in) :: desc 
      integer :: fid
      character(len=32) :: ofile = "filter-test"
      ofile = trim(ofile) //desc//".txt"
      fid = 23
      call fio_open(fid,ofile, 2)
      write(fid,"(A)") "filter%num_soilc"     
      write(fid,*)filter%num_soilc     
      write(fid,"(A)") "filter%num_soilp"     
      write(fid,*)filter%num_soilp     
      write(fid,"(A)") "filter%num_pcropp"    
      write(fid,*)filter%num_pcropp    
      write(fid,"(A)") "filter%num_nolu_barep"
      write(fid,*)filter%num_nolu_barep
      write(fid,"(A)") "filter%num_nolu_vegp" 
      write(fid,*)filter%num_nolu_vegp 
      write(fid,"(A)") "filter%num_urbanp"    
      write(fid,*)filter%num_urbanp    
      write(fid,"(A)") "filter%num_nourbanp"  
      write(fid,*)filter%num_nourbanp  
      write(fid,"(A)") "filter%num_urbanc"  
      write(fid,*)  filter%num_urbanc  
      write(fid,"(A)") "filter%num_urbanl"  
      write(fid,*)  filter%num_urbanl  
      write(fid,"(A)") "filter%num_nourbanl"
      write(fid,*)  filter%num_nourbanl
      write(fid,"(A)") "filter%num_lakep"   
      write(fid,*)  filter%num_lakep   
      write(fid,"(A)") "filter%num_lakec"   
      write(fid,*)  filter%num_lakec   
      write(fid,"(A)") "filter%num_nolakec"
      write(fid,*)  filter%num_nolakec 
      write(fid,"(A)") "filter%num_lakesnowc   "
      write(fid,*) filter%num_lakesnowc   
      write(fid,"(A)") "filter%num_lakenosnowc "
      write(fid,*) filter%num_lakenosnowc 
      write(fid,"(A)") "filter%num_nolakep     "
      write(fid,*) filter%num_nolakep     
      write(fid,"(A)") "filter%num_hydrologyc  "
      write(fid,*) filter%num_hydrologyc  
      write(fid,"(A)") "filter%num_hydrononsoic"
      write(fid,*) filter%num_hydrononsoic
      write(fid,"(A)") "filter%num_snowc       "
      write(fid,*) filter%num_snowc       
      write(fid,"(A)") "filter%num_nosnowc     "
      write(fid,*) filter%num_nosnowc    
      
      write(fid,"(A)") "filter%soilc     "
      write(fid,* ) filter%soilc     
      write(fid,"(A)") "filter%soilp     "
      write(fid,* ) filter%soilp     
      write(fid,"(A)") "filter%pcropp    "
      write(fid,* ) filter%pcropp    
      write(fid,"(A)") "filter%nolu_barep"
      write(fid,* ) filter%nolu_barep
      write(fid,"(A)") "filter%nolu_vegp "
      write(fid,* ) filter%nolu_vegp 

      write(fid,"(A)") "filter%urbanp  "
      write(fid,*) filter%urbanp  
      write(fid,"(A)") "filter%nourbanp"
      write(fid,*) filter%nourbanp
      write(fid,"(A)") "filter%urbanc  "
      write(fid,*) filter%urbanc  
      write(fid,"(A)") "filter%urbanl  "
      write(fid,*) filter%urbanl  
      write(fid,"(A)") "filter%nourbanl"
      write(fid,*) filter%nourbanl
      write(fid,"(A)") "filter%lakep   "
      write(fid,*) filter%lakep   
      write(fid,"(A)") "filter%nolakep "
      write(fid,*) filter%nolakep 
      write(fid,"(A)") "filter%lakec       "
      write(fid,*) filter%lakec       
      write(fid,"(A)") "filter%nolakec     "
      write(fid,*) filter%nolakec     
      write(fid,"(A)") "filter%hydrologyc  "
      write(fid,*) filter%hydrologyc  
      write(fid,"(A)") "filter%hydrononsoic"
      write(fid,*) filter%hydrononsoic

      write(fid,"(A)") "filter%snowc      "
      write(fid,*) filter%snowc      
      write(fid,"(A)") "filter%nosnowc    "
      write(fid,*) filter%nosnowc    
      write(fid,"(A)") "filter%lakesnowc  "
      write(fid,*) filter%lakesnowc  
      write(fid,"(A)") "filter%lakenosnowc"
      write(fid,*) filter%lakenosnowc

      call fio_close(fid)
      
   end subroutine write_filter

end module write_filterMod