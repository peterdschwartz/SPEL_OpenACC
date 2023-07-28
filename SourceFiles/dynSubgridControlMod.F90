module dynSubgridControlMod

  !---------------------------------------------------------------------------
  !
  ! !DESCRIPTION:
  ! Defines a class for storing and querying control flags related to dynamic subgrid
  ! operation.
  !
  ! Note that this is implemented (essentially) as a singleton, so the only instance of
  ! this class is stored in this module. This is done for convenience, to avoid having to
  ! pass around the single instance just to query these control flags.
  !
  ! !USES:
!#py #include "shr_assert.h"
  !#py !#py use shr_log_mod        , only : errMsg => shr_log_errMsg
  !#py use abortutils         , only : endrun
  use elm_varctl         , only : fname_len
  !
  implicit none
  private
  !
  ! !PUBLIC MEMBER FUNCTIONS:
  !#py public :: dynSubgridControl_init
  public :: get_flanduse_timeseries ! return the value of the flanduse_timeseries file name
  public :: get_do_transient_pfts   ! return the value of the do_transient_pfts control flag
  public :: get_do_transient_crops  ! return the value of the do_transient_crops control flag
  public :: run_has_transient_landcover ! returns true if any aspects of prescribed transient landcover are enabled
  public :: get_do_harvest          ! return the value of the do_harvest control flag
  public :: get_for_testing_allow_non_annual_changes ! return true if user has requested to allow area changes at times other than the year boundary, for testing purposes
  public :: get_for_testing_zero_dynbal_fluxes ! return true if user has requested to set the dynbal water and energy fluxes to zero, for testing purposes
  !
  ! !PRIVATE MEMBER FUNCTIONS:
  !#py private :: read_namelist              ! read namelist variables
  private :: check_namelist_consistency ! check consistency of namelist settings
  !
  ! !PRIVATE TYPES:
  type, public :: dyn_subgrid_control_type

     character(len=256)  :: flanduse_timeseries ! transient landuse dataset
     logical :: do_transient_pfts   ! whether to apply transient natural PFTs from dataset
     logical :: do_transient_crops  ! whether to apply transient crops from dataset
     logical :: do_harvest          ! whether to apply harvest from dataset

     ! The following is only meant for testing: Whether area changes are allowed at times
     ! other than the year boundary. This should only arise in some test configurations
     ! where we artificially create changes more frequently so that we can run short
     ! tests. This flag is only used for error-checking, not controlling any model
     ! behavior.
     logical :: for_testing_allow_non_annual_changes

     ! The following is only meant for testing: If .true., set the dynbal water and
     ! energy fluxes to zero. This is needed in some tests where we have daily rather
     ! than annual glacier dynamics: if we allow the true dynbal adjustment fluxes in
     ! those tests, we end up with sensible heat fluxes of thousands of W m-2 or more,
     ! which causes CAM to blow up. However, note that setting it to true will break
     ! water and energy conservation!
     logical :: for_testing_zero_dynbal_fluxes

     logical  :: initialized   ! whether this object has been initialized
  end type dyn_subgrid_control_type

  type(dyn_subgrid_control_type), public :: dyn_subgrid_control_inst
  !$acc declare create(dyn_subgrid_control_inst)

  character(len=*), parameter, private :: sourcefile = &
       __FILE__

contains

  !-----------------------------------------------------------------------
!#py   subroutine dynSubgridControl_init( NLFilename )
!#py     !
!#py     ! !DESCRIPTION:
!#py     ! Initialize the dyn_subgrid_control settings.
!#py     !
!#py     ! !USES:
!#py     use spmdMod           , only : masterproc
!#py     !
!#py     ! !ARGUMENTS:
!#py     character(len=*), intent(in) :: NLFilename ! Namelist filename
!#py     !
!#py     ! !LOCAL VARIABLES:
!#py 
!#py     character(len=*), parameter :: subname = 'dynSubgridControl_init'
!#py     !-----------------------------------------------------------------------
!#py     !allocate(dyn_subgrid_control_inst%initialized            )
!#py     !allocate(    dyn_subgrid_control_inst%flanduse_timeseries  )
!#py     !allocate(    dyn_subgrid_control_inst%do_transient_pfts    )
!#py     !allocate(    dyn_subgrid_control_inst%do_transient_crops   )
!#py     !allocate(    dyn_subgrid_control_inst%do_harvest           )
!#py     !allocate(dyn_subgrid_control_inst%for_testing_allow_non_annual_changes)
!#py     !allocate(dyn_subgrid_control_inst%for_testing_zero_dynbal_fluxes      )
!#py 
!#py 
!#py     call read_namelist( NLFilename )
!#py     if (masterproc) then
!#py        call check_namelist_consistency
!#py     end if
!#py 
!#py     dyn_subgrid_control_inst%initialized = .true.
!#py 
!#py   end subroutine dynSubgridControl_init

  !-----------------------------------------------------------------------
