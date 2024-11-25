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


end module test
