module H5InterfaceMod
  use iso_c_binding, only: c_int, c_double, c_char, c_ptr
  implicit none
  interface
     function c_write_int(filename, dset_name, wdata, ndims, dims) bind(C, name="c_write_int")
       import c_int, c_ptr, c_char
       character(kind=c_char), dimension(*), intent(in) :: filename
       character(kind=c_char), dimension(*), intent(in) :: dset_name
       integer(c_int), intent(in) :: wdata(*)
       integer(c_int), value :: ndims
       integer(c_int), intent(in) :: dims(*)
       integer(c_int) :: c_write_int
     end function c_write_int

     function c_write_double(filename, dset_name, wdata, ndims, dims) bind(C, name="c_write_double")
       import c_int, c_double, c_char
       character(kind=c_char), dimension(*), intent(in) :: filename
       character(kind=c_char), dimension(*), intent(in) :: dset_name
       real(c_double), intent(in) :: wdata(*)
       integer(c_int), value :: ndims
       integer(c_int), intent(in) :: dims(*)
       integer(c_int) :: c_write_double
     end function c_write_double
  end interface
end module H5InterfaceMod

