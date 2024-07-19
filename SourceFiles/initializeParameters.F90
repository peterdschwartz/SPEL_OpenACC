module initializeParameters

#include "unittest_defs.h"
  use elm_varcon
  use elm_varpar
  use soilorder_varcon
  use pftvarcon
  !#USE_START
  use NitrifDenitrifMod
  use SoilLittDecompMod
  use DecompCascadeCNMod
  use DecompCascadeBGCMod
  use SoilLittVertTranspMod
  use PhenologyMod
  use SnowSnicarMod
  use AllocationMod
  use SharedParamsMod
  use PhotosynthesisMod
  use GapMortalityMod
  use CH4Mod
  use SurfaceAlbedoMod
  use dynSubgridControlMod
  !#USE_END
  public :: init_params
  contains

      subroutine set_namelist_vars()
        use CH4varcon
        use elm_varctl
        use UrbanParamsType

        implicit none

#ifdef ALLOCATIONMOD
        select case(nu_com)
            case('RD') ! relative demand mode, same as CLM-CNP Yang 2014
                nu_com_leaf_physiology = .false.
                nu_com_root_kinetics   = .false.
                nu_com_phosphatase     = .false.
                nu_com_nfix            = .false.
            case('ECA') ! ECA competition version of CLM-CNP
                nu_com_leaf_physiology = .true. ! leaf level physiology must be true if using ECA
                nu_com_root_kinetics   = .true. ! root uptake kinetics must be true if using ECA
                nu_com_phosphatase = .true.     ! new phosphatase activity
                nu_com_nfix = .true.            ! new fixation
            case('MIC') ! MIC outcompete plant version of CLM-CNP
                nu_com_leaf_physiology = .true.
                nu_com_root_kinetics   = .true.
                nu_com_phosphatase = .true.
                nu_com_nfix = .true.
        end select
 #endif

        !dynSubgridControlMod
#ifdef DYNSUBGRIDCONTROLMOD
          allocate(dyn_subgrid_control_inst%initialized)
          allocate(    dyn_subgrid_control_inst%flanduse_timeseries)
          allocate(    dyn_subgrid_control_inst%do_transient_pfts  )
          allocate(    dyn_subgrid_control_inst%do_transient_crops )
          allocate(    dyn_subgrid_control_inst%do_harvest         )
          allocate(dyn_subgrid_control_inst%for_testing_allow_non_annual_changes)
          allocate(dyn_subgrid_control_inst%for_testing_zero_dynbal_fluxes      )

          dyn_subgrid_control_inst%flanduse_timeseries = ' '
          dyn_subgrid_control_inst%do_transient_pfts  = .false.
          dyn_subgrid_control_inst%do_transient_crops = .false.
          dyn_subgrid_control_inst%do_harvest  = .false.
          dyn_subgrid_control_inst%for_testing_allow_non_annual_changes = .false.
          dyn_subgrid_control_inst%for_testing_zero_dynbal_fluxes = .false.

          dyn_subgrid_control_inst%initialized = .true.
