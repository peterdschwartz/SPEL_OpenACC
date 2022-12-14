module landunit_varcon

  !-----------------------------------------------------------------------
  ! !DESCRIPTION:
  ! Module containing landunit indices and associated variables and routines.
  !
  ! !USES:
  !
  !
  ! !PUBLIC TYPES:
  implicit none
  save
  private

  !------------------------------------------------------------------
  ! Initialize landunit type constants
  !------------------------------------------------------------------

  integer, parameter, public :: istsoil    = 1  !soil         landunit type (natural vegetation)
  integer, parameter, public :: istcrop    = 2  !crop         landunit type
  integer, parameter, public :: istice     = 3  !land ice     landunit type (glacier)
  integer, parameter, public :: istice_mec = 4  !land ice (multiple elevation classes) landunit type
  integer, parameter, public :: istdlak    = 5  !deep lake    landunit type (now used for all lakes)
  integer, parameter, public :: istwet     = 6  !wetland      landunit type (swamp, marsh, etc.)

  integer, parameter, public :: isturb_MIN = 7  !minimum urban type index
  integer, parameter, public :: isturb_tbd = 7  !urban tbd    landunit type
  integer, parameter, public :: isturb_hd  = 8  !urban hd     landunit type
  integer, parameter, public :: isturb_md  = 9  !urban md     landunit type
  integer, parameter, public :: isturb_MAX = 9  !maximum urban type index

  integer, parameter, public :: max_lunit  = 9  !maximum value that lun_pp%itype can have
                                        !(i.e., largest value in the above list)

  integer, parameter, public                   :: landunit_name_length = 40  ! max length of landunit names
  character(len=landunit_name_length), public  :: landunit_names(max_lunit)  ! name of each landunit type

  ! parameters that depend on the above constants

  integer, parameter, public :: numurbl = isturb_MAX - isturb_MIN + 1   ! number of urban landunits

  !
  ! !PUBLIC MEMBER FUNCTIONS:
  public :: landunit_varcon_init  ! initialize constants in this module
  public :: landunit_is_special   ! returns true if this is a special landunit

  !
  ! !PRIVATE MEMBER FUNCTIONS:
  private :: set_landunit_names   ! set the landunit_names vector
!-----------------------------------------------------------------------
!$acc declare copyin(istsoil    )
!$acc declare copyin(istcrop    )
!$acc declare copyin(istice     )
!$acc declare copyin(istice_mec )
!$acc declare copyin(istdlak    )
!$acc declare copyin(istwet     )
!$acc declare copyin(isturb_MIN )
!$acc declare copyin(isturb_tbd )
!$acc declare copyin(isturb_hd  )
!$acc declare copyin(isturb_md  )
!$acc declare copyin(isturb_MAX )
!$acc declare copyin(max_lunit  )
contains

  !-----------------------------------------------------------------------
  subroutine landunit_varcon_init()
    !
    ! !DESCRIPTION:
    ! Initialize constants in landunit_varcon
    !
    ! !USES:
    !
    ! !ARGUMENTS:
    !
    ! !LOCAL VARIABLES:

    character(len=*), parameter :: subname = 'landunit_varcon_init'
    !-----------------------------------------------------------------------

    call set_landunit_names()

  end subroutine landunit_varcon_init

  !-----------------------------------------------------------------------
  function landunit_is_special(ltype) result(is_special)
    !
    ! !DESCRIPTION:
    ! Returns true if the landunit type ltype is a special landunit; returns false otherwise
    !
    ! !USES:
    !
    ! !ARGUMENTS:
    logical :: is_special  ! function result
    integer :: ltype       ! landunit type of interest
    !
    ! !LOCAL VARIABLES:

    character(len=*), parameter :: subname = 'landunit_is_special'
    !-----------------------------------------------------------------------

    if (ltype == istsoil .or. ltype == istcrop) then
       is_special = .false.
    else
       is_special = .true.
    end if

  end function landunit_is_special

  !-----------------------------------------------------------------------
  subroutine set_landunit_names
    !
    ! !DESCRIPTION:
    ! Set the landunit_names vector
    !
    ! !USES:

    !
    character(len=*), parameter :: not_set = 'NOT_SET'
    character(len=*), parameter :: subname = 'set_landunit_names'
    !-----------------------------------------------------------------------

    landunit_names(:) = not_set

    landunit_names(istsoil) = 'vegetated_or_bare_soil'
    landunit_names(istcrop) = 'crop'
    landunit_names(istice) = 'landice'
    landunit_names(istice_mec) = 'landice_multiple_elevation_classes'
    landunit_names(istdlak) = 'deep_lake'
    landunit_names(istwet) = 'wetland'
    landunit_names(isturb_tbd) = 'urban_tbd'
    landunit_names(isturb_hd) = 'urban_hd'
    landunit_names(isturb_md) = 'urban_md'

    if (any(landunit_names == not_set)) then
      stop
    end if

  end subroutine set_landunit_names

end module landunit_varcon
