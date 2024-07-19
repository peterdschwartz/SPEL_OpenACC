program main()

  use shr_kind_mod    , only : r8 => shr_kind_r8
  use update_accMod
  use elm_varctl
  use filterMod
  use decompMod ,only : get_clump_bounds_gpu, gpu_clumps,gpu_procinfo
  use decompMod , only : get_proc_bounds, get_clump_bounds,procinfo,clumps, init_proc_clump_info
  use verificationMod
  use cudafor
  use landunit_varcon      , only : istice, istice_mec, istsoil
  use soilorder_varcon
  use timeInfoMod
  use pftvarcon
  use GridcellType
  use TopounitType
  use LandunitType
  use ColumnType
  use VegetationType
  use VegetationPropertiesType
  use elm_instMod
  use elm_initializeMod
  use LakeCon
  !#USE_START
  use elm_varorb
  use GridcellDataType
  use TopounitDataType
  use LandunitDataType
  use ColumnDataType
  use VegetationDataType
  use dynPriorWeightsMod
  use SharedParamsMod
  use SoilLittDecompMod
  use DecompCascadeCNMod
  use DecompCascadeBGCMod
  use AllocationMod
  use NitrifDenitrifMod
  use CNDecompCascadeConType
  use GapMortalityMod
  use SoilLittVertTranspMod
  use UrbanParamsType
  use CH4Mod
  use PhotosynthesisMod
  use domainMod
  use DaylengthMod
  use atm2lndMod
  use CanopyHydrologyMod
  use SurfaceRadiationMod
  use UrbanRadiationMod
  use CanopyFluxesMod
  use CanopyTemperatureMod
  use BareGroundFluxesMod
  use UrbanFluxesMod
  use LakeFluxesMod
  use DUSTMod
  use LakeTemperatureMod
  use SoilTemperatureMod
  use SoilFluxesMod
  use HydrologyNoDrainageMod
  use AerosolMod
  use SnowSnicarMod
  use LakeHydrologyMod
  use EcosystemDynMod
  use SedYieldMod
  use AnnualUpdateMod
  use DryDepVelocity
  use Ch4Mod
  use dynInitColumnsMod
  use dynConsBiogeophysMod
  use dynConsBiogeochemMod
  use reweightMod
  use subgridWeightsMod
  use NitrogenDynamicsMod
  use CarbonStateUpdate1Mod
  use NitrogenStateUpdate1Mod
  use PhosphorusStateUpdate1Mod
  use FireMod
  use dynPriorWeightsMod
  use dynSubgridDriverMod
  use dynPatchStateUpdaterMod
  use dynColumnStateUpdaterMod
  use BalanceCheckMod
  use EcosystemBalanceCheckMod
  use SurfaceAlbedoMod
  use UrbanAlbedoMod
  use VerticalProfileMod
  use glc2lndMod
  use shr_orb_mod_elm
  !#USE_END

  !=======================================!
  implicit none
  type(bounds_type)  ::  bounds_clump, bounds_proc 
  integer :: beg=1,fin=10, p, nclumps, nc, step_count
  real*8 :: temp
  integer :: err
#if _CUDA
      integer(kind=cuda_count_kind) :: heapsize,free1,free2,total
      integer  :: istat, val