#endif

        allocate( smax        (0:nsoilorder) ); smax         (:) = nan
        allocate( ks_sorption (0:nsoilorder) ); ks_sorption  (:) = nan
        allocate( r_weather   (0:nsoilorder) ); r_weather    (:) = nan
        allocate( r_adsorp    (0:nsoilorder) ); r_adsorp     (:) = nan
        allocate( r_desorp    (0:nsoilorder) ); r_desorp     (:) = nan
        allocate( r_occlude   (0:nsoilorder) ); r_occlude    (:) = nan
        allocate(k_s1_biochem (0:nsoilorder) ); k_s1_biochem (:) = nan
        allocate(k_s2_biochem (0:nsoilorder) ); k_s2_biochem (:) = nan
        allocate(k_s3_biochem (0:nsoilorder) ); k_s3_biochem (:) = nan
        allocate(k_s4_biochem (0:nsoilorder) ); k_s4_biochem (:) = nan
        allocate(r_mort_soilorder (0:nsoilorder) ); r_mort_soilorder (:) = nan

        !$acc update device( &
        !$acc        spinup_state            &
        !$acc       , nyears_ad_carbon_only   &
        !$acc       , spinup_mortality_factor &
        !$acc       , carbon_only &
        !$acc       , carbonphosphorus_only &
        !$acc       , carbonnitrogen_only &
        !$acc       , urban_hac &
        !$acc       , use_century_decomp  &
        !$acc       , use_cn              &
        !$acc       , use_crop            &
        !$acc       , use_dynroot         &
        !$acc       , use_fates           &
        !$acc       , use_lch4            &
        !$acc       , use_vertsoilc       &
        !$acc     )

        !$acc update device(     &
        !$acc allowlakeprod      &
        !$acc ,replenishlakec    &
        !$acc ,fin_use_fsat      &
        !$acc ,ch4offline        &
        !$acc ,ch4rmcnlim        &
        !$acc ,anoxicmicrosites  &
        !$acc ,ch4frzout         &
        !$acc ,usefrootc         &
        !$acc ,transpirationloss &
        !$acc ,use_aereoxid_prog &
        !$acc ,usephfact         )


      end subroutine set_namelist_vars


      subroutine init_params(bounds)
        use decompMod , only : bounds_type
        implicit none
        type(bounds_type)  , intent(in) :: bounds

        !AllocationMod
#ifdef ALLOCATIONMOD
           allocate(AllocParamsInst%bdnr              )
           allocate(AllocParamsInst%dayscrecover      )
           allocate(AllocParamsInst%compet_plant_no3  )
           allocate(AllocParamsInst%compet_plant_nh4  )
           allocate(AllocParamsInst%compet_decomp_no3 )
           allocate(AllocParamsInst%compet_decomp_nh4 )
           allocate(AllocParamsInst%compet_denit      )
           allocate(AllocParamsInst%compet_nit        )
           if ( crop_prog )then
              allocate(arepr(bounds%begp:bounds%endp)); arepr(bounds%begp : bounds%endp) = nan
              allocate(aroot(bounds%begp:bounds%endp)); aroot(bounds%begp : bounds%endp) = nan
           end if
#endif

        !CH4Mod
#ifdef CH4MOD
           allocate(CH4ParamsInst%q10ch4              )
           allocate(CH4ParamsInst%q10ch4base          )
           allocate(CH4ParamsInst%f_ch4               )
           allocate(CH4ParamsInst%rootlitfrac         )
           allocate(CH4ParamsInst%cnscalefactor       )
           allocate(CH4ParamsInst%redoxlag            )
           allocate(CH4ParamsInst%lake_decomp_fact    )
           allocate(CH4ParamsInst%redoxlag_vertical   )
           allocate(CH4ParamsInst%pHmax               )
           allocate(CH4ParamsInst%pHmin               )
           allocate(CH4ParamsInst%oxinhib             )
           allocate(CH4ParamsInst%vmax_ch4_oxid       )
           allocate(CH4ParamsInst%k_m                 )
           allocate(CH4ParamsInst%q10_ch4oxid         )
           allocate(CH4ParamsInst%smp_crit            )
           allocate(CH4ParamsInst%k_m_o2              )
           allocate(CH4ParamsInst%k_m_unsat           )
           allocate(CH4ParamsInst%vmax_oxid_unsat     )
           allocate(CH4ParamsInst%aereoxid            )
           allocate(CH4ParamsInst%scale_factor_aere   )
           allocate(CH4ParamsInst%nongrassporosratio  )
           allocate(CH4ParamsInst%unsat_aere_ratio    )
           allocate(CH4ParamsInst%porosmin            )
           allocate(CH4ParamsInst%vgc_max             )
           allocate(CH4ParamsInst%satpow              )
           allocate(CH4ParamsInst%scale_factor_gasdiff)
           allocate(CH4ParamsInst%scale_factor_liqdiff)
           allocate(CH4ParamsInst%capthick            )
           allocate(CH4ParamsInst%f_sat               )
           allocate(CH4ParamsInst%qflxlagd            )
           allocate(CH4ParamsInst%highlatfact         )
           allocate(CH4ParamsInst%q10lakebase         )
           allocate(CH4ParamsInst%atmch4              )
           allocate(CH4ParamsInst%rob                 )
