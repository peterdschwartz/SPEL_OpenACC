module CropType
  !-----------------------------------------------------------------------
  ! !DESCRIPTION:
  ! Module containing variables needed for the crop model
  !
  ! TODO(wjs, 2014-08-05) Move more crop-specific variables into here
  !
  ! !USES:
  use shr_kind_mod        , only : r8 => shr_kind_r8
  !#py use shr_log_mod         , only : errMsg => shr_log_errMsg
  !#py use spmdMod             , only : masterproc
  !#py use abortutils          , only : endrun
  use decompMod           , only : bounds_type
  use elm_varcon          , only : spval
  use elm_varpar          , only : crop_prog
  use elm_varctl          , only : iulog, use_crop
  use ColumnDataType      , only : col_es
  use VegetationDataType  , only : veg_es
  !
  ! !PUBLIC TYPES:
  implicit none
  private
  save
  !

  real(r8), public, parameter :: tcvp = 0.4_r8
  real(r8), public, parameter :: tcvt = 0.01_r8
  real(r8), public, parameter :: cst  = 283._r8

  ! !PUBLIC DATA TYPES:
  !
  ! Crop state variables structure
  type, public :: crop_type

     ! Note that cropplant and harvdate could be 2D to facilitate rotation
     integer , pointer :: nyrs_crop_active_patch  (:)   ! number of years this crop patch has been active (0 for non-crop patches)
     logical , pointer :: croplive_patch          (:)   ! patch Flag, true if planted, not harvested
     logical , pointer :: cropplant_patch         (:)   ! patch Flag, true if planted
     integer , pointer :: harvdate_patch          (:)   ! patch harvest date
     real(r8), pointer :: fertnitro_patch         (:)   ! patch fertilizer nitrogen

     real(r8), pointer :: gddplant_patch          (:)   ! patch accum gdd past planting date for crop       (ddays)
     real(r8), pointer :: gddtsoi_patch           (:)   ! patch growing degree-days from planting (top two soil layers) (ddays)
     real(r8), pointer :: crpyld_patch            (:)   ! patch crop yield (bu/acre)
     real(r8), pointer :: dmyield_patch           (:)   ! patch crop yield (t/ha)

     real(r8), pointer :: vf_patch                (:)   ! patch vernalization factor for cereal
     real(r8), pointer :: cphase_patch            (:)   ! phenology phase
     real(r8), pointer :: latbaset_patch          (:)   ! Latitude vary baset for gddplant (degree C)
     character(len=20) :: baset_mapping
     real(r8)          :: baset_latvary_intercept
     real(r8)          :: baset_latvary_slope

     real(r8), pointer :: cvt_patch               (:)   ! patch temperture coefficient of variance
     real(r8), pointer :: cvp_patch               (:)   ! patch precipitation coefficient of variance
     real(r8), pointer :: plantmonth_patch        (:)   ! month of planting
     real(r8), pointer :: plantday_patch          (:)   ! day of planting
     real(r8), pointer :: harvday_patch           (:)   ! day of harvest
     real(r8), pointer :: xt_patch                (:,:)   ! monthly average temperature
     real(r8), pointer :: xp_patch                (:,:)   ! monthly average precipitation
     real(r8), pointer :: xt_bar_patch            (:,:)   ! exponential weighted moving average temperature
     real(r8), pointer :: xp_bar_patch            (:,:)   ! exponential weighted moving average precipitation
     real(r8), pointer :: prev_xt_bar_patch       (:,:)   ! previous 12-months ewma temperature
     real(r8), pointer :: prev_xp_bar_patch       (:,:)   ! previous 12-months ewma precipitation
     real(r8), pointer :: p2ETo_patch             (:,:)   ! precipitation:evapotranspiration ratio (mm)
     real(r8), pointer :: p2ETo_bar_patch         (:,:)   ! ewma precipitation:evapotranspiration ratio (mm)
     real(r8), pointer :: prev_p2ETo_bar_patch    (:,:)   ! previous 12-months ewma precipitation:evapotranspiration ratio (mm)
     real(r8), pointer :: P2E_rm_patch            (:,:)   ! precipitation:evapotranspiration ratio 4-month sum (mm)
     real(r8), pointer :: ETo_patch               (:,:)   ! evapotranspiration ratio (mm)

   contains
     procedure, public  :: Init
     procedure, public  :: InitAccBuffer
     procedure, public  :: InitAccVars
     !#py procedure, public  :: Restart
     !#py procedure, public  :: UpdateAccVars
     procedure, public  :: CropIncrementYear

     procedure, private :: InitAllocate 
     procedure, private :: InitHistory
     procedure, private, nopass :: checkDates

  end type crop_type

  !------------------------------------------------------------------------

