module H5InterfaceMod
  use iso_c_binding, only: c_int, c_double, c_char, c_ptr
  use hdf5
  implicit none
  integer         :: hdf_err
  interface
    function c_open_file(filename, mode) bind(C, name="c_open_file")
      import c_char, c_int, c_ptr
      character(kind=c_char), dimension(*), intent(in) :: filename
      integer(c_int), value :: mode
      type(c_ptr) :: c_open_file
    end function c_open_file

    function c_close_file(file_id) bind(C, name="c_close_file")
      import c_int, c_ptr
      type(c_ptr), value :: file_id
      integer(c_int) :: c_close_file
    end function c_close_file

     function c_write_int(file_id, dset_name, wdata, ndims, dims) bind(C, name="c_write_int")
       import c_int, c_ptr, c_char 
       type(c_ptr), value :: file_id
       character(kind=c_char), dimension(*), intent(in) :: dset_name
       integer(c_int), intent(in) :: wdata(*)
       integer(c_int), value :: ndims
       integer(c_int), intent(in) :: dims(*)
       integer(c_int) :: c_write_int
     end function c_write_int

     function c_write_double(file_id, dset_name, wdata, ndims, dims) bind(C, name="c_write_double")
       import c_int, c_double, c_char, c_ptr
       type(c_ptr), value :: file_id
       character(kind=c_char), dimension(*), intent(in) :: dset_name
       real(c_double), intent(in) :: wdata(*)
       integer(c_int), value :: ndims
       integer(c_int), intent(in) :: dims(*)
       integer(c_int) :: c_write_double
     end function c_write_double

    function c_read_int(file_id, dset_name, rdata) bind(C, name="c_read_int")
        import c_int, c_char, c_ptr
        type(c_ptr), value :: file_id
        character(kind=c_char), dimension(*), intent(in) :: dset_name
        integer(c_int), intent(out) :: rdata(*)
        integer(c_int) :: c_read_int
    end function c_read_int

    function c_read_dbl(file_id, dset_name, rdata) bind(C, name="c_read_dbl")
        import c_int, c_char, c_ptr, c_double
        type(c_ptr), value :: file_id
        character(kind=c_char), dimension(*), intent(in) :: dset_name
        real(c_double), intent(out) :: rdata(*)
        integer(c_int) :: c_read_dbl
    end function c_read_dbl
  end interface

  interface h5_write_data
    module procedure :: hdf5_write_data_int_0d
    module procedure :: hdf5_write_data_int_1d
    module procedure :: hdf5_write_data_int_2d
    module procedure :: hdf5_write_data_logical_0d
    module procedure :: hdf5_write_data_logical_1d
    module procedure :: hdf5_write_data_logical_2d
    module procedure :: hdf5_write_data_char_0d
    module procedure :: hdf5_write_data_real_0d
    module procedure :: hdf5_write_data_real_1d
    module procedure :: hdf5_write_data_real_2d
    module procedure :: hdf5_write_data_real_3d
  end interface h5_write_data

  interface h5_read_data
    module procedure :: hdf5_read_data_int_0d
    module procedure :: hdf5_read_data_int_1d
    module procedure :: hdf5_read_data_int_2d
    module procedure :: hdf5_read_data_int_3d

    module procedure :: hdf5_read_data_real_0d
    module procedure :: hdf5_read_data_real_1d
    module procedure :: hdf5_read_data_real_2d
    module procedure :: hdf5_read_data_real_3d

    module procedure :: hdf5_read_data_logical_0d
    module procedure :: hdf5_read_data_logical_1d
    module procedure :: hdf5_read_data_logical_2d

    module procedure :: hdf5_read_data_char_0d

  end interface h5_read_data
  contains 

  subroutine h5_open_create_file(fn, mode, file_id)
    character(len=*), INTENT(IN) :: fn
    integer, intent(in) :: mode
    integer(hid_t), intent(out) :: file_id
    integer :: err

    if (mode == 0) then 
      call h5fcreate_f(fn, H5F_ACC_TRUNC_F, file_id, err)
    else
      call h5fopen_f (fn, H5F_ACC_RDONLY_F, file_id, err)
    end if 
  end subroutine h5_open_create_file

  subroutine hdf5_write_data_int_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(in) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, trim(dsetname), H5T_NATIVE_INTEGER, dspace_id, dset_id, err)
    call h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)
    call h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_int_0d

  subroutine hdf5_write_data_int_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(in) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do
    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_INTEGER, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_int_1d

  subroutine hdf5_write_data_int_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(in) :: dset_data(:,:)

    integer, parameter :: rank = 2
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_INTEGER, dspace_id, dset_id, err)

    CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)

    ! Read the dataset.
    ! CALL h5dread_f(dset_id, H5T_NATIVE_INTEGER, data_out, data_dims, error)
    ! Close the dataset.
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_int_2d

  subroutine hdf5_write_data_logical_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(in) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err, data_i

    if(dset_data) then
      data_i = 1
    else
      data_i = 0
    endif

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, trim(dsetname), H5T_NATIVE_INTEGER, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, data_i, data_dims, err)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_logical_0d

  subroutine hdf5_write_data_logical_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(in) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err
    integer, allocatable :: data_i(:)

    allocate(data_i,mold=dset_data)
    data_i(:) = 0

    where(dset_data) data_i = 1

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do
    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_INTEGER, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, data_i, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
    deallocate(data_i)
  end subroutine hdf5_write_data_logical_1d


  subroutine hdf5_write_data_logical_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(in) :: dset_data(:,:)

    integer, parameter :: rank = 2
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err
    integer, allocatable :: data_i(:,:)

    allocate(data_i,mold=dset_data)
    data_i(:,:) = 0

    where(dset_data) data_i = 1

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do
    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_INTEGER, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_INTEGER, data_i, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
    deallocate(data_i)
  end subroutine hdf5_write_data_logical_2d

  subroutine hdf5_write_data_char_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    character(len=*), intent(in) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id, filetype
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err
    integer(size_t) :: str_len

    str_len = len_trim(dset_data)

    ! Create a datatype for Fortran strings of this length.
    call H5Tcopy_f(H5T_FORTRAN_S1, filetype, err)
    call H5Tset_size_f(filetype, str_len, err)

    ! Create a scalar dataspace for a single string.
    ! call H5Screate_f(H5S_SCALAR, dspace_id, err)
    call h5screate_simple_f(rank, data_dims, dspace_id, err)

    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, trim(dsetname)//char(0), filetype, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, filetype, dset_data, data_dims, err)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
    call h5Tclose_f(filetype,err)
  end subroutine hdf5_write_data_char_0d

  subroutine hdf5_write_data_real_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(in) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, trim(dsetname), H5T_NATIVE_DOUBLE, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_DOUBLE, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_real_0d

  subroutine hdf5_write_data_real_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(in) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do
    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_DOUBLE, dspace_id, dset_id, err)
    CALL h5dwrite_f(dset_id, H5T_NATIVE_DOUBLE, dset_data, data_dims, err)
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_real_1d

  subroutine hdf5_write_data_real_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(in) :: dset_data(:,:)

    integer, parameter :: rank = 2
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_DOUBLE, dspace_id, dset_id, err)

    CALL h5dwrite_f(dset_id, H5T_NATIVE_DOUBLE, dset_data, data_dims, err)

    ! Read the dataset.
    ! CALL h5dread_f(dset_id, H5T_NATIVE_DOUBLE, data_out, data_dims, error)
    ! Close the dataset.
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_real_2d


  subroutine hdf5_write_data_real_3d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(in) :: dset_data(:,:,:)

    integer, parameter :: rank = 3
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims
    integer :: i, j, err

    ! Write the dataset.
    do i = 1, rank
      data_dims(i) = size(dset_data,i)
    end do

    ! Create the dataspace.
    call h5screate_simple_f(rank, data_dims, dspace_id, err)
    ! Create the dataset with default properties.
    call h5dcreate_f(file_id, dsetname, H5T_NATIVE_DOUBLE, dspace_id, dset_id, err)

    CALL h5dwrite_f(dset_id, H5T_NATIVE_DOUBLE, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - WRITING ", trim(dsetname)

    ! Read the dataset.
    ! CALL h5dread_f(dset_id, H5T_NATIVE_DOUBLE, data_out, data_dims, error)
    ! Close the dataset.
    CALL h5dclose_f(dset_id, err)
    call h5Sclose_f(dspace_id, err)
  end subroutine hdf5_write_data_real_3d



  subroutine hdf5_read_data_int_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(out) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id, err)
  end subroutine hdf5_read_data_int_0d

  subroutine hdf5_read_data_int_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(out) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_int_1d


  subroutine hdf5_read_data_int_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(out) :: dset_data(:,:)

    integer, parameter :: rank = 2
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_int_2d


  subroutine hdf5_read_data_int_3d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    integer, intent(out) :: dset_data(:,:,:)

    integer, parameter :: rank = 3
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_int_3d



  subroutine hdf5_read_data_real_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(out) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_real_0d

  subroutine hdf5_read_data_real_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(out) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_real_1d


  subroutine hdf5_read_data_real_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(out) :: dset_data(:,:)

    integer, parameter :: rank = 2
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_real_2d


  subroutine hdf5_read_data_real_3d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    real(8), intent(out) :: dset_data(:,:,:)

    integer, parameter :: rank = 3
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, dset_data, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)
  end subroutine hdf5_read_data_real_3d

  subroutine hdf5_read_data_logical_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(out) :: dset_data

    integer, parameter :: rank = 0
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err
    integer :: data_i

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, data_i, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)

    if(data_i == 1) then 
      dset_data = .true.
    else
      dset_data  = .false.
    endif
  end subroutine hdf5_read_data_logical_0d

  subroutine hdf5_read_data_logical_1d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(out) :: dset_data(:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err
    integer, allocatable :: data_i(:)
    
    allocate(data_i,mold=dset_data)

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, data_i, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)

    where(data_i == 1) dset_data = .true.
    where(data_i == 0) dset_data = .false.
  end subroutine hdf5_read_data_logical_1d

  subroutine hdf5_read_data_logical_2d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in) :: file_id
    character(len=*), intent(in)   :: dsetname
    logical, intent(out) :: dset_data(:,:)

    integer, parameter :: rank = 1
    integer(hid_t)                 :: dset_id, dspace_id
    integer(hsize_t), dimension(rank) :: data_dims, dset_maxdims
    integer :: err
    integer, allocatable :: data_i(:,:)
    allocate(data_i,mold=dset_data)

    call h5dopen_f(file_id, trim(dsetname), dset_id, err)
    call h5dget_space_f(dset_id, dspace_id, err)
    call h5sget_simple_extent_dims_f(dspace_id, data_dims, dset_maxdims, err)
    call h5dread_f(dset_id, h5t_native_integer, data_i, data_dims, err)
    if(err .ne. 0) print *, "ERROR - READING ", trim(dsetname)
    call h5sclose_f(dspace_id, err)
    call h5dclose_f(dset_id,err)

    where(data_i == 1) dset_data = .true.
    where(data_i == 0) dset_data = .false.
  end subroutine hdf5_read_data_logical_2d

  subroutine hdf5_read_data_char_0d(file_id, dsetname, dset_data)
    integer(hid_t), intent(in)  :: file_id
    character(len=*), intent(in) :: dsetname
    character(len=*), intent(out) :: dset_data

    integer(hid_t) :: dset_id, filetype, dspace_id
    integer :: err
    integer, parameter :: rank = 0
    integer(size_t) :: str_len
    integer(hsize_t), dimension(rank) :: data_dims

    ! remove default vals:
    dset_data = ''

    ! Open the dataset.
    call h5dopen_f(file_id, trim(dsetname)//char(0), dset_id, err)

    ! Get the datatype and its size.
    call h5dget_type_f(dset_id, filetype, err)
    call h5tget_size_f(filetype, str_len, err)

    ! Ensure the output variable can hold the string.
    if (str_len > len(dset_data)) then
      print *, 'Error: Output string length is too short.'
      call h5tclose_f(filetype, err)
      call h5dclose_f(dset_id, err)
      return
    end if

    ! Read the string data.
    call h5dread_f(dset_id, filetype, dset_data, data_dims, err)

    ! Close resources.
    call h5tclose_f(filetype, err)
    call h5dclose_f(dset_id, err)
  end subroutine hdf5_read_data_char_0d

end module H5InterfaceMod