#endif
  character(len=50) :: clump_input_char,pproc_input_char
  integer :: clump_input,pproc_input, fc, c, l, fp,g,j
  logical :: found_thawlayer
  integer :: k_frz
  integer :: begg, endg 
  real(r8) :: declin, declinp1
  real :: startt, stopt
  real(r8),allocatable :: icemask_dummy_arr(:)
  !========================== Initialize/Allocate variables =======================!
  !First, make sure the right number of inputs have been provided
  IF(COMMAND_ARGUMENT_COUNT() == 1) THEN
    WRITE(*,*)'ONE COMMAND-LINE ARGUMENT DETECTED, Defaulting to 1 site per clump'
    call get_command_argument(1,clump_input_char)
    READ(clump_input_char,*) clump_input
    pproc_input = 1 !1 site per clump

  ELSEIF(COMMAND_ARGUMENT_COUNT() == 2) THEN
     call get_command_argument(1,clump_input_char)
     call get_command_argument(2,pproc_input_char)
     READ(clump_input_char,*) clump_input
     READ(pproc_input_char,*) pproc_input
     !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  END IF

  call elm_init(clump_input,pproc_input, dtime_mod, year_curr)
  declin = -0.4030289369547867
  step_count = 0
  nclumps = procinfo%nclumps
  print *, "number of clumps", nclumps
  print *, "step:", step_count
  if(step_count == 0 ) then
    print *, "transferring data to GPU"
    call init_proc_clump_info()
    #ifdef _CUDA
      istat = cudaMemGetInfo(free1, total)
      print *, "Free1:",free1
    #endif
    !NOTE: Moved some update directives from 
    !  update_acc_variables() due to ICE
     !$acc update device( &
     !$acc        spinup_state            &
     !$acc       , nyears_ad_carbon_only   &
     !$acc       , spinup_mortality_factor &
     !$acc       , carbon_only &
     !$acc       , carbonphosphorus_only &
     !$acc       , carbonnitrogen_only &
     !$acc       ,use_crop            &
     !$acc       ,use_snicar_frc      &
     !$acc       ,use_snicar_ad       &
     !$acc       ,use_vancouver       &
     !$acc       ,use_mexicocity      &
     !$acc       ,use_noio            &
     !$acc       ,use_var_soil_thick  &
     !$acc       ,NFIX_PTASE_plant &
     !$acc       ,tw_irr &
     !$acc       ,use_erosion &
     !$acc       ,ero_ccycle  &
     !$acc       ,anoxia &
     !$acc       , glc_do_dynglacier &
     !$acc       , all_active &
     !$acc       , co2_ppmv &
     !$acc       , const_climate_hist &
     !$acc     )
     !$acc update device( &
     !$acc     KM_DECOMP_NH4        &
     !$acc     ,KM_DECOMP_NO3        &
     !$acc     ,KM_DECOMP_P          &
     !$acc     ,KM_NIT               &
     !$acc     ,KM_DEN               &
     !$acc     ,decompmicc_patch_vr(:,:) &
     !$acc     ,alpha_nfix(:)            &
     !$acc     ,alpha_ptase(:)           &
     !$acc     ,ccost_nfix(:)            &
     !$acc     ,pcost_nfix(:)            &
     !$acc     ,ccost_ptase(:)           &
     !$acc     ,ncost_ptase(:)           &
     !$acc     ,VMAX_NFIX(:)       &
     !$acc     ,KM_NFIX(:)         &
     !$acc     ,VMAX_PTASE(:)      &
     !$acc     ,KM_PTASE           &
     !$acc     ,lamda_ptase        &
     !$acc     ,i_vc(:)            &
     !$acc     ,s_vc(:)            &
     !$acc     ,leafcn_obs(:)          &
     !$acc     ,frootcn_obs(:)         &
     !$acc     ,livewdcn_obs(:)        &
     !$acc     ,deadwdcn_obs(:)        &
     !$acc     ,leafcp_obs(:)          &
     !$acc     ,frootcp_obs(:)         &
     !$acc     ,livewdcp_obs(:)        &
     !$acc     ,deadwdcp_obs(:)        &
     !$acc     ,leafcn_obs_flex(:,:)   &
     !$acc     ,frootcn_obs_flex(:,:)  &
     !$acc     ,livewdcn_obs_flex(:,:) &
     !$acc     ,deadwdcn_obs_flex(:,:) &
     !$acc     ,leafcp_obs_flex(:,:)   &
     !$acc     ,frootcp_obs_flex(:,:)  &
     !$acc     ,livewdcp_obs_flex(:,:) &
     !$acc     ,deadwdcp_obs_flex(:,:) &
     !$acc     ,fnr(:)        &
     !$acc     ,act25(:)      &
     !$acc     ,kcha(:)       &
     !$acc     ,koha(:)       &
     !$acc     ,cpha(:)       &
     !$acc     ,vcmaxha(:)    &
     !$acc     ,jmaxha(:)     &
     !$acc     ,tpuha(:)      &
     !$acc     ,lmrha(:)      &
     !$acc     ,vcmaxhd(:)    &
     !$acc     ,jmaxhd(:)     &
     !$acc     ,tpuhd(:)      &
     !$acc     ,lmrhd(:)      &
     !$acc     ,lmrse(:)      &
     !$acc     ,qe(:)         &
     !$acc     ,theta_cj(:)   &
     !$acc     ,bbbopt(:)     &
     !$acc     ,mbbopt(:)     &
     !$acc     ,nstor(:)      &
     !$acc     ,br_xr(:)      &
     !$acc     ,tc_stress     &
     !$acc     ,vcmax_np1(:)  &
     !$acc     ,vcmax_np2(:)  &
     !$acc     ,vcmax_np3(:)  &
     !$acc     ,vcmax_np4(:)  &
     !$acc     ,jmax_np1      &
     !$acc     ,jmax_np2      &
     !$acc     ,jmax_np3      &
     !$acc     ,laimax        &
     !$acc    ,rsub_top_globalmax &
     !------------- LakeCon ------------------!
     !$acc    ,fcrit      &
     !$acc    ,minz0lake  &
     !$acc     ,pudz &
     !$acc     ,depthcrit &
     !$acc     ,mixfact &
     !$acc     ,betavis &
     !$acc     ,lakepuddling &
     !$acc     ,lake_no_ed )

     !!!$acc update device(first_step, nlevgrnd, eccen, obliqr, lambm0, mvelpp )
     call update_acc_variables()
     !Note: copy/paste enter data directives here for FUT. 
     !      Will make this automatic in the future 
     !#ACC_COPYIN
      !$acc enter data copyin( &
      !$acc ch4_vars     , &
      !$acc col_ef     , &
      !$acc col_es     , &
      !$acc col_pp     , &
      !$acc col_wf     , &
      !$acc col_ws     , &
      !$acc grc_pp     , &
      !$acc lakestate_vars     , &
      !$acc lun_pp     , &
      !$acc soilstate_vars     , &
      !$acc solarabs_vars     , &
      !$acc top_pp     , &
      !$acc veg_ef     , &
      !$acc veg_pp      &
      !$acc   )

     call get_proc_bounds(bounds_proc)
     !$acc enter data copyin(filter(:),gpu_clumps(:), gpu_procinfo, proc_filter, bounds_proc )
     ! Calculate filters on device
     allocate(icemask_dummy_arr(begg:endg))
     icemask_dummy_arr(:) = 0.d0
     call setProcFilters(bounds_proc, proc_filter, .false., icemask_dummy_arr)