contains

  !-----------------------------------------------------------------------
  subroutine Init(this, bounds)
    !
    ! !ARGUMENTS:
    class(crop_type) , intent(inout) :: this
    type(bounds_type), intent(in)    :: bounds
    !
    ! !LOCAL VARIABLES:
    
    character(len=*), parameter :: subname = 'Init'
    !-----------------------------------------------------------------------
    
    call this%InitAllocate(bounds)

    if (crop_prog) then
       call this%InitHistory(bounds)
    end if

  end subroutine Init

  !-----------------------------------------------------------------------
  subroutine InitAllocate(this, bounds)
    !
    ! !ARGUMENTS:
    class(crop_type) , intent(inout) :: this
    type(bounds_type), intent(in)    :: bounds
    !
    ! !LOCAL VARIABLES:
    integer :: begp, endp
    
    character(len=*), parameter :: subname = 'InitAllocate'
    !-----------------------------------------------------------------------

    begp = bounds%begp; endp = bounds%endp

    allocate(this%nyrs_crop_active_patch (begp:endp)) ; this%nyrs_crop_active_patch (:) = 0
    allocate(this%croplive_patch         (begp:endp)) ; this%croplive_patch         (:) = .false.
    allocate(this%cropplant_patch        (begp:endp)) ; this%cropplant_patch        (:) = .false.
    allocate(this%harvdate_patch         (begp:endp)) ; this%harvdate_patch         (:) = huge(1) 
    allocate(this%fertnitro_patch        (begp:endp)) ; this%fertnitro_patch        (:) = spval
    allocate(this%gddplant_patch         (begp:endp)) ; this%gddplant_patch         (:) = spval
    allocate(this%gddtsoi_patch          (begp:endp)) ; this%gddtsoi_patch          (:) = spval
    allocate(this%crpyld_patch           (begp:endp)) ; this%crpyld_patch           (:) = spval
    allocate(this%dmyield_patch          (begp:endp)) ; this%dmyield_patch          (:) = spval
    allocate(this%vf_patch               (begp:endp)) ; this%vf_patch               (:) = 0.0_r8
    allocate(this%cphase_patch           (begp:endp)) ; this%cphase_patch           (:) = 0.0_r8
    allocate(this%latbaset_patch         (begp:endp)) ; this%latbaset_patch         (:) = spval
    allocate(this%cvt_patch              (begp:endp)) ; this%cvt_patch(:) = spval
    allocate(this%cvp_patch              (begp:endp)) ; this%cvp_patch(:) = spval
    allocate(this%plantmonth_patch       (begp:endp)) ; this%plantmonth_patch(:) = spval
    allocate(this%plantday_patch         (begp:endp)) ; this%plantday_patch(:) = spval
    allocate(this%harvday_patch          (begp:endp)) ; this%harvday_patch(:) = spval
    allocate(this%xt_patch               (begp:endp,1:12)) ; this%xt_patch(:,:) = spval
    allocate(this%xp_patch               (begp:endp,1:12)) ; this%xp_patch(:,:) = spval
    allocate(this%xt_bar_patch           (begp:endp,1:12)) ; this%xt_bar_patch(:,:) = spval
    allocate(this%xp_bar_patch           (begp:endp,1:12)) ; this%xp_bar_patch(:,:) = spval
    allocate(this%prev_xt_bar_patch      (begp:endp,1:12)) ; this%prev_xt_bar_patch (:,:) = spval
    allocate(this%prev_xp_bar_patch      (begp:endp,1:12)) ; this%prev_xp_bar_patch (:,:) = spval
    allocate(this%p2ETo_patch            (begp:endp,1:12)) ; this%p2ETo_patch(:,:) = spval
    allocate(this%p2ETo_bar_patch        (begp:endp,1:12)) ; this%p2ETo_bar_patch   (:,:) = spval
    allocate(this%prev_p2ETo_bar_patch   (begp:endp,1:12)) ; this%prev_p2ETo_bar_patch (:,:) = spval
    allocate(this%P2E_rm_patch           (begp:endp,1:12)) ; this%P2E_rm_patch(:,:) = spval
    allocate(this%ETo_patch              (begp:endp,1:12)) ; this%ETo_patch(:,:) = spval

  end subroutine InitAllocate

  !-----------------------------------------------------------------------
  subroutine InitHistory(this, bounds)
    !
    ! !USES:
    !#py use histFileMod    , only : hist_addfld1d, hist_addfld2d
    !
    ! !ARGUMENTS:
    class(crop_type),  intent(inout) :: this
    type(bounds_type), intent(in) :: bounds
    !
    ! !LOCAL VARIABLES:
    integer :: begp, endp
    
    character(len=*), parameter :: subname = 'InitHistory'
    !-----------------------------------------------------------------------
    
    begp = bounds%begp; endp = bounds%endp

    this%gddplant_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='GDDPLANT', units='ddays', &
         !#py avgflag='A', long_name='Accumulated growing degree days past planting date for crop', &
         !#py !#py ptr_patch=this%gddplant_patch, default='inactive')

    this%gddtsoi_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='GDDTSOI', units='ddays', &
         !#py avgflag='A', long_name='Growing degree-days from planting (top two soil layers)', &
         !#py !#py ptr_patch=this%gddtsoi_patch, default='inactive')

    this%crpyld_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='CRPYLD', units='bu/acre', &
         !#py avgflag='X', long_name='Crop yield (bu/acre)', &
         !#py !#py ptr_patch=this%crpyld_patch)

    this%dmyield_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='DMYIELD', units='t/ha', &
         !#py avgflag='X', long_name='Crop yield (t/ha)', &
         !#py !#py ptr_patch=this%dmyield_patch)

    this%cvt_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='CVT', units='1', &
         !#py avgflag='X', long_name='Temperature Coefficient of Variance', &
         !#py !#py ptr_patch=this%cvt_patch, default = 'inactive')

    this%cvp_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='CVP', units='1', &
         !#py avgflag='X', long_name='Precipitation Coefficient of Variance', &
         !#py !#py ptr_patch=this%cvp_patch, default = 'inactive')

    this%plantmonth_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='PLANTMONTH', units='1', &
         !#py avgflag='X', long_name='Month of planting', &
         !#py !#py ptr_patch=this%plantmonth_patch)

    this%plantday_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='PLANTDAY', units='doy', &
         !#py avgflag='M', long_name='Date of planting', &
         !#py !#py ptr_patch=this%plantday_patch)

    this%harvday_patch(begp:endp) = spval
    !#py call hist_addfld1d (fname='HARVESTDAY', units='doy', &
         !#py avgflag='M', long_name='Date of harvest', &
         !#py !#py ptr_patch=this%harvday_patch)

    this%xt_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='XT', units='Degrees K', type2d='month', &
         !#py avgflag='A', long_name='Monthly average temperature', &
         !#py !#py ptr_patch=this%xt_patch, default = 'inactive')

    this%xp_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='XP', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Monthly total precipitation', &
         !#py !#py ptr_patch=this%xp_patch, default = 'inactive')

    this%xt_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='XT_BAR', units='Degrees K', type2d='month', &
         !#py avgflag='A', long_name='EWMA Temperature', &
         !#py !#py ptr_patch=this%xt_bar_patch, default = 'inactive')

    this%xp_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='XP_bar', units='mm', type2d='month', &
         !#py avgflag='A', long_name='EMWA Precipitation', &
         !#py !#py ptr_patch=this%xp_bar_patch, default = 'inactive')

    this%prev_xt_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='PREV_XT_BAR', units='Degrees K', type2d='month', &
         !#py avgflag='A', long_name='Previous EWMA Temperature', &
         !#py !#py ptr_patch=this%prev_xt_bar_patch, default = 'inactive')

    this%prev_xp_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='PREV_XP_bar', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Previous EMWA Precipitation', &
         !#py !#py ptr_patch=this%prev_xp_bar_patch, default = 'inactive')

    this%p2ETo_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='P2ETO', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Precipitation:Evapotranspiration ratio', &
         !#py !#py ptr_patch=this%p2ETo_patch)

    this%p2ETo_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='P2ETO_bar', units='mm', type2d='month', &
         !#py avgflag='A', long_name='EWMA Precipitation:Evapotranspiration ratio', &
         !#py !#py ptr_patch=this%p2ETo_bar_patch)

    this%prev_p2ETo_bar_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='PREV_P2ETO_bar', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Previous EWMA Precipitation:Evapotranspirationratio', &
         !#py !#py ptr_patch=this%prev_p2ETo_bar_patch)

    this%P2E_rm_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='P2E_rm', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Precipitation:Evapotranspiration ratio 4-month sum', &
         !#py !#py ptr_patch=this%P2E_rm_patch)

    this%ETo_patch(begp:endp,:) = spval
    !#py call hist_addfld2d (fname='ETO', units='mm', type2d='month', &
         !#py avgflag='A', long_name='Reference Evapotranspiration', &
         !#py !#py ptr_patch=this%ETo_patch)

  end subroutine InitHistory


    !-----------------------------------------------------------------------
  subroutine InitAccBuffer (this, bounds)
    !
    ! !DESCRIPTION:
    ! Initialize accumulation buffer for all required module accumulated fields
    ! This routine set defaults values that are then overwritten by the
    ! restart file for restart or branch runs
    ! Each interval and accumulation type is unique to each field processed.
    ! Routine [initAccBuffer] defines the fields to be processed
    ! and the type of accumulation. 
    ! Routine [updateAccVars] does the actual accumulation for a given field.
    ! Fields are accumulated by calls to subroutine [update_accum_field]. 
    ! To accumulate a field, it must first be defined in subroutine [initAccVars] 
    ! and then accumulated by calls to [updateAccVars].
    !
    ! Should only be called if crop_prog is true
    !
    ! !USES 
    !#py use accumulMod       , only : init_accum_field
    !
    ! !ARGUMENTS:
    class(crop_type) , intent(in) :: this
    type(bounds_type), intent(in) :: bounds  

    !
    ! !LOCAL VARIABLES:
    integer, parameter :: not_used = huge(1)

    !---------------------------------------------------------------------

    !#py call init_accum_field (name='GDDPLANT', units='K', &
         !#py desc='growing degree-days from planting', accum_type='runaccum', accum_period=not_used,  &
         !#py !#py subgrid_type='pft', numlev=1, init_value=0._r8)

    !#py call init_accum_field (name='GDDTSOI', units='K', &
         !#py desc='growing degree-days from planting (top two soil layers)', accum_type='runaccum', accum_period=not_used,  &
         !#py !#py subgrid_type='pft', numlev=1, init_value=0._r8)

  end subroutine InitAccBuffer

  !-----------------------------------------------------------------------
  subroutine InitAccVars(this, bounds)
    !
    ! !DESCRIPTION:
    ! Initialize module variables that are associated with
    ! time accumulated fields. This routine is called for both an initial run
    ! and a restart run (and must therefore must be called after the restart file 
    ! is read in and the accumulation buffer is obtained)
    !
    ! !USES:
    !#py use accumulMod       , only : extract_accum_field
    !#py use clm_time_manager , only : get_nstep
    !
    ! !ARGUMENTS:
    class(crop_type),  intent(inout) :: this
    type(bounds_type), intent(in)    :: bounds
    !
    ! !LOCAL VARIABLES:
    integer  :: begp, endp
    integer  :: nstep
    integer  :: ier
    real(r8), pointer :: rbufslp(:)  ! temporary
    
    character(len=*), parameter :: subname = 'InitAccVars'
    !-----------------------------------------------------------------------
    
    begp = bounds%begp; endp = bounds%endp

    ! Allocate needed dynamic memory for single level pft field
    allocate(rbufslp(begp:endp), stat=ier)
    if (ier/=0) then
       !#py write(iulog,*)' in '
       !#py call endrun(msg=" allocation error for rbufslp"//&
            !#py !#py errMsg(__FILE__, __LINE__))
    endif

    !#py nstep = get_nstep()

    !#py call extract_accum_field ('GDDPLANT', rbufslp, nstep) 
    this%gddplant_patch(begp:endp) = rbufslp(begp:endp)

    !#py call extract_accum_field ('GDDTSOI', rbufslp, nstep) 
    this%gddtsoi_patch(begp:endp)  = rbufslp(begp:endp)

    deallocate(rbufslp)

  end subroutine InitAccVars

  !-----------------------------------------------------------------------