#endif

        !GapMortalityMod
#ifdef GAPMORTALITYMOD
          allocate(CNGapMortParamsInst%am, CNGapMortParamsInst%k_mort)
#endif

        !PhotosynthesisMod
#ifdef PHOTOSYNTHESISMOD
        allocate( params_inst%krmax       (0:mxpft)         )
        allocate( params_inst%kmax        (0:mxpft,nvegwcs) )
        allocate( params_inst%psi50       (0:mxpft,nvegwcs) )
        allocate( params_inst%ck          (0:mxpft,nvegwcs) )
        allocate( params_inst%psi_soil_ref(0:mxpft)         )
#endif

        !SharedParamsMod
#ifdef SHAREDPARAMSMOD
          allocate(ParamsShareInst%Q10_mr               )
          allocate(ParamsShareInst%Q10_hr               )
          allocate(ParamsShareInst%minpsi               )
          allocate(ParamsShareInst%cwd_fcel             )
          allocate(ParamsShareInst%cwd_flig             )
          allocate(ParamsShareInst%froz_q10             )
          allocate(ParamsShareInst%decomp_depth_efolding)
          allocate(ParamsShareInst%mino2lim             )
          allocate(ParamsShareInst%organic_max          )
#endif

        !PhenologyMod
#ifdef PHENOLOGYMOD
           allocate(PhenolParamsInst%crit_dayl       )
           allocate(PhenolParamsInst%crit_dayl_stress)
           allocate(PhenolParamsInst%cumprec_onset   )
           allocate(PhenolParamsInst%ndays_on        )
           allocate(PhenolParamsInst%ndays_off       )
           allocate(PhenolParamsInst%fstor2tran      )
           allocate(PhenolParamsInst%crit_onset_fdd  )
           allocate(PhenolParamsInst%crit_onset_swi  )
           allocate(PhenolParamsInst%soilpsi_on      )
           allocate(PhenolParamsInst%crit_offset_fdd )
           allocate(PhenolParamsInst%crit_offset_swi )
           allocate(PhenolParamsInst%soilpsi_off     )
           allocate(PhenolParamsInst%lwtop           )
#endif
        !---------------------------------------------------
        !SnowSnicarMod
#ifdef SNOWSNICARMOD
           allocate(snowage_tau(idx_rhos_max,idx_Tgrd_max,idx_T_max))
           allocate(snowage_kappa(idx_rhos_max,idx_Tgrd_max,idx_T_max))
           allocate(snowage_drdt0(idx_rhos_max,idx_Tgrd_max,idx_T_max))
#endif

        !NitrifDenitrifMod
#ifdef NITRIFDENITRIFMOD
          allocate(NitrifDenitrifParamsInst%k_nitr_max           )
          allocate(NitrifDenitrifParamsInst%surface_tension_water)
          allocate(NitrifDenitrifParamsInst%rij_kro_a            )
          allocate(NitrifDenitrifParamsInst%rij_kro_alpha        )
          allocate(NitrifDenitrifParamsInst%rij_kro_beta         )
          allocate(NitrifDenitrifParamsInst%rij_kro_gamma        )
          allocate(NitrifDenitrifParamsInst%rij_kro_delta        )
#endif
        !SoilLittDecompMod
#ifdef SOILLITTDECOMPMOD
          allocate(CNDecompParamsInst%dnp)
#endif

        !DecompCascadeBGCMod
