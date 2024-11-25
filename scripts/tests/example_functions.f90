module test


   use decompMod, only : bounds_type


contains

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

    SHR_ASSERT((ltype >= 1 .and. ltype <= max_lunit), subname//': ltype out of bounds')

    if (ltype == istsoil .or. ltype == istcrop) then
       is_special = .false.
    else
       is_special = .true.
    end if

  end function landunit_is_special


  type(prior_weights_type) function constructor(bounds)
    !
    ! !DESCRIPTION:
    ! Initialize a prior_weights_type object
    !
    ! !ARGUMENTS:
    type(bounds_type), intent(in) :: bounds   ! processor bounds
    !
    ! !LOCAL VARIABLES:

    character(len=*), parameter :: subname = 'prior_weights_type constructor'
    ! ----------------------------------------------------------------------

    SHR_ASSERT(bounds%level == BOUNDS_LEVEL_PROC, subname // ': argument must be PROC-level bounds')

    allocate(constructor%pwtcol(bounds%begp:bounds%endp))
    allocate(constructor%cactive(bounds%begc:bounds%endc))

  end function constructor

  function old_weight_was_zero(this, bounds)
    !
    ! !DESCRIPTION:
    ! Returns a patch-level logical array that is true wherever the patch weight was zero
    ! prior to weight updates
    !
    ! !USES:
    !
    ! !ARGUMENTS:
    class(patch_state_updater_type), intent(in) :: this
    type(bounds_type), intent(in) :: bounds
    logical :: old_weight_was_zero(bounds%begp:bounds%endp)  ! function result
    !
    ! !LOCAL VARIABLES:
    integer :: p

    character(len=*), parameter :: subname = 'old_weight_was_zero'
    !-----------------------------------------------------------------------

    do p = bounds%begp, bounds%endp
       old_weight_was_zero(p) = (this%pwtgcell_old(p) == 0._r8)
    end do

  end function old_weight_was_zero

  logical function CNAllocate_carbon_only ( )
    cnallocate_carbon_only = .true.
  end function cnallocate_carbon_only

  pure function get_beg(bounds, subgrid_level) result(beg_index)
    !
    ! !DESCRIPTION:
    ! Get beginning bounds for a given subgrid level
    !
    ! subgrid_level should be one of the constants defined in this module:
    ! BOUNDS_SUBGRID_GRIDCELL, BOUNDS_SUBGRID_LANDUNIT, etc.
    !
    ! Returns -1 for invalid subgrid_level (does not abort in this case, in order to keep
    ! this function pure).
    !
    ! !USES:
    !
    ! !ARGUMENTS:
    integer :: beg_index  ! function result
    type(bounds_type), intent(in) :: bounds
    integer, intent(in) :: subgrid_level
    !
    ! !LOCAL VARIABLES:

    character(len=*), parameter :: subname = 'get_beg'
    !-----------------------------------------------------------------------

    select case (subgrid_level)
    case (BOUNDS_SUBGRID_GRIDCELL)
       beg_index = bounds%begg
    case (BOUNDS_SUBGRID_TOPOUNIT)
       beg_index = bounds%begt
    case (BOUNDS_SUBGRID_LANDUNIT)
       beg_index = bounds%begl
    case (BOUNDS_SUBGRID_COLUMN)
       beg_index = bounds%begc
    case (BOUNDS_SUBGRID_PATCH)
       beg_index = bounds%begp
    case (BOUNDS_SUBGRID_COHORT)
       beg_index = bounds%begCohort
    case default
       beg_index = -1
    end select

  end function get_beg

end module test
