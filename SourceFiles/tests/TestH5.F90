program TestH5
    use hdf5
    use H5InterfaceMod
    use iso_c_binding, only: c_ptr
    implicit none

    integer :: ierr
    integer, parameter :: mode_create = 0, mode_open = 1
    integer, parameter :: ndims = 1
    integer, dimension(2) :: dims = [2, 2]
    integer, dimension(1) :: scalar = 42
    real(8), dimension(2,2) :: array = reshape([3.14d0, 2.718d0, 4.d0, 1.65d0],shape=[2,2])
    integer :: read_int, status
    real(8), dimension(2,2) :: read_arr = reshape([0d0, 0d0, 0d0, 0d0], shape=[2,2])
    logical :: exists
    integer, ALLOCATABLE :: dset_data(:,:), read_int_arr(:,:)
    integer, parameter :: beg = 3, end = 10
    integer(hid_t) :: file_id
    character(len=64) :: fn = "test_data.h5"
    integer :: i,j, err, var = 1137
    logical :: log_scalar = .true. 
    logical, allocatable :: log_array(:,:), read_log_arr(:,:)
    integer :: lb(5), ub(5), drank
    character(len=32) :: nu_com = 'RD', read_char="ECA"
    ! Initialize the dset_data array.
    allocate(dset_data(beg:end,beg:end-3))
    do i = beg, end
        do j = beg, end-3
            dset_data(i,j) = (i-1)*6 + j
      end do
    end do
    
    allocate(log_array,mold=dset_data)

    log_array(:,:) = .false.
    where(mod(dset_data(:,:),5) .eq. 0) log_array = .true.
    print *,lbound(log_array,1)

    CALL h5open_f(err)
    call h5_open_create_file(fn,mode_create, file_id)
    call h5_write_data(file_id, "scalar", var)

    drank = size(shape(dset_data))
    lb(1:drank) = lbound(dset_data)
    ub(1:drank) = ubound(dset_data)

    call h5_write_data(file_id, "dset_data_lb", lb(1:drank))
    call h5_write_data(file_id, "dset_data_ub", ub(1:drank))
    call h5_write_data(file_id,"dset_data", dset_data)

    call h5_write_data(file_id,"test_boools", log_array)
    call h5_write_data(file_id,"nu_com", nu_com)
    ! Close the file.
    CALL h5fclose_f(file_id, err)
    ! Close FORTRAN interface.
    deallocate(dset_data)

    !! READ DATA
    call h5_open_create_file(fn, mode_open, file_id)
    call h5_read_data(file_id, "dset_data_lb", lb(1:drank))
    call h5_read_data(file_id, "dset_data_ub", ub(1:drank))
    allocate(read_int_arr(lb(1):ub(1), lb(2):ub(2)))
    print *, "1d bounds after read", lbound(read_int_arr,1), UBOUND(read_int_arr,1)
    call h5_read_data(file_id, "dset_data", read_int_arr)
    print*, "read ints:", read_int_arr
    call h5_read_data(file_id, "nu_com", read_char)
    print*, "read char: ",trim( read_char )
    CALL h5fclose_f(file_id, err)
    CALL h5close_f(err)

    ! inquire(file=trim(fn),exist=exists)
    ! if(exists) then
    !     file_id = c_open_file(trim(fn)//char(0), mode_create)
    ! else
    !     file_id = c_open_file(trim(fn)//char(0), mode_create)
    ! end if 
    !
    ! ! Write a scalar integer
    ! ierr = c_write_int(file_id, "scalar_int", scalar, 0, null())
    ! if (ierr /= 0) then
    !     print *, "Error writing scalar integer"
    ! else
    !     print *, "Successfully wrote scalar integer"
    ! end if
    !
    ! ! Write a 1D double array
    ! print *, "Writing :", shape(array), size(array)
    ! ! call hdf5_write_data_2d_real8(file_id, "double_array", array)
    ! ierr = c_write_double(file_id, "double_array", array, 2, dims)
    ! if (ierr /= 0) then
    !     print *, "Error writing double array"
    ! else
    !     print *, "Successfully wrote double array"
    ! end if
    !
    ! status = c_read_int(file_id, "scalar_int"//char(0), read_int)
    ! if(status == 0) then
    !     print*, "READ INT:",read_int
    ! else
    !     print *, "FAILED TO READ INT"
    ! end if 
    ! status = c_read_dbl(file_id, "double_array"//char(0), read_arr)
    ! if(status == 0) then
    !     print*, "READ ARR:",read_arr
    ! else
    !     print *, "FAILED TO READ Arr"
    ! end if 
    !
    ! ierr = c_close_file(file_id)

end program TestH5