#if _CUDA
    ! Heap Limit may need to be increased for certain routines
    ! if using routine directives with many automatic arrays
    ! should be adjusted based on problem size
    istat = cudaDeviceGetLimit(heapsize, cudaLimitMallocHeapSize)
    print *, "SETTING Heap Limit from", heapsize
    heapsize = 10_8*1024_8*1024_8
    print *, "TO:",heapsize
    istat = cudaDeviceSetLimit(cudaLimitMallocHeapSize,heapsize)
    istat = cudaMemGetInfo(free1, total)
    print *, "Free1:",free1/1.E+9
#endif
    end if

    !NOTE: This may be adjusted depending on the timestep data 
    !      is output from 
    !TODO: make this info apart of input file itself

   !$acc enter data copyin( doalb, declinp1, declin )
   !$acc update device(dtime_mod, dayspyr_mod, &
   !$acc    year_curr, mon_curr, day_curr, secs_curr, nstep_mod, thiscalday_mod &
   !$acc  , nextsw_cday_mod, end_cd_mod, doalb )  

    ! Note: should add these to writeConstants in the future (as arguments?) 
    !$acc serial 
    declin = -0.4023686267583503
    declinp1 = -0.4023686267583503
    !$acc end serial

   #ifdef _OPENACC 
     #define gpuflag 1 
   #else 
     #define gpuflag 0
   #endif 

    !NOTE: Put ELM Subroutine call here 
    ! Default is currently LakeTemperature for others to reproduce
    ! and gain familiarity with this framework. 
    ! SPEL will be updated to auto-insert the all the appropriate
    ! calls for a given FUT in the future
    
    ! This is the "Naive" Implementation
    !#NAIVE
    !$acc parallel loop independent gang vector default(present) private(bounds_clump) 
    do nc=1, nclumps
      call get_clump_bounds_gpu(nc, bounds_clump)

    end do
    !#NAIVE

    ! This call should be used if running SPEL with "opt = True" and "add_acc = True" 
    ! and all internal loops have been accelerated -- must comment out the above

    #if _CUDA
      istat = cudaMemGetInfo(free1, total)
      print *, "free after kernel:",free1/1.E+9
    #endif
    deallocate(icemask_dummy_arr)
    print *, "done with unit-test execution"

end Program main