#ifdef DECOMPCASCADEBGCMOD
          allocate(DecompBGCParamsInst%cn_s1_bgc    )
          allocate(DecompBGCParamsInst%cn_s2_bgc    )
          allocate(DecompBGCParamsInst%cn_s3_bgc    )
          allocate(DecompBGCParamsInst%np_s1_new_bgc)
          allocate(DecompBGCParamsInst%np_s2_new_bgc)
          allocate(DecompBGCParamsInst%np_s3_new_bgc)
          allocate(DecompBGCParamsInst%cp_s1_new_bgc)
          allocate(DecompBGCParamsInst%cp_s2_new_bgc)
          allocate(DecompBGCParamsInst%cp_s3_new_bgc)
          allocate(DecompBGCParamsInst%rf_l1s1_bgc  )
          allocate(DecompBGCParamsInst%rf_l2s1_bgc  )
          allocate(DecompBGCParamsInst%rf_l3s2_bgc  )
          allocate(DecompBGCParamsInst%rf_s2s1_bgc  )
          allocate(DecompBGCParamsInst%rf_s2s3_bgc  )
          allocate(DecompBGCParamsInst%rf_s3s1_bgc  )
          allocate(DecompBGCParamsInst%rf_cwdl2_bgc )
          allocate(DecompBGCParamsInst%rf_cwdl3_bgc )
          allocate(DecompBGCParamsInst%tau_l1_bgc   )
          allocate(DecompBGCParamsInst%tau_l2_l3_bgc)
          allocate(DecompBGCParamsInst%tau_s1_bgc   )
          allocate(DecompBGCParamsInst%tau_s2_bgc   )
          allocate(DecompBGCParamsInst%tau_s3_bgc   )
          allocate(DecompBGCParamsInst%tau_cwd_bgc  )
          allocate(DecompBGCParamsInst%cwd_fcel_bgc )
          allocate(DecompBGCParamsInst%cwd_flig_bgc )
          allocate(DecompBGCParamsInst%k_frag_bgc   )
          allocate(DecompBGCParamsInst%minpsi_bgc   )

          allocate(DecompBGCParamsInst%nsompools); DecompBGCParamsInst%nsompools = 3
          allocate(DecompBGCParamsInst%spinup_vector(DecompBGCParamsInst%nsompools))
          DecompBGCParamsInst%spinup_vector(:) = (/ 1.0_r8, 15.0_r8, 675.0_r8 /)
#endif

        !DecompCascadeCNMod
