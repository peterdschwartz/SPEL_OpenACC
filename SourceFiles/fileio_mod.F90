module fileio_mod
!#define DEBUG

        use shr_kind_mod   , only : r8 => shr_kind_r8

    implicit none

        ! public members
        integer, public :: funit_id(256) = 0

    ! public subroutines
        public :: fio_open
        public :: fio_close
        public :: fio_read
        public :: fio_write

        interface fio_read
                module procedure fio_read_int
                module procedure fio_read_real8
                module procedure fio_read_logical
                module procedure fio_read_logical_array
                module procedure fio_read_int_array
    module procedure fio_read_int_2Darray
                module procedure fio_read_real8_array
                module procedure fio_read_real8_2Darray
                module procedure fio_read_real8_3Darray
                module procedure fio_read_string_array
        end interface

contains

! error code
! 0: success
! 1: file does not exist
! 2: field name not found

    ! open file
        subroutine fio_open(unitid, filename, accesstype, overwritten, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),   intent(in)          :: filename
                integer,                        intent(in)              :: accesstype  ! 1: read, 2: write, 3: read write
                integer, optional,  intent(in)          :: overwritten ! 1. overwritten files(default), 0. append to files
                integer, optional,      intent(inout)   :: errcode

                ! local vars
                logical :: alive
                integer :: error
                character(len=256)              :: temp
                integer :: ow ! local over written

                if (present(overwritten)) then
                        ow = overwritten
                else
                        ow = 1
                endif

                error = 0
                inquire(file=filename, exist=alive)
                if (alive .eqv. .false.) then
                                if (accesstype .eq. 1) then
#if defined(DEBUG)
                            write (*, "(A)") "file does not exist"
#endif
                            error = 1
                            if (present(errcode)) then
                                    errcode = error
                            end if
                        else
                            funit_id(unitid) = unitid
#if defined(DEBUG)
                            write(*, "(A,A)") "create file: ", filename
#endif
                            open(unit=funit_id(unitid), file=filename, status="new", iostat=error, form='formatted')
                            if (present(errcode)) then
                                    errcode = error
                            end if
                        endif
                else
                    funit_id(unitid) = unitid
#if defined(DEBUG)
                    write(*, "(A,A)") "open file: ", filename
#endif
            ! read file
        if(accesstype .eq. 1) then
                                                open(unit=funit_id(unitid), file=filename, action="read", status="old", iostat=error, form='formatted')
                                else
            if(ow .eq. 1) then
                                        open(unit=funit_id(unitid), file=filename, status="new", iostat=error, form='formatted')
                                else
                          open(unit=funit_id(unitid), file=filename, status="old", position="append", iostat=error, form='formatted')
                                endif
                                endif

                        if (present(errcode)) then
                            errcode = error
                  end if

                endif

        end subroutine fio_open

        ! close file
        subroutine fio_close(unitid)
                implicit none

                integer, intent(in) :: unitid

                close(funit_id(unitid))

        end subroutine fio_close

        ! read int
        subroutine fio_read_int(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,   intent(in)              :: unitid
                character(len=*), intent(in)       :: fieldname
                integer,           intent(inout)   :: vardata
                integer, optional, intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

          rewind(unit=funit_id(unitid))

#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif

        do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (trim(line(:)) .eq. trim(fieldname)) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata

#if defined(DEBUG)
                                write (*, "(I6)") vardata
#endif
                                error = 0
                                exit
                        end if
                end do

                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_int

        ! read int array
        subroutine fio_read_int_array(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                integer,                        intent(inout)   :: vardata(:)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, "(10(2X,I6))") vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_int_array


  ! read real8 2D array
  subroutine fio_read_int_2Darray(unitid, fieldname, vardata, errcode)
    implicit none
    ! input
    integer,                    intent(in)              :: unitid
    character(len=*),   intent(in)              :: fieldname
    integer,                    intent(inout)   :: vardata(:,:)
    integer, optional,  intent(inout)   :: errcode

    ! local var
    integer                     :: ct
    integer                     :: error
    character(len=256)  :: line

      rewind(unit=funit_id(unitid))
#if defined(DEBUG)
    write(*, "(A,A)") "fieldname: ", fieldname
#endif
    do while(.true.)
      read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
      if (error/=0) then
        ! field not found
        write(*, "(A)") "not found"
        error = 2
        exit
      end if
            ! found
      if (line(:) .eq. fieldname) then
        read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
        write (*, "(10(2X,I6))") vardata
#endif
        error = 0
        exit
      end if
    end do
    if (present(errcode)) then
      errcode = error
    end if

  end subroutine fio_read_int_2Darray

        ! read real8
        subroutine fio_read_real8(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,          intent(in)              :: unitid
                character(len=*), intent(in)              :: fieldname
                real(r8),         intent(inout)   :: vardata
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                !write (*, "(F12.8)") vardata
                                write(*,*) vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_real8

        ! read real8 array
        subroutine fio_read_real8_array(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                real(r8),                       intent(inout)   :: vardata(:)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, "(10(2X,F12.4))") vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_real8_array

        ! read real8 2D array
        subroutine fio_read_real8_2Darray(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                real(r8),                       intent(inout)   :: vardata(:,:)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, "(10(2X,F12.4))") vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_real8_2Darray

        ! read real8 3D array
        subroutine fio_read_real8_3Darray(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                real(r8),                       intent(inout)   :: vardata(:,:, :)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, "(10(2X,F12.4))") vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_real8_3Darray

        ! read real8
        subroutine fio_read_string_array(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                character(len=*),       intent(inout)   :: vardata(:)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, "((3(2X,A)))") vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_string_array

        ! write file
        subroutine fio_write()
        end subroutine fio_write

        subroutine fio_read_logical(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,   intent(in)              :: unitid
                character(len=*), intent(in)       :: fieldname
                logical,           intent(inout)   :: vardata
                integer, optional, intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

          rewind(unit=funit_id(unitid))

#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif

        do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (trim(line(:)) .eq. trim(fieldname)) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata

#if defined(DEBUG)
                                write (*, "(L3)") vardata
#endif
                                error = 0
                                exit
                        end if
                end do

                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_logical
        ! read logical array
        subroutine fio_read_logical_array(unitid, fieldname, vardata, errcode)
                implicit none
                ! input
                integer,                        intent(in)              :: unitid
                character(len=*),       intent(in)              :: fieldname
                logical,                        intent(inout)   :: vardata(:)
                integer, optional,      intent(inout)   :: errcode

                ! local var
                integer                         :: ct
                integer                         :: error
                character(len=256)      :: line

            rewind(unit=funit_id(unitid))
#if defined(DEBUG)
                write(*, "(A,A)") "fieldname: ", fieldname
#endif
                do while(.true.)
                        read(unit=funit_id(unitid), fmt="(A)", iostat=error) line
                        if (error/=0) then
                                ! field not found
                                write(*, "(A)") "not found"
                                error = 2
                                exit
                        end if
            ! found
                        if (line(:) .eq. fieldname) then
                                read(unit=funit_id(unitid), fmt=*, iostat=error) vardata
#if defined(DEBUG)
                                write (*, *) vardata
#endif
                                error = 0
                                exit
                        end if
                end do
                if (present(errcode)) then
                        errcode = error
                end if

        end subroutine fio_read_logical_array

end module fileio_mod