!#py   subroutine read_namelist( NLFilename )
!#py     !
!#py     ! !DESCRIPTION:
!#py     ! Read dyn_subgrid_control namelist variables
!#py     !
!#py     ! !USES:
!#py     use fileutils      , only : getavu, relavu
!#py     use elm_nlUtilsMod , only : find_nlgroup_name
!#py     use elm_varctl     , only : iulog
!#py     use spmdMod        , only : masterproc, mpicom
!#py     use shr_mpi_mod    , only : shr_mpi_bcast
!#py     !
!#py     ! !ARGUMENTS:
!#py     character(len=*), intent(in) :: NLFilename   ! Namelist filename
!#py     !
!#py     ! !LOCAL VARIABLES:
!#py     ! temporary variables corresponding to the components of dyn_subgrid_control_type:
!#py     character(len=fname_len) :: flanduse_timeseries
!#py     logical :: do_transient_pfts
!#py     logical :: do_transient_crops
!#py     logical :: do_harvest
!#py     logical :: for_testing_allow_non_annual_changes
!#py     logical :: for_testing_zero_dynbal_fluxes
!#py     ! other local variables:
!#py     integer :: nu_nml    ! unit for namelist file
!#py     integer :: nml_error ! namelist i/o error flag
!#py 
!#py     character(len=*), parameter :: subname = 'read_namelist'
!#py     !-----------------------------------------------------------------------
!#py 
!#py     namelist /dynamic_subgrid/ &
!#py          flanduse_timeseries, &
!#py          do_transient_pfts, &
!#py          do_transient_crops, &
!#py          do_harvest, &
!#py          for_testing_allow_non_annual_changes, &
!#py          for_testing_zero_dynbal_fluxes
!#py 
!#py     ! Initialize options to default values, in case they are not specified in the namelist
!#py     flanduse_timeseries = ' '
!#py     do_transient_pfts  = .false.
!#py     do_transient_crops = .false.
!#py     do_harvest         = .false.
!#py     for_testing_allow_non_annual_changes = .false.
!#py     for_testing_zero_dynbal_fluxes = .false.
!#py 
!#py     if (masterproc) then
!#py        nu_nml = getavu()
!#py        open( nu_nml, file=trim(NLFilename), status='old', iostat=nml_error )
!#py        call find_nlgroup_name(nu_nml, 'dynamic_subgrid', status=nml_error)
!#py        if (nml_error == 0) then
!#py           read(nu_nml, nml=dynamic_subgrid, iostat=nml_error)
!#py           if (nml_error /= 0) then
!#py              call endrun(msg='ERROR reading dynamic_subgrid namelist'//errMsg(sourcefile, __LINE__))
!#py           end if
!#py        else
!#py           call endrun(msg='ERROR finding dynamic_subgrid namelist'//errMsg(sourcefile, __LINE__))
!#py        end if
!#py        close(nu_nml)
!#py        call relavu( nu_nml )
!#py     endif
!#py 
!#py     call shr_mpi_bcast (flanduse_timeseries, mpicom)
!#py     call shr_mpi_bcast (do_transient_pfts, mpicom)
!#py     call shr_mpi_bcast (do_transient_crops, mpicom)
!#py     call shr_mpi_bcast (do_harvest, mpicom)
!#py     call shr_mpi_bcast (for_testing_allow_non_annual_changes, mpicom)
!#py     call shr_mpi_bcast (for_testing_zero_dynbal_fluxes, mpicom)
!#py 
!#py     dyn_subgrid_control_inst%flanduse_timeseries = flanduse_timeseries
!#py     dyn_subgrid_control_inst%do_transient_pfts = do_transient_pfts
!#py     dyn_subgrid_control_inst%do_transient_crops = do_transient_crops
!#py     dyn_subgrid_control_inst%do_harvest = do_harvest
!#py     dyn_subgrid_control_inst%for_testing_allow_non_annual_changes = for_testing_allow_non_annual_changes
!#py     dyn_subgrid_control_inst%for_testing_zero_dynbal_fluxes = for_testing_zero_dynbal_fluxes
!#py 
!#py     if (masterproc) then
!#py        write(iulog,*) ' '
!#py        write(iulog,*) 'dynamic_subgrid settings:'
!#py        write(iulog,nml=dynamic_subgrid)
!#py        write(iulog,*) ' '
!#py     end if
!#py 
!#py   end subroutine read_namelist

  !-----------------------------------------------------------------------
  subroutine check_namelist_consistency
    !
    ! !DESCRIPTION:
    ! Check consistency of namelist settingsn
    !
    ! !USES:
    use elm_varctl     , only : iulog, use_fates, use_cn, use_crop
    !
    ! !ARGUMENTS:
    !
    ! !LOCAL VARIABLES:

    character(len=*), parameter :: subname = 'check_namelist_consistency'
    !-----------------------------------------------------------------------

    if (dyn_subgrid_control_inst%flanduse_timeseries == ' ') then
       if (dyn_subgrid_control_inst%do_transient_pfts) then
          !#py write(iulog,*) 'ERROR: do_transient_pfts can only be true if you are running with'
          !#py write(iulog,*) 'a flanduse_timeseries file (currently flanduse_timeseries is blank)'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
       if (dyn_subgrid_control_inst%do_transient_crops) then
          !#py write(iulog,*) 'ERROR: do_transient_crops can only be true if you are running with'
          !#py write(iulog,*) 'a flanduse_timeseries file (currently flanduse_timeseries is blank)'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
       if (dyn_subgrid_control_inst%do_harvest) then
          !#py write(iulog,*) 'ERROR: do_harvest can only be true if you are running with'
          !#py write(iulog,*) 'a flanduse_timeseries file (currently flanduse_timeseries is blank)'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
    end if

    if (dyn_subgrid_control_inst%do_transient_pfts) then
       if (use_fates) then
          !#py write(iulog,*) 'ERROR: do_transient_pfts is incompatible with use_fates'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
    end if

    if (dyn_subgrid_control_inst%do_transient_crops) then
       if (use_fates) then
          ! NOTE(wjs, 2017-01-13) ED / FATES does not currently have a mechanism for
          ! changing its column areas, with the consequent changes in aboveground biomass
          ! per unit area. See https://github.com/NGEET/ed-clm/issues/173
          !#py write(iulog,*) 'ERROR: do_transient_crops does not currently work with use_fates'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
    end if

    if (dyn_subgrid_control_inst%do_harvest) then
       if (.not. use_cn) then
          !#py write(iulog,*) 'ERROR: do_harvest can only be true if use_cn is true'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
       if (use_fates) then
          !#py write(iulog,*) 'ERROR: do_harvest currently does not work with use_fates'
          !#py !#py call endrun(msg=errMsg(sourcefile, __LINE__))
       end if
    end if

  end subroutine check_namelist_consistency

  !-----------------------------------------------------------------------
  character(len=fname_len) function get_flanduse_timeseries()
    ! !DESCRIPTION:
    ! Return the value of the flanduse_timeseries file name

    character(len=*), parameter :: subname = 'get_flanduse_timeseries'
    !-----------------------------------------------------------------------

    get_flanduse_timeseries = dyn_subgrid_control_inst%flanduse_timeseries

  end function get_flanduse_timeseries

  !-----------------------------------------------------------------------
  logical function get_do_transient_pfts()
    ! !DESCRIPTION:
    ! Return the value of the do_transient_pfts control flag
    !-----------------------------------------------------------------------
    !$acc routine seq 
    !SHR_ASSERT(dyn_subgrid_control_inst%initialized, errMsg(sourcefile, __LINE__))

    get_do_transient_pfts = dyn_subgrid_control_inst%do_transient_pfts

  end function get_do_transient_pfts

  !-----------------------------------------------------------------------
  logical function get_do_transient_crops()
    ! !DESCRIPTION:
    ! Return the value of the do_transient_crops control flag
    !-----------------------------------------------------------------------
    !$acc routine seq 
    get_do_transient_crops = dyn_subgrid_control_inst%do_transient_crops

  end function get_do_transient_crops

  !-----------------------------------------------------------------------
  logical function run_has_transient_landcover()
    ! !DESCRIPTION:
    ! Returns true if any aspects of prescribed transient landcover are enabled
    !-----------------------------------------------------------------------
    !$acc routine seq
    run_has_transient_landcover = &
         (dyn_subgrid_control_inst%do_transient_pfts .or. &
         dyn_subgrid_control_inst%do_transient_crops)
  end function run_has_transient_landcover

  !-----------------------------------------------------------------------
  logical function get_do_harvest()
    ! !DESCRIPTION:
    ! Return the value of the do_harvest control flag
    !-----------------------------------------------------------------------
    !$acc routine seq 

    get_do_harvest = dyn_subgrid_control_inst%do_harvest

  end function get_do_harvest

  !-----------------------------------------------------------------------
  logical function get_for_testing_allow_non_annual_changes()
    !
    ! !DESCRIPTION:
    ! Return true if the user has requested to allow area changes at times other than the
    ! year boundary. (This should typically only be true for testing.) (This only
    ! controls error-checking, not any operation of the code.)
    !-----------------------------------------------------------------------
    !$acc routine seq 

    get_for_testing_allow_non_annual_changes = dyn_subgrid_control_inst%for_testing_allow_non_annual_changes

  end function get_for_testing_allow_non_annual_changes

  !-----------------------------------------------------------------------
  logical function get_for_testing_zero_dynbal_fluxes()
    !$acc routine seq
    ! !DESCRIPTION:
    ! Return true if the user has requested to set the dynbal water and energy fluxes to
    ! zero. This should typically only be true for testing: This is needed in some tests
    ! where we have daily rather than annual glacier dynamics: if we allow the true dynbal
    ! adjustment fluxes in those tests, we end up with sensible heat fluxes of thousands
    ! of W m-2 or more, which causes CAM to blow up. However, note that setting it to
    ! true will break water and energy conservation!
    ! -----------------------------------------------------------------------

    get_for_testing_zero_dynbal_fluxes = dyn_subgrid_control_inst%for_testing_zero_dynbal_fluxes

  end function get_for_testing_zero_dynbal_fluxes

end module dynSubgridControlMod