#ifdef DECOMPCASCADECNMOD
          allocate(DecompCNParamsInst%cn_s1_cn    ); DecompCNParamsInst%cn_s1_cn    =spval
          allocate(DecompCNParamsInst%cn_s2_cn    ); DecompCNParamsInst%cn_s2_cn    =spval
          allocate(DecompCNParamsInst%cn_s3_cn    ); DecompCNParamsInst%cn_s3_cn    =spval
          allocate(DecompCNParamsInst%cn_s4_cn    ); DecompCNParamsInst%cn_s4_cn    =spval
          allocate(DecompCNParamsInst%np_s1_new_cn); DecompCNParamsInst%np_s1_new_cn=spval
          allocate(DecompCNParamsInst%np_s2_new_cn); DecompCNParamsInst%np_s2_new_cn=spval
          allocate(DecompCNParamsInst%np_s3_new_cn); DecompCNParamsInst%np_s3_new_cn=spval
          allocate(DecompCNParamsInst%np_s4_new_cn); DecompCNParamsInst%np_s4_new_cn=spval
          allocate(DecompCNParamsInst%cp_s1_new_cn); DecompCNParamsInst%cp_s1_new_cn=spval
          allocate(DecompCNParamsInst%cp_s2_new_cn); DecompCNParamsInst%cp_s2_new_cn=spval
          allocate(DecompCNParamsInst%cp_s3_new_cn); DecompCNParamsInst%cp_s3_new_cn=spval
          allocate(DecompCNParamsInst%cp_s4_new_cn); DecompCNParamsInst%cp_s4_new_cn=spval
          allocate(DecompCNParamsInst%rf_l1s1_cn  ); DecompCNParamsInst%rf_l1s1_cn  =spval
          allocate(DecompCNParamsInst%rf_l2s2_cn  ); DecompCNParamsInst%rf_l2s2_cn  =spval
          allocate(DecompCNParamsInst%rf_l3s3_cn  ); DecompCNParamsInst%rf_l3s3_cn  =spval
          allocate(DecompCNParamsInst%rf_s1s2_cn  ); DecompCNParamsInst%rf_s1s2_cn  =spval
          allocate(DecompCNParamsInst%rf_s2s3_cn  ); DecompCNParamsInst%rf_s2s3_cn  =spval
          allocate(DecompCNParamsInst%rf_s3s4_cn  ); DecompCNParamsInst%rf_s3s4_cn  =spval
          allocate(DecompCNParamsInst%cwd_fcel_cn ); DecompCNParamsInst%cwd_fcel_cn =spval
          allocate(DecompCNParamsInst%cwd_flig_cn ); DecompCNParamsInst%cwd_flig_cn =spval
          allocate(DecompCNParamsInst%k_l1_cn     ); DecompCNParamsInst%k_l1_cn     =spval
          allocate(DecompCNParamsInst%k_l2_cn     ); DecompCNParamsInst%k_l2_cn     =spval
          allocate(DecompCNParamsInst%k_l3_cn     ); DecompCNParamsInst%k_l3_cn     =spval
          allocate(DecompCNParamsInst%k_s1_cn     ); DecompCNParamsInst%k_s1_cn     =spval
          allocate(DecompCNParamsInst%k_s2_cn     ); DecompCNParamsInst%k_s2_cn     =spval
          allocate(DecompCNParamsInst%k_s3_cn     ); DecompCNParamsInst%k_s3_cn     =spval
          allocate(DecompCNParamsInst%k_s4_cn     ); DecompCNParamsInst%k_s4_cn     =spval
          allocate(DecompCNParamsInst%k_frag_cn   ); DecompCNParamsInst%k_frag_cn   =spval
          allocate(DecompCNParamsInst%minpsi_cn   ); DecompCNParamsInst%minpsi_cn   =spval
          allocate(DecompCNParamsInst%nsompools   ); DecompCNParamsInst%nsompools = 4
          allocate(DecompCNParamsInst%nlitpools   ); DecompCNParamsInst%nlitpools = 3
          allocate(DecompCNParamsInst%ncwdpools   ); DecompCNParamsInst%ncwdpools = 1

          ! These are not read off of netcdf file
          allocate(DecompCNParamsInst%spinup_vector(DecompCNParamsInst%nsompools+DecompCNParamsInst%nlitpools+ &
              DecompCNParamsInst%ncwdpools))
#endif
        !SoilLittVertTransp
#ifdef SOILLITTVERTTRANSPMOD
          print *, "Allocating SoilLittVertTranspParamsInst"
          allocate(SoilLittVertTranspParamsInst%som_diffus                )
          allocate(SoilLittVertTranspParamsInst%cryoturb_diffusion_k      )
          allocate(SoilLittVertTranspParamsInst%max_altdepth_cryoturbation)
#endif

        !SurfaceAlbedoMod
#ifdef SURFACEALBEDOMOD
          allocate(albsat(8,numrad), albdry(8,numrad) )
          albsat(1:8,1) = (/0.12_r8,0.11_r8,0.10_r8,0.09_r8,0.08_r8,0.07_r8,0.06_r8,0.05_r8/)
          albsat(1:8,2) = (/0.24_r8,0.22_r8,0.20_r8,0.18_r8,0.16_r8,0.14_r8,0.12_r8,0.10_r8/)
          albdry(1:8,1) = (/0.24_r8,0.22_r8,0.20_r8,0.18_r8,0.16_r8,0.14_r8,0.12_r8,0.10_r8/)
          albdry(1:8,2) = (/0.48_r8,0.44_r8,0.40_r8,0.36_r8,0.32_r8,0.28_r8,0.24_r8,0.20_r8/)
          allocate(isoicol(bounds%begc:bounds%endc))
#endif

      end subroutine

end module initializeParameters