!#py   subroutine Restart(this, bounds, ncid, flag)
!#py     !
!#py     ! !USES:
!#py     !#py use restUtilMod
!#py     !#py use ncdio_pio
!#py     use VegetationType , only : veg_pp                
!#py     use pftvarcon      , only : npcropmin, npcropmax
!#py     !
!#py     ! !ARGUMENTS:
!#py     class(crop_type), intent(inout)  :: this
!#py     type(bounds_type), intent(in)    :: bounds 
!#py     type(file_desc_t), intent(inout) :: ncid   
!#py     character(len=*) , intent(in)    :: flag   
!#py     !
!#py     ! !LOCAL VARIABLES:
!#py     integer, pointer :: temp1d(:) ! temporary
!#py     integer :: restyear
!#py     integer :: p
!#py     logical :: readvar   ! determine if variable is on initial file
!#py     real(r8), pointer :: ptr2d(:,:) ! temp. pointers for slicing larger arrays
!#py     real(r8), pointer :: ptr1d(:)   ! temp. pointers for slicing larger arrays
!#py 
!#py     character(len=*), parameter :: subname = 'Restart'
!#py     !-----------------------------------------------------------------------
!#py 
!#py     if (use_crop) then
!#py        call restartvar(ncid=ncid, flag=flag, varname='nyrs_crop_active', xtype=ncd_int, &
!#py             dim1name='pft', &
!#py             long_name='Number of years this crop patch has been active (0 for non-crop patches)', &
!#py             units='years', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%nyrs_crop_active_patch)
!#py        if (flag == 'read' .and. .not. readvar) then
!#py           ! BACKWARDS_COMPATIBILITY(wjs, 2017-02-17) Old restart files did not have this
!#py           ! patch-level variable. Instead, they had a single scalar tracking the number
!#py           ! of years the crop model ran. Copy this scalar onto all *active* crop patches.
!#py 
!#py           ! Some arguments in the following restartvar call are irrelevant, because we
!#py           ! only call this for 'read'. I'm simply maintaining the old restartvar call.
!#py           call restartvar(ncid=ncid, flag=flag,  varname='restyear', xtype=ncd_int,  &
!#py                long_name='Number of years prognostic crop ran', units="years", &
!#py                interpinic_flag='copy', readvar=readvar, data=restyear)
!#py           if (readvar) then
!#py              do p = bounds%begp, bounds%endp
!#py                 if (veg_pp%itype(p) >= npcropmin .and. veg_pp%itype(p) <= npcropmax .and. &
!#py                      veg_pp%active(p)) then
!#py                    this%nyrs_crop_active_patch(p) = restyear
!#py                 end if
!#py              end do
!#py           end if
!#py        end if
!#py 
!#py        allocate(temp1d(bounds%begp:bounds%endp))
!#py        if (flag == 'write') then 
!#py           do p= bounds%begp,bounds%endp
!#py              if (this%croplive_patch(p)) then
!#py                 temp1d(p) = 1
!#py              else
!#py                 temp1d(p) = 0
!#py              end if
!#py           end do
!#py        end if
!#py        call restartvar(ncid=ncid, flag=flag,  varname='croplive', xtype=ncd_log,  &
!#py             dim1name='pft', &
!#py             long_name='Flag that crop is alive, but not harvested', &
!#py             interpinic_flag='interp', readvar=readvar, data=temp1d)
!#py        if (flag == 'read') then 
!#py           do p= bounds%begp,bounds%endp
!#py              if (temp1d(p) == 1) then
!#py                 this%croplive_patch(p) = .true.
!#py              else
!#py                 this%croplive_patch(p) = .false.
!#py              end if
!#py           end do
!#py        end if
!#py        deallocate(temp1d)
!#py 
!#py        allocate(temp1d(bounds%begp:bounds%endp))
!#py        if (flag == 'write') then 
!#py           do p= bounds%begp,bounds%endp
!#py              if (this%cropplant_patch(p)) then
!#py                 temp1d(p) = 1
!#py              else
!#py                 temp1d(p) = 0
!#py              end if
!#py           end do
!#py        end if
!#py        call restartvar(ncid=ncid, flag=flag,  varname='cropplant', xtype=ncd_log,  &
!#py             dim1name='pft', &
!#py             long_name='Flag that crop is planted, but not harvested' , &
!#py             interpinic_flag='interp', readvar=readvar, data=temp1d)
!#py        if (flag == 'read') then 
!#py           do p= bounds%begp,bounds%endp
!#py              if (temp1d(p) == 1) then
!#py                 this%cropplant_patch(p) = .true.
!#py              else
!#py                 this%cropplant_patch(p) = .false.
!#py              end if
!#py           end do
!#py        end if
!#py        deallocate(temp1d)
!#py 
!#py        call restartvar(ncid=ncid, flag=flag,  varname='harvdate', xtype=ncd_int,  &
!#py             dim1name='pft', long_name='harvest date', units='jday', nvalid_range=(/1,366/), & 
!#py             interpinic_flag='interp', readvar=readvar, data=this%harvdate_patch)
!#py 
!#py        call restartvar(ncid=ncid, flag=flag,  varname='vf', xtype=ncd_double,  &
!#py             dim1name='pft', long_name='vernalization factor', units='', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%vf_patch)
!#py 
!#py        call restartvar(ncid=ncid, flag=flag,  varname='cphase',xtype=ncd_double, &
!#py             dim1name='pft', long_name='crop phenology phase', &
!#py             units='0-not planted, 1-planted, 2-leaf emerge, 3-grain fill, 4-harvest', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%cphase_patch)
!#py        if (flag=='read' )then
!#py           call this%checkDates( )  ! Check that restart date is same calendar date (even if year is different)
!#py                                    ! This is so that it properly goes through
!#py                                    ! the crop phases
!#py        end if
!#py        call restartvar(ncid=ncid, flag=flag, varname='cvt', xtype=ncd_double,  &
!#py             dim1name='pft', &
!#py             long_name='temperature coefficient of variance', units='1', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%cvt_patch)
!#py 
!#py        call restartvar(ncid=ncid, flag=flag, varname='cvp', xtype=ncd_double,  &
!#py             dim1name='pft', &
!#py             long_name='precipitation coefficient of variance', units='1', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%cvp_patch)
!#py 
!#py        call restartvar(ncid=ncid, flag=flag, varname='plantmonth', xtype=ncd_double,  &
!#py             dim1name='pft', &
!#py             long_name='Month of planting', units='1', &
!#py             interpinic_flag='interp', readvar=readvar, data=this%plantmonth_patch)
!#py 
!#py        ptr2d => this%xt_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='xt', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='monthly average temperature', units='Kelvin', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%xp_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='xp', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='monthly average precipitation', units='mm', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%xt_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='xt_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='ewma temperature', units='Kelvin', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%xp_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='xp_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='ewma precipitation', units='mm', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%prev_xt_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='prev_xt_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='previous ewma temperature', units='Kelvin', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%prev_xp_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='prev_xp_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='previous ewma precipitation', units='mm', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%p2ETo_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='p2ETo', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='precipitation:evapotranspiration ratio', units='mm/s', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%p2ETo_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='p2ETo_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='ewma P:PET', units='1', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%prev_p2ETo_bar_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='prev_p2ETo_bar', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='previous ewma P:PET', units='1', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%P2E_rm_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='P2E_rm', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='precipitation:evapotranspiration ratio 4-month sum', units='mm', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py        ptr2d => this%ETo_patch(:,:)
!#py        call restartvar(ncid=ncid, flag=flag, varname='ETo', xtype=ncd_double, &
!#py             dim1name='pft',dim2name='month', switchdim=.true., &
!#py             long_name='reference evapotranspiration', units='mm', &
!#py             interpinic_flag='interp', readvar=readvar, data=ptr2d)
!#py 
!#py     end if
!#py 
!#py !#py !#py   end subroutine Restart

  !-----------------------------------------------------------------------
