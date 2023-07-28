module writeMod
contains
subroutine write_vars()
     use fileio_mod, only : fio_open, fio_close
     use elm_varsur, only : wt_lunit, urban_valid
     use elm_instMod, only : canopystate_vars 
     use GridcellType, only : grc_pp 
     use TopounitDataType, only : top_af 
     use LandunitType, only : lun_pp 
     use ColumnType, only : col_pp 
     use ColumnDataType, only : col_es 
     use ColumnDataType, only : col_ef 
     use ColumnDataType, only : col_ws 
     use VegetationType, only : veg_pp 
     use VegetationDataType, only : veg_wf 
     use VegetationDataType, only : veg_ef 
     use elm_instMod, only : solarabs_vars 
     use TopounitType, only : top_pp 
     implicit none 
      integer :: fid 
     character(len=64) :: ofile = "SoilFluxes_vars.txt" 
     fid = 23 
     
     !====================== grc_pp ======================!
     
     !$acc update self(& 
     !$acc grc_pp%gindex, &
     !$acc grc_pp%area, &
     !$acc grc_pp%lat, &
     !$acc grc_pp%lon, &
     !$acc grc_pp%latdeg, &
     !$acc grc_pp%londeg, &
     !$acc grc_pp%topi, &
     !$acc grc_pp%topf, &
     !$acc grc_pp%ntopounits, &
     !$acc grc_pp%lndi, &
     !$acc grc_pp%lndf, &
     !$acc grc_pp%nlandunits, &
     !$acc grc_pp%coli, &
     !$acc grc_pp%colf, &
     !$acc grc_pp%ncolumns, &
     !$acc grc_pp%pfti, &
     !$acc grc_pp%pftf, &
     !$acc grc_pp%npfts, &
     !$acc grc_pp%max_dayl, &
     !$acc grc_pp%dayl, &
     !$acc grc_pp%prev_dayl, &
     !$acc grc_pp%landunit_indices )
     
     !====================== lun_pp ======================!
     
     !$acc update self(& 
     !$acc lun_pp%gridcell, &
     !$acc lun_pp%wtgcell, &
     !$acc lun_pp%topounit, &
     !$acc lun_pp%wttopounit, &
     !$acc lun_pp%coli, &
     !$acc lun_pp%colf, &
     !$acc lun_pp%ncolumns, &
     !$acc lun_pp%pfti, &
     !$acc lun_pp%pftf, &
     !$acc lun_pp%npfts, &
     !$acc lun_pp%itype, &
     !$acc lun_pp%ifspecial, &
     !$acc lun_pp%lakpoi, &
     !$acc lun_pp%urbpoi, &
     !$acc lun_pp%glcmecpoi, &
     !$acc lun_pp%active, &
     !$acc lun_pp%canyon_hwr, &
     !$acc lun_pp%wtroad_perv, &
     !$acc lun_pp%wtlunit_roof, &
     !$acc lun_pp%ht_roof, &
     !$acc lun_pp%z_0_town, &
     !$acc lun_pp%z_d_town )
     
     !====================== col_pp ======================!
     
     !$acc update self(& 
     !$acc col_pp%gridcell, &
     !$acc col_pp%wtgcell, &
     !$acc col_pp%topounit, &
     !$acc col_pp%wttopounit, &
     !$acc col_pp%landunit, &
     !$acc col_pp%wtlunit, &
     !$acc col_pp%pfti, &
     !$acc col_pp%pftf, &
     !$acc col_pp%npfts, &
     !$acc col_pp%itype, &
     !$acc col_pp%active, &
     !$acc col_pp%glc_topo, &
     !$acc col_pp%micro_sigma, &
     !$acc col_pp%n_melt, &
     !$acc col_pp%topo_slope, &
     !$acc col_pp%topo_std, &
     !$acc col_pp%hslp_p10, &
     !$acc col_pp%nlevbed, &
     !$acc col_pp%zibed, &
     !$acc col_pp%snl, &
     !$acc col_pp%dz, &
     !$acc col_pp%z, &
     !$acc col_pp%zi, &
     !$acc col_pp%zii, &
     !$acc col_pp%dz_lake, &
     !$acc col_pp%z_lake, &
     !$acc col_pp%lakedepth, &
     !$acc col_pp%hydrologically_active )
     
     !====================== veg_pp ======================!
     
     !$acc update self(& 
     !$acc veg_pp%gridcell, &
     !$acc veg_pp%wtgcell, &
     !$acc veg_pp%topounit, &
     !$acc veg_pp%wttopounit, &
     !$acc veg_pp%landunit, &
     !$acc veg_pp%wtlunit, &
     !$acc veg_pp%column, &
     !$acc veg_pp%wtcol, &
     !$acc veg_pp%itype, &
     !$acc veg_pp%mxy, &
     !$acc veg_pp%active, &
     !$acc veg_pp%is_fates )
     
     !====================== top_pp ======================!
     
     !$acc update self(& 
     !$acc top_pp%gridcell, &
     !$acc top_pp%topo_grc_ind, &
     !$acc top_pp%wtgcell, &
     !$acc top_pp%lndi, &
     !$acc top_pp%lndf, &
     !$acc top_pp%nlandunits, &
     !$acc top_pp%coli, &
     !$acc top_pp%colf, &
     !$acc top_pp%ncolumns, &
     !$acc top_pp%pfti, &
     !$acc top_pp%pftf, &
     !$acc top_pp%npfts, &
     !$acc top_pp%landunit_indices, &
     !$acc top_pp%active, &
     !$acc top_pp%area, &
     !$acc top_pp%lat, &
     !$acc top_pp%lon, &
     !$acc top_pp%elevation, &
     !$acc top_pp%slope, &
     !$acc top_pp%aspect, &
     !$acc top_pp%emissivity, &
     !$acc top_pp%surfalb_dir, &
     !$acc top_pp%surfalb_dif )
     write(fid,'(A)') 'glc2lnd_vars%icemask_grc'
     write(fid,*) glc2lnd_vars%icemask_grc     
     !====================== canopystate_vars ======================!
     
     !$acc update self(& 
     !$acc canopystate_vars%frac_veg_nosno_patch )
     
     !====================== top_af ======================!
     
     !$acc update self(& 
     !$acc top_af%lwrad )
     
     !====================== col_es ======================!
     
     !$acc update self(& 
     !$acc col_es%t_soisno, &
     !$acc col_es%t_ssbef, &
     !$acc col_es%t_h2osfc, &
     !$acc col_es%t_h2osfc_bef, &
     !$acc col_es%t_grnd, &
     !$acc col_es%emg, &
     !$acc col_es%fact, &
     !$acc col_es%c_h2osfc )
     
     !====================== col_ef ======================!
     
     !$acc update self(& 
     !$acc col_ef%eflx_h2osfc_to_snow, &
     !$acc col_ef%eflx_building_heat, &
     !$acc col_ef%htvp, &
     !$acc col_ef%xmf, &
     !$acc col_ef%xmf_h2osfc, &
     !$acc col_ef%errsoi )
     
     !====================== col_ws ======================!
     
     !$acc update self(& 
     !$acc col_ws%h2osoi_liq, &
     !$acc col_ws%h2osoi_ice, &
     !$acc col_ws%do_capsnow, &
     !$acc col_ws%frac_sno_eff, &
     !$acc col_ws%frac_h2osfc )
     
     !====================== veg_wf ======================!
     
     !$acc update self(& 
     !$acc veg_wf%qflx_sub_snow, &
     !$acc veg_wf%qflx_evap_soi, &
     !$acc veg_wf%qflx_evap_veg, &
     !$acc veg_wf%qflx_evap_can, &
     !$acc veg_wf%qflx_evap_tot, &
     !$acc veg_wf%qflx_evap_grnd, &
     !$acc veg_wf%qflx_snwcp_liq, &
     !$acc veg_wf%qflx_snwcp_ice, &
     !$acc veg_wf%qflx_tran_veg, &
     !$acc veg_wf%qflx_dew_snow, &
     !$acc veg_wf%qflx_dew_grnd, &
     !$acc veg_wf%qflx_ev_snow, &
     !$acc veg_wf%qflx_ev_soil, &
     !$acc veg_wf%qflx_ev_h2osfc )
     
     !====================== veg_ef ======================!
     
     !$acc update self(& 
     !$acc veg_ef%eflx_sh_grnd, &
     !$acc veg_ef%eflx_sh_veg, &
     !$acc veg_ef%eflx_sh_tot, &
     !$acc veg_ef%eflx_sh_tot_u, &
     !$acc veg_ef%eflx_sh_tot_r, &
     !$acc veg_ef%eflx_lh_tot, &
     !$acc veg_ef%eflx_lh_tot_u, &
     !$acc veg_ef%eflx_lh_tot_r, &
     !$acc veg_ef%eflx_lh_vegt, &
     !$acc veg_ef%eflx_lh_vege, &
     !$acc veg_ef%eflx_lh_grnd, &
     !$acc veg_ef%eflx_soil_grnd, &
     !$acc veg_ef%eflx_soil_grnd_u, &
     !$acc veg_ef%eflx_soil_grnd_r, &
     !$acc veg_ef%eflx_lwrad_net, &
     !$acc veg_ef%eflx_lwrad_net_r, &
     !$acc veg_ef%eflx_lwrad_net_u, &
     !$acc veg_ef%eflx_lwrad_out, &
     !$acc veg_ef%eflx_lwrad_out_r, &
     !$acc veg_ef%eflx_lwrad_out_u, &
     !$acc veg_ef%eflx_traffic, &
     !$acc veg_ef%eflx_wasteheat, &
     !$acc veg_ef%eflx_heat_from_ac, &
     !$acc veg_ef%dlrad, &
     !$acc veg_ef%ulrad, &
     !$acc veg_ef%cgrndl, &
     !$acc veg_ef%cgrnds, &
     !$acc veg_ef%errsoi )
     
     !====================== solarabs_vars ======================!
     
     !$acc update self(& 
     !$acc solarabs_vars%sabg_soil_patch, &
     !$acc solarabs_vars%sabg_snow_patch, &
     !$acc solarabs_vars%sabg_patch )
     call fio_open(fid,ofile, 2) 

     write(fid,"(A)") "wt_lunit"
     write(fid,*) wt_lunit
     write(fid,"(A)") "urban_valid"
     write(fid,*) urban_valid

     
     !====================== grc_pp ======================!
     
     write (fid, "(A)") "grc_pp%gindex" 
     write (fid, *) grc_pp%gindex
     write (fid, "(A)") "grc_pp%area" 
     write (fid, *) grc_pp%area
     write (fid, "(A)") "grc_pp%lat" 
     write (fid, *) grc_pp%lat
     write (fid, "(A)") "grc_pp%lon" 
     write (fid, *) grc_pp%lon
     write (fid, "(A)") "grc_pp%latdeg" 
     write (fid, *) grc_pp%latdeg
     write (fid, "(A)") "grc_pp%londeg" 
     write (fid, *) grc_pp%londeg
     write (fid, "(A)") "grc_pp%topi" 
     write (fid, *) grc_pp%topi
     write (fid, "(A)") "grc_pp%topf" 
     write (fid, *) grc_pp%topf
     write (fid, "(A)") "grc_pp%ntopounits" 
     write (fid, *) grc_pp%ntopounits
     write (fid, "(A)") "grc_pp%lndi" 
     write (fid, *) grc_pp%lndi
     write (fid, "(A)") "grc_pp%lndf" 
     write (fid, *) grc_pp%lndf
     write (fid, "(A)") "grc_pp%nlandunits" 
     write (fid, *) grc_pp%nlandunits
     write (fid, "(A)") "grc_pp%coli" 
     write (fid, *) grc_pp%coli
     write (fid, "(A)") "grc_pp%colf" 
     write (fid, *) grc_pp%colf
     write (fid, "(A)") "grc_pp%ncolumns" 
     write (fid, *) grc_pp%ncolumns
     write (fid, "(A)") "grc_pp%pfti" 
     write (fid, *) grc_pp%pfti
     write (fid, "(A)") "grc_pp%pftf" 
     write (fid, *) grc_pp%pftf
     write (fid, "(A)") "grc_pp%npfts" 
     write (fid, *) grc_pp%npfts
     write (fid, "(A)") "grc_pp%max_dayl" 
     write (fid, *) grc_pp%max_dayl
     write (fid, "(A)") "grc_pp%dayl" 
     write (fid, *) grc_pp%dayl
     write (fid, "(A)") "grc_pp%prev_dayl" 
     write (fid, *) grc_pp%prev_dayl
     write (fid, "(A)") "grc_pp%landunit_indices" 
     write (fid, *) grc_pp%landunit_indices
     
     !====================== lun_pp ======================!
     
     write (fid, "(A)") "lun_pp%gridcell" 
     write (fid, *) lun_pp%gridcell
     write (fid, "(A)") "lun_pp%wtgcell" 
     write (fid, *) lun_pp%wtgcell
     write (fid, "(A)") "lun_pp%topounit" 
     write (fid, *) lun_pp%topounit
     write (fid, "(A)") "lun_pp%wttopounit" 
     write (fid, *) lun_pp%wttopounit
     write (fid, "(A)") "lun_pp%coli" 
     write (fid, *) lun_pp%coli
     write (fid, "(A)") "lun_pp%colf" 
     write (fid, *) lun_pp%colf
     write (fid, "(A)") "lun_pp%ncolumns" 
     write (fid, *) lun_pp%ncolumns
     write (fid, "(A)") "lun_pp%pfti" 
     write (fid, *) lun_pp%pfti
     write (fid, "(A)") "lun_pp%pftf" 
     write (fid, *) lun_pp%pftf
     write (fid, "(A)") "lun_pp%npfts" 
     write (fid, *) lun_pp%npfts
     write (fid, "(A)") "lun_pp%itype" 
     write (fid, *) lun_pp%itype
     write (fid, "(A)") "lun_pp%ifspecial" 
     write (fid, *) lun_pp%ifspecial
     write (fid, "(A)") "lun_pp%lakpoi" 
     write (fid, *) lun_pp%lakpoi
     write (fid, "(A)") "lun_pp%urbpoi" 
     write (fid, *) lun_pp%urbpoi
     write (fid, "(A)") "lun_pp%glcmecpoi" 
     write (fid, *) lun_pp%glcmecpoi
     write (fid, "(A)") "lun_pp%active" 
     write (fid, *) lun_pp%active
     write (fid, "(A)") "lun_pp%canyon_hwr" 
     write (fid, *) lun_pp%canyon_hwr
     write (fid, "(A)") "lun_pp%wtroad_perv" 
     write (fid, *) lun_pp%wtroad_perv
     write (fid, "(A)") "lun_pp%wtlunit_roof" 
     write (fid, *) lun_pp%wtlunit_roof
     write (fid, "(A)") "lun_pp%ht_roof" 
     write (fid, *) lun_pp%ht_roof
     write (fid, "(A)") "lun_pp%z_0_town" 
     write (fid, *) lun_pp%z_0_town
     write (fid, "(A)") "lun_pp%z_d_town" 
     write (fid, *) lun_pp%z_d_town
     
     !====================== col_pp ======================!
     
     write (fid, "(A)") "col_pp%gridcell" 
     write (fid, *) col_pp%gridcell
     write (fid, "(A)") "col_pp%wtgcell" 
     write (fid, *) col_pp%wtgcell
     write (fid, "(A)") "col_pp%topounit" 
     write (fid, *) col_pp%topounit
     write (fid, "(A)") "col_pp%wttopounit" 
     write (fid, *) col_pp%wttopounit
     write (fid, "(A)") "col_pp%landunit" 
     write (fid, *) col_pp%landunit
     write (fid, "(A)") "col_pp%wtlunit" 
     write (fid, *) col_pp%wtlunit
     write (fid, "(A)") "col_pp%pfti" 
     write (fid, *) col_pp%pfti
     write (fid, "(A)") "col_pp%pftf" 
     write (fid, *) col_pp%pftf
     write (fid, "(A)") "col_pp%npfts" 
     write (fid, *) col_pp%npfts
     write (fid, "(A)") "col_pp%itype" 
     write (fid, *) col_pp%itype
     write (fid, "(A)") "col_pp%active" 
     write (fid, *) col_pp%active
     write (fid, "(A)") "col_pp%glc_topo" 
     write (fid, *) col_pp%glc_topo
     write (fid, "(A)") "col_pp%micro_sigma" 
     write (fid, *) col_pp%micro_sigma
     write (fid, "(A)") "col_pp%n_melt" 
     write (fid, *) col_pp%n_melt
     write (fid, "(A)") "col_pp%topo_slope" 
     write (fid, *) col_pp%topo_slope
     write (fid, "(A)") "col_pp%topo_std" 
     write (fid, *) col_pp%topo_std
     write (fid, "(A)") "col_pp%hslp_p10" 
     write (fid, *) col_pp%hslp_p10
     write (fid, "(A)") "col_pp%nlevbed" 
     write (fid, *) col_pp%nlevbed
     write (fid, "(A)") "col_pp%zibed" 
     write (fid, *) col_pp%zibed
     write (fid, "(A)") "col_pp%snl" 
     write (fid, *) col_pp%snl
     write (fid, "(A)") "col_pp%dz" 
     write (fid, *) col_pp%dz
     write (fid, "(A)") "col_pp%z" 
     write (fid, *) col_pp%z
     write (fid, "(A)") "col_pp%zi" 
     write (fid, *) col_pp%zi
     write (fid, "(A)") "col_pp%zii" 
     write (fid, *) col_pp%zii
     write (fid, "(A)") "col_pp%dz_lake" 
     write (fid, *) col_pp%dz_lake
     write (fid, "(A)") "col_pp%z_lake" 
     write (fid, *) col_pp%z_lake
     write (fid, "(A)") "col_pp%lakedepth" 
     write (fid, *) col_pp%lakedepth
     write (fid, "(A)") "col_pp%hydrologically_active" 
     write (fid, *) col_pp%hydrologically_active
     
     !====================== veg_pp ======================!
     
     write (fid, "(A)") "veg_pp%gridcell" 
     write (fid, *) veg_pp%gridcell
     write (fid, "(A)") "veg_pp%wtgcell" 
     write (fid, *) veg_pp%wtgcell
     write (fid, "(A)") "veg_pp%topounit" 
     write (fid, *) veg_pp%topounit
     write (fid, "(A)") "veg_pp%wttopounit" 
     write (fid, *) veg_pp%wttopounit
     write (fid, "(A)") "veg_pp%landunit" 
     write (fid, *) veg_pp%landunit
     write (fid, "(A)") "veg_pp%wtlunit" 
     write (fid, *) veg_pp%wtlunit
     write (fid, "(A)") "veg_pp%column" 
     write (fid, *) veg_pp%column
     write (fid, "(A)") "veg_pp%wtcol" 
     write (fid, *) veg_pp%wtcol
     write (fid, "(A)") "veg_pp%itype" 
     write (fid, *) veg_pp%itype
     write (fid, "(A)") "veg_pp%mxy" 
     write (fid, *) veg_pp%mxy
     write (fid, "(A)") "veg_pp%active" 
     write (fid, *) veg_pp%active
     write (fid, "(A)") "veg_pp%is_fates" 
     write (fid, *) veg_pp%is_fates
     
     !====================== top_pp ======================!
     
     write (fid, "(A)") "top_pp%gridcell" 
     write (fid, *) top_pp%gridcell
     write (fid, "(A)") "top_pp%topo_grc_ind" 
     write (fid, *) top_pp%topo_grc_ind
     write (fid, "(A)") "top_pp%wtgcell" 
     write (fid, *) top_pp%wtgcell
     write (fid, "(A)") "top_pp%lndi" 
     write (fid, *) top_pp%lndi
     write (fid, "(A)") "top_pp%lndf" 
     write (fid, *) top_pp%lndf
     write (fid, "(A)") "top_pp%nlandunits" 
     write (fid, *) top_pp%nlandunits
     write (fid, "(A)") "top_pp%coli" 
     write (fid, *) top_pp%coli
     write (fid, "(A)") "top_pp%colf" 
     write (fid, *) top_pp%colf
     write (fid, "(A)") "top_pp%ncolumns" 
     write (fid, *) top_pp%ncolumns
     write (fid, "(A)") "top_pp%pfti" 
     write (fid, *) top_pp%pfti
     write (fid, "(A)") "top_pp%pftf" 
     write (fid, *) top_pp%pftf
     write (fid, "(A)") "top_pp%npfts" 
     write (fid, *) top_pp%npfts
     write (fid, "(A)") "top_pp%landunit_indices" 
     write (fid, *) top_pp%landunit_indices
     write (fid, "(A)") "top_pp%active" 
     write (fid, *) top_pp%active
     write (fid, "(A)") "top_pp%area" 
     write (fid, *) top_pp%area
     write (fid, "(A)") "top_pp%lat" 
     write (fid, *) top_pp%lat
     write (fid, "(A)") "top_pp%lon" 
     write (fid, *) top_pp%lon
     write (fid, "(A)") "top_pp%elevation" 
     write (fid, *) top_pp%elevation
     write (fid, "(A)") "top_pp%slope" 
     write (fid, *) top_pp%slope
     write (fid, "(A)") "top_pp%aspect" 
     write (fid, *) top_pp%aspect
     write (fid, "(A)") "top_pp%emissivity" 
     write (fid, *) top_pp%emissivity
     write (fid, "(A)") "top_pp%surfalb_dir" 
     write (fid, *) top_pp%surfalb_dir
     write (fid, "(A)") "top_pp%surfalb_dif" 
     write (fid, *) top_pp%surfalb_dif
     
     !====================== canopystate_vars ======================!
     
     write (fid, "(A)") "canopystate_vars%frac_veg_nosno_patch" 
     write (fid, *) canopystate_vars%frac_veg_nosno_patch
     
     !====================== top_af ======================!
     
     write (fid, "(A)") "top_af%lwrad" 
     write (fid, *) top_af%lwrad
     
     !====================== col_es ======================!
     
     write (fid, "(A)") "col_es%t_soisno" 
     write (fid, *) col_es%t_soisno
     write (fid, "(A)") "col_es%t_ssbef" 
     write (fid, *) col_es%t_ssbef
     write (fid, "(A)") "col_es%t_h2osfc" 
     write (fid, *) col_es%t_h2osfc
     write (fid, "(A)") "col_es%t_h2osfc_bef" 
     write (fid, *) col_es%t_h2osfc_bef
     write (fid, "(A)") "col_es%t_grnd" 
     write (fid, *) col_es%t_grnd
     write (fid, "(A)") "col_es%emg" 
     write (fid, *) col_es%emg
     write (fid, "(A)") "col_es%fact" 
     write (fid, *) col_es%fact
     write (fid, "(A)") "col_es%c_h2osfc" 
     write (fid, *) col_es%c_h2osfc
     
     !====================== col_ef ======================!
     
     write (fid, "(A)") "col_ef%eflx_h2osfc_to_snow" 
     write (fid, *) col_ef%eflx_h2osfc_to_snow
     write (fid, "(A)") "col_ef%eflx_building_heat" 
     write (fid, *) col_ef%eflx_building_heat
     write (fid, "(A)") "col_ef%htvp" 
     write (fid, *) col_ef%htvp
     write (fid, "(A)") "col_ef%xmf" 
     write (fid, *) col_ef%xmf
     write (fid, "(A)") "col_ef%xmf_h2osfc" 
     write (fid, *) col_ef%xmf_h2osfc
     write (fid, "(A)") "col_ef%errsoi" 
     write (fid, *) col_ef%errsoi
     
     !====================== col_ws ======================!
     
     write (fid, "(A)") "col_ws%h2osoi_liq" 
     write (fid, *) col_ws%h2osoi_liq
     write (fid, "(A)") "col_ws%h2osoi_ice" 
     write (fid, *) col_ws%h2osoi_ice
     write (fid, "(A)") "col_ws%do_capsnow" 
     write (fid, *) col_ws%do_capsnow
     write (fid, "(A)") "col_ws%frac_sno_eff" 
     write (fid, *) col_ws%frac_sno_eff
     write (fid, "(A)") "col_ws%frac_h2osfc" 
     write (fid, *) col_ws%frac_h2osfc
     
     !====================== veg_wf ======================!
     
     write (fid, "(A)") "veg_wf%qflx_sub_snow" 
     write (fid, *) veg_wf%qflx_sub_snow
     write (fid, "(A)") "veg_wf%qflx_evap_soi" 
     write (fid, *) veg_wf%qflx_evap_soi
     write (fid, "(A)") "veg_wf%qflx_evap_veg" 
     write (fid, *) veg_wf%qflx_evap_veg
     write (fid, "(A)") "veg_wf%qflx_evap_can" 
     write (fid, *) veg_wf%qflx_evap_can
     write (fid, "(A)") "veg_wf%qflx_evap_tot" 
     write (fid, *) veg_wf%qflx_evap_tot
     write (fid, "(A)") "veg_wf%qflx_evap_grnd" 
     write (fid, *) veg_wf%qflx_evap_grnd
     write (fid, "(A)") "veg_wf%qflx_snwcp_liq" 
     write (fid, *) veg_wf%qflx_snwcp_liq
     write (fid, "(A)") "veg_wf%qflx_snwcp_ice" 
     write (fid, *) veg_wf%qflx_snwcp_ice
     write (fid, "(A)") "veg_wf%qflx_tran_veg" 
     write (fid, *) veg_wf%qflx_tran_veg
     write (fid, "(A)") "veg_wf%qflx_dew_snow" 
     write (fid, *) veg_wf%qflx_dew_snow
     write (fid, "(A)") "veg_wf%qflx_dew_grnd" 
     write (fid, *) veg_wf%qflx_dew_grnd
     write (fid, "(A)") "veg_wf%qflx_ev_snow" 
     write (fid, *) veg_wf%qflx_ev_snow
     write (fid, "(A)") "veg_wf%qflx_ev_soil" 
     write (fid, *) veg_wf%qflx_ev_soil
     write (fid, "(A)") "veg_wf%qflx_ev_h2osfc" 
     write (fid, *) veg_wf%qflx_ev_h2osfc
     
     !====================== veg_ef ======================!
     
     write (fid, "(A)") "veg_ef%eflx_sh_grnd" 
     write (fid, *) veg_ef%eflx_sh_grnd
     write (fid, "(A)") "veg_ef%eflx_sh_veg" 
     write (fid, *) veg_ef%eflx_sh_veg
     write (fid, "(A)") "veg_ef%eflx_sh_tot" 
     write (fid, *) veg_ef%eflx_sh_tot
     write (fid, "(A)") "veg_ef%eflx_sh_tot_u" 
     write (fid, *) veg_ef%eflx_sh_tot_u
     write (fid, "(A)") "veg_ef%eflx_sh_tot_r" 
     write (fid, *) veg_ef%eflx_sh_tot_r
     write (fid, "(A)") "veg_ef%eflx_lh_tot" 
     write (fid, *) veg_ef%eflx_lh_tot
     write (fid, "(A)") "veg_ef%eflx_lh_tot_u" 
     write (fid, *) veg_ef%eflx_lh_tot_u
     write (fid, "(A)") "veg_ef%eflx_lh_tot_r" 
     write (fid, *) veg_ef%eflx_lh_tot_r
     write (fid, "(A)") "veg_ef%eflx_lh_vegt" 
     write (fid, *) veg_ef%eflx_lh_vegt
     write (fid, "(A)") "veg_ef%eflx_lh_vege" 
     write (fid, *) veg_ef%eflx_lh_vege
     write (fid, "(A)") "veg_ef%eflx_lh_grnd" 
     write (fid, *) veg_ef%eflx_lh_grnd
     write (fid, "(A)") "veg_ef%eflx_soil_grnd" 
     write (fid, *) veg_ef%eflx_soil_grnd
     write (fid, "(A)") "veg_ef%eflx_soil_grnd_u" 
     write (fid, *) veg_ef%eflx_soil_grnd_u
     write (fid, "(A)") "veg_ef%eflx_soil_grnd_r" 
     write (fid, *) veg_ef%eflx_soil_grnd_r
     write (fid, "(A)") "veg_ef%eflx_lwrad_net" 
     write (fid, *) veg_ef%eflx_lwrad_net
     write (fid, "(A)") "veg_ef%eflx_lwrad_net_r" 
     write (fid, *) veg_ef%eflx_lwrad_net_r
     write (fid, "(A)") "veg_ef%eflx_lwrad_net_u" 
     write (fid, *) veg_ef%eflx_lwrad_net_u
     write (fid, "(A)") "veg_ef%eflx_lwrad_out" 
     write (fid, *) veg_ef%eflx_lwrad_out
     write (fid, "(A)") "veg_ef%eflx_lwrad_out_r" 
     write (fid, *) veg_ef%eflx_lwrad_out_r
     write (fid, "(A)") "veg_ef%eflx_lwrad_out_u" 
     write (fid, *) veg_ef%eflx_lwrad_out_u
     write (fid, "(A)") "veg_ef%eflx_traffic" 
     write (fid, *) veg_ef%eflx_traffic
     write (fid, "(A)") "veg_ef%eflx_wasteheat" 
     write (fid, *) veg_ef%eflx_wasteheat
     write (fid, "(A)") "veg_ef%eflx_heat_from_ac" 
     write (fid, *) veg_ef%eflx_heat_from_ac
     write (fid, "(A)") "veg_ef%dlrad" 
     write (fid, *) veg_ef%dlrad
     write (fid, "(A)") "veg_ef%ulrad" 
     write (fid, *) veg_ef%ulrad
     write (fid, "(A)") "veg_ef%cgrndl" 
     write (fid, *) veg_ef%cgrndl
     write (fid, "(A)") "veg_ef%cgrnds" 
     write (fid, *) veg_ef%cgrnds
     write (fid, "(A)") "veg_ef%errsoi" 
     write (fid, *) veg_ef%errsoi
     
     !====================== solarabs_vars ======================!
     
     write (fid, "(A)") "solarabs_vars%sabg_soil_patch" 
     write (fid, *) solarabs_vars%sabg_soil_patch
     write (fid, "(A)") "solarabs_vars%sabg_snow_patch" 
     write (fid, *) solarabs_vars%sabg_snow_patch
     write (fid, "(A)") "solarabs_vars%sabg_patch" 
     write (fid, *) solarabs_vars%sabg_patch
     call fio_close(fid) 
end subroutine write_vars
end module writeMod
