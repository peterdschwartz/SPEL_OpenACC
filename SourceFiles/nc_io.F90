module nc_io

   use netcdf
   use iso_fortran_env
   use iso_c_binding
   implicit none

   public
   integer, parameter :: open_file = 0
   integer, parameter :: create_file = 1
   real(8), parameter :: fill_double = 1.d+36
   integer, parameter :: fill_int = -9999

   interface nc_write_var_array
      module procedure nc_write_double
      module procedure nc_write_integer
      module procedure nc_write_logical
      module procedure nc_write_char
   end interface

   interface nc_write_var_scalar
      module procedure nc_write_double_scalar
      module procedure nc_write_integer_scalar
      module procedure nc_write_logical_scalar
   end interface

   interface nc_read_var
      module procedure nc_read_string
      module procedure nc_read_double_0
      module procedure nc_read_double_1
      module procedure nc_read_double_2
      module procedure nc_read_double_3
      module procedure nc_read_integer_0, &
         nc_read_integer_1, nc_read_integer_2, nc_read_integer_3, &
         nc_read_logical_0, nc_read_logical_1, nc_read_logical_2

   end interface

contains

   integer function nc_create_or_open_file(fn, mode) result(ncid)
      character(len=*), intent(in) :: fn
      integer, intent(in) :: mode

      if (mode == open_file) then
         call check(nf90_open(trim(fn), nf90_nowrite + nf90_netcdf4, ncid))
      else
         call check(nf90_create(trim(fn), nf90_clobber + nf90_netcdf4, ncid))
      end if
   end function nc_create_or_open_file

   subroutine check(status)
      integer, intent(in) :: status
      if (status /= nf90_noerr) then
         print *, trim(nf90_strerror(status))
         stop 2
      end if
   end subroutine check

   subroutine nc_define_var(ncid, ndim, dims, dim_names, varname, xtype, var_id)
      integer, intent(in) :: ncid, ndim
      integer, intent(in) :: dims(ndim)
      character(len=32), dimension(ndim), intent(in) :: dim_names
      character(len=*), intent(in) :: varname
      integer, intent(in) :: xtype  ! e.g. NF90_DOUBLE, NF90_INT, NF90_CHAR, NF90_STRING
      integer, intent(out) :: var_id
      ! Locals
      integer :: i, status
      integer, allocatable :: dim_ids(:)

      allocate (dim_ids(ndim))
      do i = 1, ndim
         status = nf90_inq_dimid(ncid, trim(dim_names(i)), dim_ids(i))
         if(status .ne. nf90_noerr) then
            call check(nf90_def_dim(ncid, trim(dim_names(i)), dims(i), dim_ids(i)))
         end if
      end do

      if (ndim == 0) then
         ! scalar variable: pass zero-length dim_ids
         call check(nf90_def_var(ncid, trim(varname), xtype, dim_ids(1:0), var_id))
      else
         call check(nf90_def_var(ncid, trim(varname), xtype, dim_ids, var_id))
      end if
      
      select case (xtype)
      case (nf90_double)
         call check(nf90_put_att(ncid,var_id,"_FillValue", fill_double))
      case (nf90_int)
         call check(nf90_put_att(ncid,var_id,"_FillValue", fill_int))
      end select

      deallocate (dim_ids)
   end subroutine

   subroutine nc_read_string(ncid, varname, dim_name, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      character(len=*), intent(in) :: dim_name
      character(len=*), intent(out) :: var
      integer :: var_id, dimid, strlen,i
      character(:), allocatable :: buf

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_inq_dimid(ncid, trim(dim_name), dimid))
      call check(nf90_inquire_dimension(ncid, dimid, len=strlen))
      allocate(character(strlen) :: buf); 
      call check(nf90_get_var(ncid, var_id, buf))
      var = ""
      do i=1, strlen 
         var(i:i) = buf(i:i)
      end do
   end subroutine

   subroutine nc_read_double_0(ncid, varname, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      real(8), intent(out) :: var
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine

   subroutine nc_read_double_1(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      real(8), intent(out) :: var(:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine
   
   subroutine nc_read_double_2(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      real(8), intent(out) :: var(:,:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine

   subroutine nc_read_double_3(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      real(8), intent(out) :: var(:,:,:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine

   subroutine nc_read_integer_0(ncid, varname, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(out) :: var
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine

   subroutine nc_read_integer_1(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      integer, intent(out) :: var(:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine
   
   subroutine nc_read_integer_2(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      integer, intent(out) :: var(:,:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine



   subroutine nc_read_integer_3(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      integer, intent(out) :: var(:,:,:)
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_get_var(ncid, var_id, var))
   end subroutine


   subroutine nc_read_logical_0(ncid, varname, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      logical, intent(out) :: var
      integer :: temp

      call nc_read_var(ncid,varname, temp)
      if (temp == 1) then
         var = .true.
      else
         var = .false.
      end if

   end subroutine

   subroutine nc_read_logical_1(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      logical, intent(out) :: var(:)
      integer, allocatable :: temp(:)
      ! Locals:
      integer :: lbs(ndim), ubs(ndim)
      lbs = lbound(var); ubs = ubound(var)
      allocate(temp(lbs(1):ubs(1)))

      call nc_read_var(ncid,varname,ndim,temp)
      var(:) = .false.
      where(temp == 1) var = .true.

   end subroutine
   
   subroutine nc_read_logical_2(ncid, varname, ndim, var)
      integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      integer, intent(in) :: ndim
      logical, intent(out) :: var(:,:)
      integer, allocatable :: temp(:,:)
      !Locals:
      integer :: lbs(ndim), ubs(ndim)
      lbs = lbound(var); ubs = ubound(var)
      allocate(temp(lbs(1):ubs(1), lbs(2):ubs(2)))

      call nc_read_var(ncid,varname,ndim,temp)
      var(:,:) = .false.
      where(temp == 1) var = .true.

   end subroutine

   subroutine nc_write_logical(ncid, ndim, dims, dim_names, var, varname)
      integer, intent(in) :: ncid, ndim
      integer, intent(in) :: dims(ndim)
      character(len=*), dimension(:), intent(in) :: dim_names
      logical, intent(in) :: var(product(dims))
      character(len=*), intent(in) :: varname
      integer :: var_id
      integer, allocatable :: int_buf(:)

      allocate (int_buf(product(dims)))
      int_buf = merge(1, 0, var)  ! logical → int (1=true, 0=false)

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_put_var(ncid, var_id, int_buf))
   end subroutine

   subroutine nc_write_char(ncid, var, varname)
     integer, intent(in) :: ncid
      character(len=*), intent(in) :: varname
      character(len=*), intent(in) :: var

      integer :: var_id, i
      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_put_var(ncid, var_id, trim(var)))

   end subroutine

   subroutine nc_write_integer(ncid, ndim, dims, dim_names, var, varname)
      integer, intent(in) :: ncid
      integer, intent(in) :: ndim
      integer, intent(in) :: dims(ndim)
      character(len=*), dimension(:), intent(in) :: dim_names
      integer, intent(in) :: var(product(dims))
      character(len=*), intent(in) :: varname
      !! locals:
      integer :: var_id
      integer, allocatable :: data_1d(:), data_2d(:, :), data_3d(:, :, :)
      integer, allocatable :: buffer(:)

      allocate (buffer(product(dims)))
      buffer = var

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      select case (ndim)
      case (1)
         allocate (data_1d(dims(1))); data_1d = reshape(buffer, [dims(1)])
         call check(nf90_put_var(ncid, var_id, data_1d))
      case (2)
         allocate (data_2d(dims(1), dims(2))); data_2d = reshape(buffer, [dims(1), dims(2)])
         call check(nf90_put_var(ncid, var_id, data_2d))
      case (3)
         allocate (data_3d(dims(1), dims(2), dims(3))); data_3d = reshape(buffer, [dims(1), dims(2), dims(3)])
         call check(nf90_put_var(ncid, var_id, data_3d))
      case default
         stop "(nc_write_double) doesn't support >3D doubles"
      end select
   end subroutine nc_write_integer

   subroutine nc_write_double(ncid, ndim, dims, dim_names, var, varname)
      integer, intent(in) :: ncid
      integer, intent(in) :: ndim
      integer, intent(in) :: dims(ndim)
      character(len=*), dimension(:), intent(in) :: dim_names
      real(8), intent(in) :: var(product(dims))
      character(len=*), intent(in) :: varname
      !! locals:
      integer :: var_id
      real(8), allocatable :: data_1d(:), data_2d(:, :), data_3d(:, :, :)
      real(8), allocatable :: buffer(:)

      allocate (buffer(product(dims)))

      buffer = var

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      select case (ndim)
      case (1)
         allocate (data_1d(dims(1))); data_1d = reshape(buffer, [dims(1)])
         call check(nf90_put_var(ncid, var_id, data_1d))
      case (2)
         allocate (data_2d(dims(1), dims(2))); data_2d = reshape(buffer, [dims(1), dims(2)])
         call check(nf90_put_var(ncid, var_id, data_2d))
      case (3)
         allocate (data_3d(dims(1), dims(2), dims(3))); data_3d = reshape(buffer, [dims(1), dims(2), dims(3)])
         call check(nf90_put_var(ncid, var_id, data_3d))
      case default
         stop "(nc_write_double) doesn't support >3D doubles"
      end select
   end subroutine nc_write_double

   subroutine nc_write_double_scalar(ncid, var, varname)
      integer, intent(in) :: ncid
      real(8), intent(in) :: var
      character(len=*), intent(in) :: varname
      !! locals:
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_put_var(ncid, var_id, var))

   end subroutine nc_write_double_scalar


   subroutine nc_write_integer_scalar(ncid, var, varname)
      integer, intent(in) :: ncid
      integer, intent(in) :: var
      character(len=*), intent(in) :: varname
      !! locals:
      integer :: var_id

      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_put_var(ncid, var_id, var))

   end subroutine nc_write_integer_scalar

   subroutine nc_write_logical_scalar(ncid, var, varname)
      integer, intent(in) :: ncid
      logical, intent(in) :: var
      character(len=*), intent(in) :: varname
      !! locals:
      integer :: var_id, buf
      buf = 0
      if (var) buf = 1
      call check(nf90_inq_varid(ncid, trim(varname), var_id))
      call check(nf90_put_var(ncid, var_id, buf))

   end subroutine nc_write_logical_scalar

end module nc_io
