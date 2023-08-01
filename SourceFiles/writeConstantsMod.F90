module writeConstantsMod

contains

  subroutine writeConstants()

    use fileio_mod, only : fio_open, fio_close
    use pftvarcon
    use soilorder_varcon
    use elm_varcon
    use elm_varpar
    use elm_varctl
    use AllocationMod
    use PhenologyMod
    use CH4varcon
    use CH4Mod
    use SharedParamsMod
    use SnowSnicarMod
    use PhotosynthesisMod
    use DUSTMod
    use DecompCascadeBGCMod
    use DecompCascadeCNMod
    use SoilLittVertTranspMod
    use GapMortalityMod
    use SurfaceAlbedoMod
    use SoilLittDecompMod
    use Tracer_varcon
    use timeInfoMod
    implicit none
    integer :: fid = 23
    character(len=256) :: ofile = "E3SM_constants.txt"

    call fio_open(fid, ofile, 2)

    !elm_varpar
    write(fid, "(A)") "nlevsoi  "
    write(fid,*) nlevsoi
    write(fid, "(A)") "nlevsoifl"
    write(fid,*) nlevsoifl
    write(fid, "(A)") "nlevgrnd "
    write(fid,*) nlevgrnd
    write(fid,"(A)") "nlevurb        "
    write(fid,*) nlevurb
    write(fid,"(A)") "nlevlak        "
    write(fid,*) nlevlak
    write(fid,"(A)") "nlevdecomp     "
    write(fid,*) nlevdecomp
    write(fid,"(A)") "nlevdecomp_full"
    write(fid,*) nlevdecomp_full
    write(fid,"(A)") "nlevtrc_soil"
    write(fid,*) nlevtrc_soil
    write(fid,"(A)") "nlevtrc_full"
    write(fid,*) nlevtrc_full
    write(fid,"(A)") "nlevsno"
    write(fid,*) nlevsno
    
    !timeInfoMod
    write(fid, "(A)")"dtime_mod"
    write(fid,*) dtime_mod       
    write(fid, "(A)")"dayspyr_mod"
    write(fid,*) dayspyr_mod
    write(fid, "(A)")"first"
    write(fid,*) first
    write(fid, "(A)")"year_curr"
    write(fid,*) year_curr
    write(fid, "(A)")"mon_curr"
    write(fid,*) mon_curr
    write(fid, "(A)")"day_curr"
    write(fid,*) day_curr
    write(fid, "(A)")"secs_curr"
    write(fid,*) secs_curr
    write(fid, "(A)")"nstep_mod"
    write(fid,*) nstep_mod
    write(fid, "(A)")"jday_mod"
    write(fid,*) jday_mod
    write(fid, "(A)")"thiscalday_mod"
    write(fid,*) thiscalday_mod
    write(fid, "(A)")"nextsw_cday_mod"
    write(fid,*) nextsw_cday_mod
    write(fid, "(A)")"end_cd_mod"
    write(fid,*) end_cd_mod
    write(fid, "(A)")"doalb"
    write(fid,*) doalb
    write(fid, "(A)")"year_prev"
    write(fid,*) year_prev
    write(fid, "(A)")"mon_prev"
    write(fid,*) mon_prev
    write(fid, "(A)")"day_prev"
    write(fid,*) day_prev
    write(fid, "(A)")"secs_prev"
    write(fid,*) secs_prev

    !from pftconrd
    write(fid, "(A)") "dleaf    "
    write(fid,*) dleaf
    write(fid, "(A)") "c3psn    "
    write(fid,*) c3psn
    write(fid, "(A)") "xl       "
    write(fid,*) xl
    write(fid, "(A)") "rhol     "
    write(fid,*) rhol
    write(fid, "(A)") "rhos     "
    write(fid,*) rhos
    write(fid, "(A)") "taul     "
    write(fid,*) taul
    write(fid, "(A)") "taus     "
    write(fid,*) taus
    write(fid, "(A)") "z0mr     "
    write(fid,*) z0mr
    write(fid, "(A)") "displar  "
    write(fid,*) displar
    write(fid, "(A)") "roota_par"
    write(fid,*) roota_par
    write(fid, "(A)") "rootb_par"
    write(fid,*) rootb_par
    write(fid, "(A)") "crop     "
    write(fid,*) crop
    write(fid, "(A)") "irrigated"
    write(fid,*) irrigated
    write(fid, "(A)") "smpso    "
    write(fid,*) smpso
    write(fid, "(A)") "smpsc    "
    write(fid,*) smpsc
    write(fid, "(A)") "fnitr    "
    write(fid,*) fnitr
    write(fid, "(A)") "slatop   "
    write(fid,*) slatop
    write(fid, "(A)") "dsladlai "
    write(fid,*) dsladlai
    write(fid, "(A)") "leafcn   "
    write(fid,*) leafcn
    write(fid, "(A)") "flnr     "
    write(fid,*) flnr
    write(fid, "(A)") "woody    "
    write(fid,*) woody
    write(fid, "(A)") "lflitcn  "
    write(fid,*) lflitcn
    write(fid, "(A)") "frootcn  "
    write(fid,*) frootcn
    write(fid, "(A)") "livewdcn "
    write(fid,*) livewdcn
    write(fid, "(A)") "deadwdcn "
    write(fid,*) deadwdcn

    write(fid,"(A)") "leafcp       "
    write(fid,*) leafcp
    write(fid,"(A)") "lflitcp      "
    write(fid,*) lflitcp
    write(fid,"(A)") "frootcp      "
    write(fid,*) frootcp
    write(fid,"(A)") "livewdcp     "
    write(fid,*) livewdcp
    write(fid,"(A)") "deadwdcp     "
    write(fid,*) deadwdcp
    write(fid,"(A)") "grperc       "
    write(fid,*) grperc
    write(fid,"(A)") "grpnow       "
    write(fid,*) grpnow
    write(fid,"(A)") "rootprof_beta"
    write(fid,*) rootprof_beta
    write(fid,"(A)") "graincn      "
    write(fid,*) graincn
    write(fid,"(A)") "graincp      "
    write(fid,*) graincp
    write(fid,"(A)") "mxtmp        "
    write(fid,*) mxtmp
    write(fid,"(A)") "baset        "
    write(fid,*) baset
    write(fid,"(A)") "declfact     "
    write(fid,*) declfact
    write(fid,"(A)") "bfact        "
    write(fid,*) bfact
    write(fid,"(A)") "aleaff       "
    write(fid,*) aleaff
    write(fid,"(A)") "arootf       "
    write(fid,*) arootf
    write(fid,"(A)") "astemf       "
    write(fid,*) astemf
    write(fid,"(A)") "arooti       "
    write(fid,*) arooti
    write(fid,"(A)") "fleafi       "
    write(fid,*) fleafi
    write(fid,"(A)") "allconsl     "
    write(fid,*) allconsl
    write(fid,"(A)") "allconss     "
    write(fid,*) allconss
    write(fid,"(A)") "ztopmx       "
    write(fid,*) ztopmx
    write(fid,"(A)") "laimx        "
    write(fid,*) laimx
    write(fid,"(A)") "gddmin       "
    write(fid,*) gddmin
    write(fid,"(A)") "hybgdd       "
    write(fid,*) hybgdd
    write(fid,"(A)") "lfemerg      "
    write(fid,*) lfemerg
    write(fid,"(A)") "grnfill      "
    write(fid,*) grnfill
    write(fid,"(A)") "mxmat        "
    write(fid,*) mxmat
    write(fid,"(A)") "mnNHplantdate"
    write(fid,*) mnNHplantdate
    write(fid,"(A)") "mxNHplantdate"
    write(fid,*) mxNHplantdate
    write(fid,"(A)") "mnSHplantdate"
    write(fid,*) mnSHplantdate
    write(fid,"(A)") "mxSHplantdate"
    write(fid,*) mxSHplantdate
    write(fid,"(A)") "planttemp    "
    write(fid,*) planttemp
    write(fid,"(A)") "minplanttemp "
    write(fid,*) minplanttemp
    write(fid,"(A)") "froot_leaf   "
    write(fid,*) froot_leaf
    write(fid,"(A)") "stem_leaf    "
    write(fid,*) stem_leaf
    write(fid,"(A)") "croot_stem   "
    write(fid,*) croot_stem
    write(fid,"(A)") "flivewd      "
    write(fid,*) flivewd
    write(fid,"(A)") "fcur         "
    write(fid,*) fcur
    write(fid,"(A)") "lf_flab      "
    write(fid,*) lf_flab
    write(fid,"(A)") "lf_fcel      "
    write(fid,*) lf_fcel
    write(fid,"(A)") "lf_flig      "
    write(fid,*) lf_flig
    write(fid,"(A)") "fr_flab      "
    write(fid,*) fr_flab
    write(fid,"(A)") "fr_fcel      "
    write(fid,*) fr_fcel
    write(fid,"(A)") "fr_flig      "
    write(fid,*) fr_flig
    write(fid,"(A)") "leaf_long    "
    write(fid,*) leaf_long
    write(fid,"(A)") "froot_long   "
    write(fid,*) froot_long
    write(fid,"(A)") "evergreen    "
    write(fid,*) evergreen
    write(fid,"(A)") "stress_decid "
    write(fid,*) stress_decid
    write(fid,"(A)") "season_decid "
    write(fid,*) season_decid
    write(fid,"(A)") "pconv        "
    write(fid,*) pconv
    write(fid,"(A)") "pprod10      "
    write(fid,*) pprod10
    write(fid,"(A)") "pprod100     "
    write(fid,*) pprod100
    write(fid,"(A)") "pprodharv10  "
    write(fid,*) pprodharv10
    write(fid,"(A)") "cc_leaf      "
    write(fid,*) cc_leaf
    write(fid,"(A)") "cc_lstem     "
    write(fid,*) cc_lstem
    write(fid,"(A)") "cc_dstem     "
    write(fid,*) cc_dstem
    write(fid,"(A)") "cc_other     "
    write(fid,*) cc_other
    write(fid,"(A)") "fm_leaf      "
    write(fid,*) fm_leaf
    write(fid,"(A)") "fm_lstem     "
    write(fid,*) fm_lstem
    write(fid,"(A)") "fm_dstem     "
    write(fid,*) fm_dstem
    write(fid,"(A)") "fm_other     "
    write(fid,*) fm_other
    write(fid,"(A)") "fm_root      "
    write(fid,*) fm_root
    write(fid,"(A)") "fm_lroot     "
    write(fid,*) fm_lroot
    write(fid,"(A)") "fm_droot     "
    write(fid,*) fm_droot
    write(fid,"(A)") "fsr_pft      "
    write(fid,*) fsr_pft
    write(fid,"(A)") "fd_pft       "
    write(fid,*) fd_pft
    write(fid,"(A)") "fertnitro    "
    write(fid,*) fertnitro
    write(fid,"(A)") "fleafcn      "
    write(fid,*) fleafcn
    write(fid,"(A)") "ffrootcn     "
    write(fid,*) ffrootcn
    write(fid,"(A)") "fstemcn      "
    write(fid,*) fstemcn
    write(fid,"(A)") "presharv     "
    write(fid,*) presharv
    write(fid,"(A)") "convfact     "
    write(fid,*) convfact
    write(fid,"(A)") "fyield       "
    write(fid,*) fyield
    write(fid,"(A)") "root_dmx     "
    write(fid,*) root_dmx

    write(fid,"(A)") "VMAX_PLANT_NH4"
    write(fid,*) VMAX_PLANT_NH4
    write(fid,"(A)") "VMAX_PLANT_NO3"
    write(fid,*) VMAX_PLANT_NO3
    write(fid,"(A)") "VMAX_PLANT_P  "
    write(fid,*) VMAX_PLANT_P
    write(fid,"(A)") "VMAX_MINSURF_P_vr"
    write(fid,*) VMAX_MINSURF_P_vr
    write(fid,"(A)") "KM_PLANT_NH4"
    write(fid,*) KM_PLANT_NH4
    write(fid,"(A)") "KM_PLANT_NO3"
    write(fid,*) KM_PLANT_NO3
    write(fid,"(A)") "KM_PLANT_P  "
    write(fid,*) KM_PLANT_P
    write(fid,"(A)") "KM_MINSURF_P_vr    "
    write(fid,*) KM_MINSURF_P_vr
    write(fid,"(A)") "decompmicc_patch_vr"
    write(fid,*) decompmicc_patch_vr
    write(fid,"(A)") "VMAX_PTASE "
    write(fid,*) VMAX_PTASE
    write(fid,"(A)") "i_vc       "
    write(fid,*) i_vc
    write(fid,"(A)") "s_vc       "
    write(fid,*) s_vc
    write(fid,"(A)") "alpha_nfix "
    write(fid,*) alpha_nfix
    write(fid,"(A)") "alpha_ptase"
    write(fid,*) alpha_ptase
    write(fid,"(A)") "ccost_nfix "
    write(fid,*) ccost_nfix
    write(fid,"(A)") "pcost_nfix "
    write(fid,*) pcost_nfix
    write(fid,"(A)") "ccost_ptase"
    write(fid,*) ccost_ptase
    write(fid,"(A)") "ncost_ptase"
    write(fid,*) ncost_ptase
    write(fid,"(A)") "VMAX_NFIX  "
    write(fid,*) VMAX_NFIX
    write(fid,"(A)") "KM_NFIX    "
    write(fid,*) KM_NFIX
    write(fid,"(A)") "leafcn_obs       "
    write(fid,*) leafcn_obs
    write(fid,"(A)") "frootcn_obs      "
    write(fid,*) frootcn_obs
    write(fid,"(A)") "livewdcn_obs     "
    write(fid,*) livewdcn_obs
    write(fid,"(A)") "deadwdcn_obs     "
    write(fid,*) deadwdcn_obs
    write(fid,"(A)") "leafcp_obs       "
    write(fid,*) leafcp_obs
    write(fid,"(A)") "frootcp_obs      "
    write(fid,*) frootcp_obs
    write(fid,"(A)") "livewdcp_obs     "
    write(fid,*) livewdcp_obs
    write(fid,"(A)") "deadwdcp_obs     "
    write(fid,*) deadwdcp_obs
    write(fid,"(A)") "leafcn_obs_flex  "
    write(fid,*) leafcn_obs_flex
    write(fid,"(A)") "frootcn_obs_flex "
    write(fid,*) frootcn_obs_flex
    write(fid,"(A)") "livewdcn_obs_flex"
    write(fid,*) livewdcn_obs_flex
    write(fid,"(A)") "deadwdcn_obs_flex"
    write(fid,*) deadwdcn_obs_flex
    write(fid,"(A)") "leafcp_obs_flex  "
    write(fid,*) leafcp_obs_flex
    write(fid,"(A)") "frootcp_obs_flex "
    write(fid,*) frootcp_obs_flex
    write(fid,"(A)") "livewdcp_obs_flex"
    write(fid,*) livewdcp_obs_flex
    write(fid,"(A)") "deadwdcp_obs_flex"
    write(fid,*) deadwdcp_obs_flex
    write(fid,"(A)") "vcmax_np1        "
    write(fid,*) vcmax_np1
    write(fid,"(A)") "vcmax_np2        "
    write(fid,*) vcmax_np2
    write(fid,"(A)") "vcmax_np3        "
    write(fid,*) vcmax_np3
    write(fid,"(A)") "vcmax_np4        "
    write(fid,*) vcmax_np4
    write(fid,"(A)") "fnr    "
    write(fid,*) fnr
    write(fid,"(A)") "act25  "
    write(fid,*) act25
    write(fid,"(A)") "kcha   "
    write(fid,*) kcha
    write(fid,"(A)") "koha   "
    write(fid,*) koha
    write(fid,"(A)") "cpha   "
    write(fid,*) cpha
    write(fid,"(A)") "vcmaxha"
    write(fid,*) vcmaxha
    write(fid,"(A)") "jmaxha "
    write(fid,*) jmaxha
    write(fid,"(A)") "tpuha  "
    write(fid,*) tpuha
    write(fid,"(A)") "lmrha  "
    write(fid,*) lmrha
    write(fid,"(A)") "vcmaxhd"
    write(fid,*) vcmaxhd
    write(fid,"(A)") "jmaxhd "
    write(fid,*) jmaxhd
    write(fid,"(A)") "tpuhd  "
    write(fid,*) tpuhd
    write(fid,"(A)") "lmrhd  "
    write(fid,*) lmrhd
    write(fid,"(A)") "lmrse  "
    write(fid,*) lmrse
    write(fid,"(A)") "qe     "
    write(fid,*) qe
    write(fid,"(A)") "theta_cj"
    write(fid,*) theta_cj
    write(fid,"(A)") "bbbopt "
    write(fid,*) bbbopt
    write(fid,"(A)") "mbbopt "
    write(fid,*) mbbopt
    write(fid,"(A)") "nstor  "
    write(fid,*) nstor
    write(fid,"(A)") "br_xr  "
    write(fid,*) br_xr

    write(fid,"(A)") "noveg                  "
    write(fid,*) noveg
    write(fid,"(A)") "ndllf_evr_tmp_tree     "
    write(fid,*) ndllf_evr_tmp_tree
    write(fid,"(A)") "ndllf_evr_brl_tree     "
    write(fid,*) ndllf_evr_brl_tree
    write(fid,"(A)") "ndllf_dcd_brl_tree     "
    write(fid,*) ndllf_dcd_brl_tree
    write(fid,"(A)") "nbrdlf_evr_trp_tree    "
    write(fid,*) nbrdlf_evr_trp_tree
    write(fid,"(A)") "nbrdlf_evr_tmp_tree    "
    write(fid,*) nbrdlf_evr_tmp_tree
    write(fid,"(A)") "nbrdlf_dcd_trp_tree    "
    write(fid,*) nbrdlf_dcd_trp_tree
    write(fid,"(A)") "nbrdlf_dcd_tmp_tree    "
    write(fid,*) nbrdlf_dcd_tmp_tree
    write(fid,"(A)") "nbrdlf_dcd_brl_tree    "
    write(fid,*) nbrdlf_dcd_brl_tree
    write(fid,"(A)") "ntree                  "
    write(fid,*) ntree
    write(fid,"(A)") "nbrdlf_evr_shrub       "
    write(fid,*) nbrdlf_evr_shrub
    write(fid,"(A)") "nbrdlf_dcd_tmp_shrub   "
    write(fid,*) nbrdlf_dcd_tmp_shrub
    write(fid,"(A)") "nbrdlf_dcd_brl_shrub   "
    write(fid,*) nbrdlf_dcd_brl_shrub
    write(fid,"(A)") "nc3_arctic_grass       "
    write(fid,*) nc3_arctic_grass
    write(fid,"(A)") "nc3_nonarctic_grass    "
    write(fid,*) nc3_nonarctic_grass
    write(fid,"(A)") "nc4_grass              "
    write(fid,*) nc4_grass
    write(fid,"(A)") "npcropmin              "
    write(fid,*) npcropmin
    write(fid,"(A)") "ncorn                  "
    write(fid,*) ncorn
    write(fid,"(A)") "ncornirrig             "
    write(fid,*) ncornirrig
    write(fid,"(A)") "nscereal               "
    write(fid,*) nscereal
    write(fid,"(A)") "nscerealirrig          "
    write(fid,*) nscerealirrig
    write(fid,"(A)") "nwcereal               "
    write(fid,*) nwcereal
    write(fid,"(A)") "nwcerealirrig          "
    write(fid,*) nwcerealirrig
    write(fid,"(A)") "nsoybean               "
    write(fid,*) nsoybean
    write(fid,"(A)") "nsoybeanirrig          "
    write(fid,*) nsoybeanirrig
    write(fid,"(A)") "npcropmax              "
    write(fid,*) npcropmax
    write(fid,"(A)") "nc3crop                "
    write(fid,*) nc3crop
    write(fid,"(A)") "nc3irrig               "
    write(fid,*) nc3irrig

    !-------- elm_varcon --------- !
    write(fid,"(A)") "zlak "
    write(fid,*) zlak
    write(fid,"(A)") "dzlak"
    write(fid,*) dzlak
    write(fid,"(A)") "zsoi "
    write(fid,*) zsoi
    write(fid,"(A)") "dzsoi"
    write(fid,*) dzsoi
    write(fid,"(A)") "zisoi"
    write(fid,*) zisoi
    write(fid,"(A)") "dzsoi_decomp"
    write(fid,*) dzsoi_decomp
    write(fid,"(A)") "nlvic  "
    write(fid,*) nlvic
    write(fid,"(A)") "dzvic  "
    write(fid,*) dzvic
    write(fid,"(A)") "zsoifl "
    write(fid,*) zsoifl
    write(fid,"(A)") "zisoifl"
    write(fid,*) zisoifl
    write(fid,"(A)") "dzsoifl"
    write(fid,*) dzsoifl

    !-------soilorder_varcon ------------------ !
    write(fid,"(A)") "smax            "
    write(fid,*) smax
    write(fid,"(A)") "ks_sorption     "
    write(fid,*) ks_sorption
    write(fid,"(A)") "r_weather       "
    write(fid,*) r_weather
    write(fid,"(A)") "r_adsorp        "
    write(fid,*) r_adsorp
    write(fid,"(A)") "r_desorp        "
    write(fid,*) r_desorp
    write(fid,"(A)") "r_occlude       "
    write(fid,*) r_occlude
    write(fid,"(A)") "k_s1_biochem    "
    write(fid,*) k_s1_biochem
    write(fid,"(A)") "k_s2_biochem    "
    write(fid,*) k_s2_biochem
    write(fid,"(A)") "k_s3_biochem    "
    write(fid,*) k_s3_biochem
    write(fid,"(A)") "k_s4_biochem    "
    write(fid,*) k_s4_biochem
    write(fid,"(A)") "r_mort_soilorder"
    write(fid,*) r_mort_soilorder

    !AllocParamsInst
    write(fid,"(A)") "AllocParamsInst%bdnr             "
    write(fid,*) AllocParamsInst%bdnr
    write(fid,"(A)") "AllocParamsInst%dayscrecover     "
    write(fid,*) AllocParamsInst%dayscrecover
    write(fid,"(A)") "AllocParamsInst%compet_plant_no3 "
    write(fid,*) AllocParamsInst%compet_plant_no3
    write(fid,"(A)") "AllocParamsInst%compet_plant_nh4 "
    write(fid,*) AllocParamsInst%compet_plant_nh4
    write(fid,"(A)") "AllocParamsInst%compet_decomp_no3"
    write(fid,*) AllocParamsInst%compet_decomp_no3
    write(fid,"(A)") "AllocParamsInst%compet_decomp_nh4"
    write(fid,*) AllocParamsInst%compet_decomp_nh4
    write(fid,"(A)") "AllocParamsInst%compet_denit     "
    write(fid,*) AllocParamsInst%compet_denit
    write(fid,"(A)") "AllocParamsInst%compet_nit       "
    write(fid,*) AllocParamsInst%compet_nit



    !PhenologyMod!
    write(fid,"(A)") "PhenolParamsInst%crit_dayl       "
    write(fid,*) PhenolParamsInst%crit_dayl
    write(fid,"(A)") "PhenolParamsInst%crit_dayl_stress"
    write(fid,*) PhenolParamsInst%crit_dayl_stress
    write(fid,"(A)") "PhenolParamsInst%cumprec_onset   "
    write(fid,*) PhenolParamsInst%cumprec_onset
    write(fid,"(A)") "PhenolParamsInst%ndays_on        "
    write(fid,*) PhenolParamsInst%ndays_on
    write(fid,"(A)") "PhenolParamsInst%ndays_off       "
    write(fid,*) PhenolParamsInst%ndays_off
    write(fid,"(A)") "PhenolParamsInst%fstor2tran      "
    write(fid,*) PhenolParamsInst%fstor2tran
    write(fid,"(A)") "PhenolParamsInst%crit_onset_fdd  "
    write(fid,*) PhenolParamsInst%crit_onset_fdd
    write(fid,"(A)") "PhenolParamsInst%crit_onset_swi  "
    write(fid,*) PhenolParamsInst%crit_onset_swi
    write(fid,"(A)") "PhenolParamsInst%soilpsi_on      "
    write(fid,*) PhenolParamsInst%soilpsi_on
    write(fid,"(A)") "PhenolParamsInst%crit_offset_fdd "
    write(fid,*) PhenolParamsInst%crit_offset_fdd
    write(fid,"(A)") "PhenolParamsInst%crit_offset_swi "
    write(fid,*) PhenolParamsInst%crit_offset_swi
    write(fid,"(A)") "PhenolParamsInst%soilpsi_off     "
    write(fid,*) PhenolParamsInst%soilpsi_off
    write(fid,"(A)") "PhenolParamsInst%lwtop           "
    write(fid,*) PhenolParamsInst%lwtop

    !CH4varcon
    write(fid,"(A)") "allowlakeprod    "
    write(fid,*) allowlakeprod
    write(fid,"(A)") "replenishlakec   "
    write(fid,*) replenishlakec
    write(fid,"(A)") "fin_use_fsat     "
    write(fid,*) fin_use_fsat
    write(fid,"(A)") "ch4offline       "
    write(fid,*) ch4offline
    write(fid,"(A)") "ch4rmcnlim       "
    write(fid,*) ch4rmcnlim
    write(fid,"(A)") "anoxicmicrosites "
    write(fid,*) anoxicmicrosites
    write(fid,"(A)") "ch4frzout        "
    write(fid,*) ch4frzout
    write(fid,"(A)") "usefrootc        "
    write(fid,*) usefrootc
    write(fid,"(A)") "transpirationloss"
    write(fid,*) transpirationloss
    write(fid,"(A)") "use_aereoxid_prog"
    write(fid,*) use_aereoxid_prog
    write(fid,"(A)") "usephfact        "
    write(fid,*) usephfact

    !!!!! SharedParamsMod !!!!!!
    write(fid,"(A)") "ParamsShareInst%Q10_mr               "
    write(fid,*) ParamsShareInst%Q10_mr
    write(fid,"(A)") "ParamsShareInst%Q10_hr               "
    write(fid,*) ParamsShareInst%Q10_hr
    write(fid,"(A)") "ParamsShareInst%minpsi               "
    write(fid,*) ParamsShareInst%minpsi
    write(fid,"(A)") "ParamsShareInst%cwd_fcel             "
    write(fid,*) ParamsShareInst%cwd_fcel
    write(fid,"(A)") "ParamsShareInst%cwd_flig             "
    write(fid,*) ParamsShareInst%cwd_flig
    write(fid,"(A)") "ParamsShareInst%froz_q10             "
    write(fid,*) ParamsShareInst%froz_q10
    write(fid,"(A)") "ParamsShareInst%decomp_depth_efolding"
    write(fid,*) ParamsShareInst%decomp_depth_efolding
    write(fid,"(A)") "ParamsShareInst%mino2lim             "
    write(fid,*) ParamsShareInst%mino2lim
    write(fid,"(A)") "ParamsShareInst%organic_max          "
    write(fid,*) ParamsShareInst%organic_max

    !! SnowSnicarMod !!
    write(fid,"(A)") "snowage_tau  "
    write(fid,*) snowage_tau
    write(fid,"(A)") "snowage_kappa"
    write(fid,*) snowage_kappa
    write(fid,"(A)") "snowage_drdt0"
    write(fid,*) snowage_drdt0

    write(fid,"(A)") "ss_alb_snw_drc     "
    write(fid,*) ss_alb_snw_drc
    write(fid,"(A)") "asm_prm_snw_drc    "
    write(fid,*) asm_prm_snw_drc
    write(fid,"(A)") "ext_cff_mss_snw_drc"
    write(fid,*) ext_cff_mss_snw_drc
    write(fid,"(A)") "ss_alb_snw_dfs     "
    write(fid,*) ss_alb_snw_dfs
    write(fid,"(A)") "asm_prm_snw_dfs    "
    write(fid,*) asm_prm_snw_dfs
    write(fid,"(A)") "ext_cff_mss_snw_dfs"
    write(fid,*) ext_cff_mss_snw_dfs

    write(fid,"(A)") "bcenh          "
    write(fid,*) bcenh
    write(fid,"(A)") "ss_alb_bc1     "
    write(fid,*) ss_alb_bc1
    write(fid,"(A)") "asm_prm_bc1    "
    write(fid,*) asm_prm_bc1
    write(fid,"(A)") "ext_cff_mss_bc1"
    write(fid,*) ext_cff_mss_bc1
    write(fid,"(A)") "ss_alb_bc2     "
    write(fid,*) ss_alb_bc2
    write(fid,"(A)") "asm_prm_bc2    "
    write(fid,*) asm_prm_bc2
    write(fid,"(A)") "ext_cff_mss_bc2"
    write(fid,*) ext_cff_mss_bc2

    write(fid,"(A)") "ss_alb_oc1      "
    write(fid,*) ss_alb_oc1
    write(fid,"(A)") "asm_prm_oc1     "
    write(fid,*) asm_prm_oc1
    write(fid,"(A)") "ext_cff_mss_oc1 "
    write(fid,*) ext_cff_mss_oc1
    write(fid,"(A)") "ss_alb_oc2      "
    write(fid,*) ss_alb_oc2
    write(fid,"(A)") "asm_prm_oc2     "
    write(fid,*) asm_prm_oc2
    write(fid,"(A)") "ext_cff_mss_oc2 "
    write(fid,*) ext_cff_mss_oc2
    write(fid,"(A)") "ss_alb_dst1     "
    write(fid,*) ss_alb_dst1
    write(fid,"(A)") "asm_prm_dst1    "
    write(fid,*) asm_prm_dst1
    write(fid,"(A)") "ext_cff_mss_dst1"
    write(fid,*) ext_cff_mss_dst1
    write(fid,"(A)") "ss_alb_dst2     "
    write(fid,*) ss_alb_dst2
    write(fid,"(A)") "asm_prm_dst2    "
    write(fid,*) asm_prm_dst2
    write(fid,"(A)") "ext_cff_mss_dst2"
    write(fid,*) ext_cff_mss_dst2
    write(fid,"(A)") "ss_alb_dst3     "
    write(fid,*) ss_alb_dst3
    write(fid,"(A)") "asm_prm_dst3    "
    write(fid,*) asm_prm_dst3
    write(fid,"(A)") "ext_cff_mss_dst3"
    write(fid,*) ext_cff_mss_dst3
    write(fid,"(A)") "ss_alb_dst4     "
    write(fid,*) ss_alb_dst4
    write(fid,"(A)") "asm_prm_dst4    "
    write(fid,*) asm_prm_dst4
    write(fid,"(A)") "ext_cff_mss_dst4"
    write(fid,*) ext_cff_mss_dst4

    !!PhotosynthesisMod:
    write(fid,"(A)") "params_inst%krmax       "
    write(fid,*) params_inst%krmax
    write(fid,"(A)") "params_inst%kmax        "
    write(fid,*) params_inst%kmax
    write(fid,"(A)") "params_inst%psi50       "
    write(fid,*) params_inst%psi50
    write(fid,"(A)") "params_inst%ck          "
    write(fid,*) params_inst%ck
    write(fid,"(A)") "params_inst%psi_soil_ref"
    write(fid,*) params_inst%psi_soil_ref

    !! CH4Mod !!
    write(fid,"(A)") "CH4ParamsInst%q10ch4              "
    write(fid,*) CH4ParamsInst%q10ch4
    write(fid,"(A)") "CH4ParamsInst%q10ch4base          "
    write(fid,*) CH4ParamsInst%q10ch4base
    write(fid,"(A)") "CH4ParamsInst%f_ch4               "
    write(fid,*) CH4ParamsInst%f_ch4
    write(fid,"(A)") "CH4ParamsInst%rootlitfrac         "
    write(fid,*) CH4ParamsInst%rootlitfrac
    write(fid,"(A)") "CH4ParamsInst%cnscalefactor       "
    write(fid,*) CH4ParamsInst%cnscalefactor
    write(fid,"(A)") "CH4ParamsInst%redoxlag            "
    write(fid,*) CH4ParamsInst%redoxlag
    write(fid,"(A)") "CH4ParamsInst%lake_decomp_fact    "
    write(fid,*) CH4ParamsInst%lake_decomp_fact
    write(fid,"(A)") "CH4ParamsInst%redoxlag_vertical   "
    write(fid,*) CH4ParamsInst%redoxlag_vertical
    write(fid,"(A)") "CH4ParamsInst%pHmax               "
    write(fid,*) CH4ParamsInst%pHmax
    write(fid,"(A)") "CH4ParamsInst%pHmin               "
    write(fid,*) CH4ParamsInst%pHmin
    write(fid,"(A)") "CH4ParamsInst%oxinhib             "
    write(fid,*) CH4ParamsInst%oxinhib
    write(fid,"(A)") "CH4ParamsInst%vmax_ch4_oxid       "
    write(fid,*) CH4ParamsInst%vmax_ch4_oxid
    write(fid,"(A)") "CH4ParamsInst%k_m                 "
    write(fid,*) CH4ParamsInst%k_m
    write(fid,"(A)") "CH4ParamsInst%q10_ch4oxid         "
    write(fid,*) CH4ParamsInst%q10_ch4oxid
    write(fid,"(A)") "CH4ParamsInst%smp_crit            "
    write(fid,*) CH4ParamsInst%smp_crit
    write(fid,"(A)") "CH4ParamsInst%k_m_o2              "
    write(fid,*) CH4ParamsInst%k_m_o2
    write(fid,"(A)") "CH4ParamsInst%k_m_unsat           "
    write(fid,*) CH4ParamsInst%k_m_unsat
    write(fid,"(A)") "CH4ParamsInst%vmax_oxid_unsat     "
    write(fid,*) CH4ParamsInst%vmax_oxid_unsat
    write(fid,"(A)") "CH4ParamsInst%aereoxid            "
    write(fid,*) CH4ParamsInst%aereoxid
    write(fid,"(A)") "CH4ParamsInst%scale_factor_aere   "
    write(fid,*) CH4ParamsInst%scale_factor_aere
    write(fid,"(A)") "CH4ParamsInst%nongrassporosratio  "
    write(fid,*) CH4ParamsInst%nongrassporosratio
    write(fid,"(A)") "CH4ParamsInst%unsat_aere_ratio    "
    write(fid,*) CH4ParamsInst%unsat_aere_ratio
    write(fid,"(A)") "CH4ParamsInst%porosmin            "
    write(fid,*) CH4ParamsInst%porosmin
    write(fid,"(A)") "CH4ParamsInst%vgc_max             "
    write(fid,*) CH4ParamsInst%vgc_max
    write(fid,"(A)") "CH4ParamsInst%satpow              "
    write(fid,*) CH4ParamsInst%satpow
    write(fid,"(A)") "CH4ParamsInst%scale_factor_gasdiff"
    write(fid,*) CH4ParamsInst%scale_factor_gasdiff
    write(fid,"(A)") "CH4ParamsInst%scale_factor_liqdiff"
    write(fid,*) CH4ParamsInst%scale_factor_liqdiff
    write(fid,"(A)") "CH4ParamsInst%capthick            "
    write(fid,*) CH4ParamsInst%capthick
    write(fid,"(A)") "CH4ParamsInst%f_sat               "
    write(fid,*) CH4ParamsInst%f_sat
    write(fid,"(A)") "CH4ParamsInst%qflxlagd            "
    write(fid,*) CH4ParamsInst%qflxlagd
    write(fid,"(A)") "CH4ParamsInst%highlatfact         "
    write(fid,*) CH4ParamsInst%highlatfact
    write(fid,"(A)") "CH4ParamsInst%q10lakebase         "
    write(fid,*) CH4ParamsInst%q10lakebase
    write(fid,"(A)") "CH4ParamsInst%atmch4              "
    write(fid,*) CH4ParamsInst%atmch4
    write(fid,"(A)") "CH4ParamsInst%rob                 "
    write(fid,*) CH4ParamsInst%rob

    !! DecompCascadeBGCMod
    if((.not. is_active_betr_bgc) .and. use_century_decomp) then
      write(fid, "(A)") "DecompBGCParamsInst%cn_s1_bgc    "
      write(fid,*) DecompBGCParamsInst%cn_s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cn_s2_bgc    "
      write(fid,*) DecompBGCParamsInst%cn_s2_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cn_s3_bgc    "
      write(fid,*) DecompBGCParamsInst%cn_s3_bgc
      write(fid, "(A)") "DecompBGCParamsInst%np_s1_new_bgc"
      write(fid,*) DecompBGCParamsInst%np_s1_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%np_s2_new_bgc"
      write(fid,*) DecompBGCParamsInst%np_s2_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%np_s3_new_bgc"
      write(fid,*) DecompBGCParamsInst%np_s3_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cp_s1_new_bgc"
      write(fid,*) DecompBGCParamsInst%cp_s1_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cp_s2_new_bgc"
      write(fid,*) DecompBGCParamsInst%cp_s2_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cp_s3_new_bgc"
      write(fid,*) DecompBGCParamsInst%cp_s3_new_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_l1s1_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_l1s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_l2s1_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_l2s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_l3s2_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_l3s2_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_s2s1_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_s2s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_s2s3_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_s2s3_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_s3s1_bgc  "
      write(fid,*) DecompBGCParamsInst%rf_s3s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_cwdl2_bgc "
      write(fid,*) DecompBGCParamsInst%rf_cwdl2_bgc
      write(fid, "(A)") "DecompBGCParamsInst%rf_cwdl3_bgc "
      write(fid,*) DecompBGCParamsInst%rf_cwdl3_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_l1_bgc   "
      write(fid,*) DecompBGCParamsInst%tau_l1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_l2_l3_bgc"
      write(fid,*) DecompBGCParamsInst%tau_l2_l3_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_s1_bgc   "
      write(fid,*) DecompBGCParamsInst%tau_s1_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_s2_bgc   "
      write(fid,*) DecompBGCParamsInst%tau_s2_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_s3_bgc   "
      write(fid,*) DecompBGCParamsInst%tau_s3_bgc
      write(fid, "(A)") "DecompBGCParamsInst%tau_cwd_bgc  "
      write(fid,*) DecompBGCParamsInst%tau_cwd_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cwd_fcel_bgc "
      write(fid,*) DecompBGCParamsInst%cwd_fcel_bgc
      write(fid, "(A)") "DecompBGCParamsInst%cwd_flig_bgc "
      write(fid,*) DecompBGCParamsInst%cwd_flig_bgc
      write(fid, "(A)") "DecompBGCParamsInst%k_frag_bgc   "
      write(fid,*) DecompBGCParamsInst%k_frag_bgc
      write(fid, "(A)") "DecompBGCParamsInst%minpsi_bgc   "
      write(fid,*) DecompBGCParamsInst%minpsi_bgc
    else
      !!! DecompCNParamsInst
      print *, "DecompCNParamsInst"
      write(fid,"(A)") "DecompCNParamsInst%cn_s1_cn    "
      write(fid, *)  DecompCNParamsInst%cn_s1_cn
      write(fid,"(A)") "DecompCNParamsInst%cn_s2_cn    "
      write(fid, *)  DecompCNParamsInst%cn_s2_cn
      write(fid,"(A)") "DecompCNParamsInst%cn_s3_cn    "
      write(fid, *)  DecompCNParamsInst%cn_s3_cn
      write(fid,"(A)") "DecompCNParamsInst%cn_s4_cn    "
      write(fid, *)  DecompCNParamsInst%cn_s4_cn
      write(fid,"(A)") "DecompCNParamsInst%np_s1_new_cn"
      write(fid, *)  DecompCNParamsInst%np_s1_new_cn
      write(fid,"(A)") "DecompCNParamsInst%np_s2_new_cn"
      write(fid, *)  DecompCNParamsInst%np_s2_new_cn
      write(fid,"(A)") "DecompCNParamsInst%np_s3_new_cn"
      write(fid, *)  DecompCNParamsInst%np_s3_new_cn
      write(fid,"(A)") "DecompCNParamsInst%np_s4_new_cn"
      write(fid, *)  DecompCNParamsInst%np_s4_new_cn
      write(fid,"(A)") "DecompCNParamsInst%cp_s1_new_cn"
      write(fid, *)  DecompCNParamsInst%cp_s1_new_cn
      write(fid,"(A)") "DecompCNParamsInst%cp_s2_new_cn"
      write(fid, *)  DecompCNParamsInst%cp_s2_new_cn
      write(fid,"(A)") "DecompCNParamsInst%cp_s3_new_cn"
      write(fid, *)  DecompCNParamsInst%cp_s3_new_cn
      write(fid,"(A)") "DecompCNParamsInst%cp_s4_new_cn"
      write(fid, *)  DecompCNParamsInst%cp_s4_new_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_l1s1_cn  "
      write(fid, *)  DecompCNParamsInst%rf_l1s1_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_l2s2_cn  "
      write(fid, *)  DecompCNParamsInst%rf_l2s2_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_l3s3_cn  "
      write(fid, *)  DecompCNParamsInst%rf_l3s3_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_s1s2_cn  "
      write(fid, *)  DecompCNParamsInst%rf_s1s2_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_s2s3_cn  "
      write(fid, *)  DecompCNParamsInst%rf_s2s3_cn
      write(fid,"(A)") "DecompCNParamsInst%rf_s3s4_cn  "
      write(fid, *)  DecompCNParamsInst%rf_s3s4_cn
      write(fid,"(A)") "DecompCNParamsInst%cwd_fcel_cn "
      write(fid, *)  DecompCNParamsInst%cwd_fcel_cn
      write(fid,"(A)") "DecompCNParamsInst%cwd_flig_cn "
      write(fid, *)  DecompCNParamsInst%cwd_flig_cn
      write(fid,"(A)") "DecompCNParamsInst%k_l1_cn     "
      write(fid, *)  DecompCNParamsInst%k_l1_cn
      write(fid,"(A)") "DecompCNParamsInst%k_l2_cn     "
      write(fid, *)  DecompCNParamsInst%k_l2_cn
      write(fid,"(A)") "DecompCNParamsInst%k_l3_cn     "
      write(fid, *)  DecompCNParamsInst%k_l3_cn
      write(fid,"(A)") "DecompCNParamsInst%k_s1_cn     "
      write(fid, *)  DecompCNParamsInst%k_s1_cn
      write(fid,"(A)") "DecompCNParamsInst%k_s2_cn     "
      write(fid, *)  DecompCNParamsInst%k_s2_cn
      write(fid,"(A)") "DecompCNParamsInst%k_s3_cn     "
      write(fid, *)  DecompCNParamsInst%k_s3_cn
      write(fid,"(A)") "DecompCNParamsInst%k_s4_cn     "
      write(fid, *)  DecompCNParamsInst%k_s4_cn
      write(fid,"(A)") "DecompCNParamsInst%k_frag_cn   "
      write(fid, *)  DecompCNParamsInst%k_frag_cn
      write(fid,"(A)") "DecompCNParamsInst%minpsi_cn   "
      write(fid, *)  DecompCNParamsInst%minpsi_cn
    end if

    !! SoilLittVertTranspMod
    write(fid, "(A)") "SoilLittVertTranspParamsInst%som_diffus                "
    write(fid, *) SoilLittVertTranspParamsInst%som_diffus
    write(fid, "(A)") "SoilLittVertTranspParamsInst%cryoturb_diffusion_k      "
    write(fid, *) SoilLittVertTranspParamsInst%cryoturb_diffusion_k
    write(fid, "(A)") "SoilLittVertTranspParamsInst%max_altdepth_cryoturbation"
    write(fid, *) SoilLittVertTranspParamsInst%max_altdepth_cryoturbation

    write(fid,"(A)") "CNGapMortParamsInst%am    "
    write(fid,  *) CNGapMortParamsInst%am
    write(fid,"(A)") "CNGapMortParamsInst%k_mort"
    write(fid,  *) CNGapMortParamsInst%k_mort

    !SoilLittDecompMod
    write(fid,"(A)") "CNDecompParamsInst%dnp"
    write(fid,*)  CNDecompParamsInst%dnp

    !SurfaceAlbedoMod
    write(fid,"(A)") "albsat "
    write(fid, *) albsat
    write(fid,"(A)") "albdry "
    write(fid, *) albdry
    write(fid,"(A)") "isoicol"
    write(fid, *) isoicol

    call fio_close(fid)

  end subroutine writeConstants

end module writeConstantsMod
