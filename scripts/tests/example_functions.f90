module test

  type bounds_type
     ! The following variables correspond to "Local" quantities
     integer :: begg, endg                       ! beginning and ending gridcell index
     integer :: begt, endt                       ! beginning and ending topographic unit index
     integer :: begl, endl                       ! beginning and ending landunit index
     integer :: begc, endc                       ! beginning and ending column index
     integer :: begp, endp                       ! beginning and ending pft index
     integer :: begCohort, endCohort             ! beginning and ending cohort indices

     ! The following variables correspond to "Ghost/Halo" quantites
     integer :: begg_ghost, endg_ghost           ! beginning and ending gridcell index
     integer :: begt_ghost, endt_ghost           ! beginning and ending topounit index
     integer :: begl_ghost, endl_ghost           ! beginning and ending landunit index
     integer :: begc_ghost, endc_ghost           ! beginning and ending column index
     integer :: begp_ghost, endp_ghost           ! beginning and ending pft index
     integer :: begCohort_ghost, endCohort_ghost ! beginning and ending cohort indices

     ! The following variables correspond to "ALL" (=Local + Ghost) quantites
     integer :: begg_all, endg_all               ! beginning and ending gridcell index
     integer :: begt_all, endt_all               ! beginning and ending topounit index
     integer :: begl_all, endl_all               ! beginning and ending landunit index
     integer :: begc_all, endc_all               ! beginning and ending column index
     integer :: begp_all, endp_all               ! beginning and ending pft index
     integer :: begCohort_all, endCohort_all     ! beginning and ending cohort indices

     integer :: level                            ! whether defined on the proc or clump level
     integer :: clump_index                      ! if defined on the clump level, this gives the clump index
  end type bounds_type
  public bounds_type

   type, public :: column_nitrogen_flux
      ! harvest fluxes
      real(r8), pointer :: hrv_deadstemn_to_prod10n(:) => null() ! dead stem N harvest mortality to 10-year product pool (gN/m2/s)
      real(r8), pointer :: hrv_deadstemn_to_prod100n(:) => null() ! dead stem N harvest mortality to 100-year product pool (gN/m2/s)
      real(r8), pointer :: m_n_to_litr_met_fire(:, :) => null() ! N from leaf, froot, xfer and storage N to litter labile N by fire (gN/m3/s)
      contains
         procedure, public :: Init       => col_nf_init
   end type

   type(column_nitrogen_flux), target :: col_nf

contains


  subroutine col_nf_init(this, begc, endc)
    !
    ! !ARGUMENTS:
    class(column_nitrogen_flux) :: this
    integer, intent(in) :: begc,endc

    allocate(this%hrv_deadstemn_to_prod10n        (begc:endc))                   ; this%hrv_deadstemn_to_prod10n       (:)   = spval
    allocate(this%hrv_deadstemn_to_prod100n       (begc:endc))                   ; this%hrv_deadstemn_to_prod100n      (:)   = spval
    allocate(this%m_n_to_litr_met_fire            (begc:endc,1:nlevdecomp_full)) ; this%m_n_to_litr_met_fire           (:,:) = spval
  end subroutine col_nf_init

   subroutine test_parsing_sub(bounds, var1, var2, var3)

      type(bounds_type), intent(in) :: bounds
      real(r8), INTENT(IN) :: var1
      real(r8), INTENT(IN) :: var2
      real(r8), INTENT(IN) :: var3

      integer :: x, y

      x = bounds%begg + var1 + var2 + var3
   end subroutine test_parsing_sub

   subroutine call_sub(bounds)
      type(bounds_type), intent(in) :: bounds
      real(r8) :: input1, input2(bounds%begg), input3
      real(r8) :: local_var
      integer  :: g

      call test_parsing_sub(bounds, max(input1, local_var + input2(g)), col_nf%m_n_to_litr_met_fire(g), var3=input3)

   end subroutine call_sub

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

      !#py SHR_ASSERT((ltype >= 1 .and. ltype <= max_lunit), subname//': ltype out of bounds')

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

      !#py SHR_ASSERT(bounds%level == BOUNDS_LEVEL_PROC, subname//': argument must be PROC-level bounds')

      allocate (constructor%pwtcol(bounds%begp:bounds%endp))
      allocate (constructor%cactive(bounds%begc:bounds%endc))

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

   logical function CNAllocate_carbon_only()
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
