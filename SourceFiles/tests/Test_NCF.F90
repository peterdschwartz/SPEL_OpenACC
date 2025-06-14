program test_nc_io
   use nc_io
   use nc_allocMod
   implicit none

   integer :: ncid, varid, t_dimid
   integer , parameter :: N=11
   real(8), allocatable,dimension(:, :) :: var_data, read_data
   real(8), dimension(10) :: press
   real(8) :: const
   character(len=256) :: filename
   character(len=256) :: varname
   character(len=256) :: dim_names(3)
   integer :: i, dims(4)
   character(len=10) :: nu_com = "RD", read_str

   ! Initialize data and variables
   filename = "test.nc"
   varname = "temperature"
   dim_names = ["latitude", "longitude", "time"]

   allocate(var_data(N,N))
   ! Fill var_data with sample values (e.g., temperature)
   do i = 1, N 
      var_data(i,:) =dble(i)*10.d0
   end do
   press(:) = 4.d0
   const = 2.d0

   ! Create or open the NetCDF file
   ncid = nc_create_or_open_file(filename, create_file)

   ! Write the data to the NetCDF file
   print*, "Defining"
   call check(nf90_def_dim(ncid, "time", NF90_UNLIMITED, t_dimid))

   call nc_define_var(ncid, rank(var_data), shape(var_data), dim_names, varname, NF90_DOUBLE, varid, .true.)

   call check(nf90_put_att(ncid, varid, "lbounds", lbound(var_data))); call check(nf90_put_att(ncid, varid, "ubounds", ubound(var_data))); 
   call nc_define_var(ncid, rank(press), shape(press), ["bars"],"pressure",NF90_DOUBLE, varid, .false.)
   call check(nf90_put_att(ncid, varid, "lbounds", lbound(var_data))); call check(nf90_put_att(ncid, varid, "ubounds", ubound(var_data))); 
   call nc_define_var(ncid, rank(const), shape(const), ["scalar"],"const",NF90_DOUBLE, varid, .false.)
   call nc_define_var(ncid, 1,[len(nu_com)], ["nu_com"//"_str"], "nu_com",NF90_char, varid, .false.)

   call check(nf90_enddef(ncid))

   print *, "Writing"
   do i = 1, 3
      var_data(i,1) = -1.d0
      call nc_write_var_array(ncid, 2, shape(var_data), dim_names, reshape(var_data, [product(shape(var_data))]), varname, i)
   end do
   call nc_write_var_array(ncid, 1,shape(press), ["bars"],press,"pressure")
   call nc_write_var_scalar(ncid, const, "const")
   call nc_write_var_array(ncid, nu_com, "nu_com")

   print *, "NetCDF file written successfully."

   ! Close the NetCDF file
   call check(nf90_close(ncid))
   nu_com = 'ECA'

   print *, "~~~~ Reading phase ~~~~~"
   ncid = nc_create_or_open_file(filename, open_file)
   call nc_alloc(ncid, trim(varname), rank(read_data),read_data)

   call nc_read_var(ncid, trim(varname), rank(var_data), read_data, timestep=2)
   print *, "read data:"
   print *, read_data(:,:)
   call nc_read_var(ncid, "nu_com", "nu_com"//"_str", read_str)
   print *, "read_str: ",read_str
   call check(nf90_close(ncid))

   deallocate(var_data, read_data)

end program test_nc_io