!#py   subroutine UpdateAccVars(this, bounds, temperature_vars)
!#py     !
!#py     ! !DESCRIPTION:
!#py     ! Update accumulated variables. Should be called every time step.
!#py     !
!#py     ! Should only be called if crop_prog is true.
!#py     !
!#py     ! !USES:
!#py     !#py use accumulMod       , only : update_accum_field, extract_accum_field, accumResetVal
!#py     use shr_const_mod    , only : SHR_CONST_CDAY, SHR_CONST_TKFRZ
!#py     !#py use clm_time_manager , only : get_step_size, get_nstep
!#py     use pftvarcon        , only : nwcereal, nwcerealirrig, mxtmp, baset
!#py     use TemperatureType  , only : temperature_type
!#py     use VegetationType   , only : veg_pp                
!#py     use ColumnType       , only : col_pp
!#py     !
!#py     ! !ARGUMENTS:
!#py     class(crop_type)       , intent(inout) :: this
!#py     type(bounds_type)      , intent(in)    :: bounds
!#py     type(temperature_type) , intent(in)    :: temperature_vars
!#py     !
!#py     ! !LOCAL VARIABLES:
!#py     integer :: p,c   ! indices
!#py     integer :: ivt   ! vegetation type
!#py     integer :: dtime ! timestep size [seconds]
!#py     integer :: nstep ! timestep number
!#py     integer :: ier   ! error status
!#py     integer :: begp, endp
!#py     real(r8), pointer :: rbufslp(:)      ! temporary single level - pft level
!#py     
!#py     character(len=*), parameter :: subname = 'UpdateAccVars'
!#py     !-----------------------------------------------------------------------
!#py     
!#py     begp = bounds%begp; endp = bounds%endp
!#py 
!#py     !#py dtime = get_step_size()
!#py     !#py nstep = get_nstep()
!#py 
!#py     ! Allocate needed dynamic memory for single level pft field
!#py 
!#py     allocate(rbufslp(begp:endp), stat=ier)
!#py     if (ier/=0) then
!#py        !#py write(iulog,*)'update_accum_hist allocation error for rbuf1dp'
!#py        !#py !#py call endrun(msg=errMsg(__FILE__, __LINE__))
!#py     endif
!#py 
!#py     ! Accumulate and extract GDDPLANT
!#py     
!#py     do p = begp,endp
!#py        if (this%croplive_patch(p)) then ! relative to planting date
!#py           ivt = veg_pp%itype(p)
!#py           rbufslp(p) = max(0._r8, min(mxtmp(ivt), &
!#py                veg_es%t_ref2m(p)-(SHR_CONST_TKFRZ + baset(ivt)))) &
!#py                * dtime/SHR_CONST_CDAY
!#py           if (ivt == nwcereal .or. ivt == nwcerealirrig) then
!#py              rbufslp(p) = rbufslp(p)*this%vf_patch(p)
!#py           end if
!#py        else
!#py           rbufslp(p) = accumResetVal
!#py        end if
!#py     end do
!#py     call update_accum_field  ('GDDPLANT', rbufslp, nstep)
!#py     call extract_accum_field ('GDDPLANT', this%gddplant_patch, nstep)
!#py 
!#py     ! Accumulate and extract GDDTSOI
!#py     ! In agroibis this variable is calculated
!#py     ! to 0.05 m, so here we use the top two soil layers
!#py 
!#py     do p = begp,endp
!#py        if (this%croplive_patch(p)) then ! relative to planting date
!#py           ivt = veg_pp%itype(p)
!#py           c = veg_pp%column(p)
!#py           rbufslp(p) = max(0._r8, min(mxtmp(ivt), &
!#py                ((col_es%t_soisno(c,1)*col_pp%dz(c,1) + &
!#py                col_es%t_soisno(c,2)*col_pp%dz(c,2))/(col_pp%dz(c,1)+col_pp%dz(c,2))) - &
!#py                (SHR_CONST_TKFRZ + baset(ivt)))) * dtime/SHR_CONST_CDAY
!#py           if (ivt == nwcereal .or. ivt == nwcerealirrig) then
!#py              rbufslp(p) = rbufslp(p)*this%vf_patch(p)
!#py           end if
!#py        else
!#py           rbufslp(p) = accumResetVal
!#py        end if
!#py     end do
!#py     call update_accum_field  ('GDDTSOI', rbufslp, nstep)
!#py     call extract_accum_field ('GDDTSOI', this%gddtsoi_patch, nstep)
!#py 
!#py     deallocate(rbufslp)
!#py 
!#py !#py   end subroutine UpdateAccVars

  !-----------------------------------------------------------------------
  subroutine CropIncrementYear (this, num_pcropp, filter_pcropp)
    !
    ! !DESCRIPTION:
    ! Increment the crop year, if appropriate
    !
    ! This routine should be called every time step
    !
    ! !USES:
    !#py use clm_time_manager , only : get_curr_date, is_first_step
    !
    ! !ARGUMENTS:
    class(crop_type) :: this
    integer , intent(in) :: num_pcropp       ! number of prog. crop patches in filter
    integer , intent(in) :: filter_pcropp(:) ! filter for prognostic crop patches
    !
    ! !LOCAL VARIABLES:
    integer :: kyr   ! current year
    integer :: kmo   ! month of year  (1, ..., 12)
    integer :: kda   ! day of month   (1, ..., 31)
    integer :: mcsec ! seconds of day (0, ..., seconds/day)
    integer :: fp, p
    !-----------------------------------------------------------------------

    ! Update nyrs when it's the end of the year (unless it's the very start of
    ! the
    ! run). This assumes that, if this patch is active at the end of the year,
    ! then it was
    ! active for the whole year.
    stop "CROPINCREMENT YEAR ERROR"
    if ((kmo == 1 .and. kda == 1 .and. mcsec == 0) ) then
       do fp = 1, num_pcropp
          p = filter_pcropp(fp)

          this%nyrs_crop_active_patch(p) = this%nyrs_crop_active_patch(p) + 1
       end do
    end if

  end subroutine CropIncrementYear

 !-----------------------------------------------------------------------
  subroutine checkDates( )
    !
    ! !DESCRIPTION: 
    ! Make sure the dates are compatible. The date given to startup the model
    ! and the date on the restart file must be the same although years can be
    ! different. The dates need to be checked when the restart file is being
    ! read in for a startup or branch case (they are NOT allowed to be different
    ! for a restart case).
    !
    ! For the prognostic crop model the date of planting is tracked and growing
    ! degree days is tracked (with a 20 year mean) -- so shifting the start dates
    ! messes up these bits of saved information.
    !
    ! !ARGUMENTS:
    !#py use clm_time_manager, only : get_driver_start_ymd, get_start_date
    use elm_varctl      , only : iulog
    use elm_varctl      , only : nsrest, nsrBranch, nsrStartup
    !
    ! !LOCAL VARIABLES:
    integer :: stymd       ! Start date YYYYMMDD from driver
    integer :: styr        ! Start year from driver
    integer :: stmon_day   ! Start date MMDD from driver
    integer :: rsmon_day   ! Restart date MMDD from restart file
    integer :: rsyr        ! Restart year from restart file
    integer :: rsmon       ! Restart month from restart file
    integer :: rsday       ! Restart day from restart file
    integer :: tod         ! Restart time of day from restart file
    character(len=*), parameter :: formDate = '(A,i4.4,"/",i2.2,"/",i2.2)' ! log output format
    character(len=32) :: subname = 'CropRest::checkDates'
    !-----------------------------------------------------------------------
    !
    ! If branch or startup make sure the startdate is compatible with the date
    ! on the restart file.
    !
    if ( nsrest == nsrBranch .or. nsrest == nsrStartup )then
       styr        = stymd / 10000
       stmon_day   = stymd - styr*10000
       rsmon_day = rsmon*100 + rsday
       !!if ( masterproc ) &
            !#py write(iulog,formDate) 'Date on the restart file is: ', rsyr, rsmon, rsday
       if ( stmon_day /= rsmon_day )then
          !#py write(iulog,formDate) 'Start date is: ', styr, stmon_day/100, &
               !#py (stmon_day - stmon_day/100)
          !#py call endrun(msg=' ERROR: For prognostic crop to work correctly, the start date (month and day)'// &
               !#py ' and the date on the restart file needs to match (years can be different)'//&
               !#py !#py errMsg(__FILE__, __LINE__))
       end if
    end if

  end subroutine checkDates

end module CropType

