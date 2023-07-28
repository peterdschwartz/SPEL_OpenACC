module writeMod
contains
subroutine write_vars()
     use fileio_mod, only : fio_open, fio_close
     use elm_varsur, only : wt_lunit, urban_valid
     use GridcellType, only : grc_pp 
     use LandunitType, only : lun_pp 
     use ColumnType, only : col_pp 
     use ColumnDataType, only : col_es 
     use ColumnDataType, only : col_ef 
     use ColumnDataType, only : col_ws 
     use ColumnDataType, only : col_wf 
     use VegetationType, only : veg_pp 
     use VegetationDataType, only : veg_ef 
     use elm_instMod, only : ch4_vars 
     use elm_instMod, only : soilstate_vars 
     use elm_instMod, only : solarabs_vars 
     use TopounitType, only : top_pp 
     use elm_instMod, only : lakestate_vars 
     implicit none 
      integer :: fid 
     character(len=64) :: ofile = "test_vars.txt" 
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
     
     !====================== col_es ======================!
     
     !$acc update self(& 
     !$acc col_es%t_soisno, &
     !$acc col_es%t_grnd, &
     !$acc col_es%t_lake, &
     !$acc col_es%hc_soi, &
     !$acc col_es%hc_soisno )
     
     !====================== col_ef ======================!
     
     !$acc update self(& 
     !$acc col_ef%eflx_snomelt, &
     !$acc col_ef%imelt, &
     !$acc col_ef%errsoi )
     
     !====================== col_ws ======================!
     
     !$acc update self(& 
     !$acc col_ws%h2osoi_liq, &
     !$acc col_ws%h2osoi_ice, &
     !$acc col_ws%h2osno, &
     !$acc col_ws%snow_depth, &
     !$acc col_ws%frac_iceold )
     
     !====================== col_wf ======================!
     
     !$acc update self(& 
     !$acc col_wf%qflx_snomelt, &
     !$acc col_wf%qflx_snow_melt, &
     !$acc col_wf%qflx_snofrz_lyr, &
     !$acc col_wf%qflx_snofrz )
     
     !====================== veg_ef ======================!
     
     !$acc update self(& 
     !$acc veg_ef%eflx_sh_grnd, &
     !$acc veg_ef%eflx_sh_tot, &
     !$acc veg_ef%eflx_soil_grnd, &
     !$acc veg_ef%eflx_gnet )
     
     !====================== ch4_vars ======================!
     
     !$acc update self(& 
     !$acc ch4_vars%grnd_ch4_cond_col )
     
     !====================== soilstate_vars ======================!
     
     !$acc update self(& 
     !$acc soilstate_vars%watsat_col, &
     !$acc soilstate_vars%tkmg_col, &
     !$acc soilstate_vars%tkdry_col, &
     !$acc soilstate_vars%tksatu_col, &
     !$acc soilstate_vars%csol_col )
     
     !====================== solarabs_vars ======================!
     
     !$acc update self(& 
     !$acc solarabs_vars%sabg_patch, &
     !$acc solarabs_vars%sabg_lyr_patch, &
     !$acc solarabs_vars%fsds_nir_d_patch, &
     !$acc solarabs_vars%fsds_nir_i_patch, &
     !$acc solarabs_vars%fsr_nir_d_patch, &
     !$acc solarabs_vars%fsr_nir_i_patch )
     
     !====================== lakestate_vars ======================!
     
     !$acc update self(& 
     !$acc lakestate_vars%etal_col, &
     !$acc lakestate_vars%lake_raw_col, &
     !$acc lakestate_vars%ks_col, &
     !$acc lakestate_vars%ws_col, &
     !$acc lakestate_vars%betaprime_col, &
     !$acc lakestate_vars%savedtke1_col, &
     !$acc lakestate_vars%lake_icefrac_col, &
     !$acc lakestate_vars%lake_icethick_col, &
     !$acc lakestate_vars%lakeresist_col )
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
     write (fid, "(A)") "veg_pp%is_veg" 
     write (fid, *) veg_pp%is_veg
     write (fid, "(A)") "veg_pp%is_bareground" 
     write (fid, *) veg_pp%is_bareground
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
     
     !====================== col_es ======================!
     
     write (fid, "(A)") "col_es%t_soisno" 
     write (fid, *) col_es%t_soisno
     write (fid, "(A)") "col_es%t_grnd" 
     write (fid, *) col_es%t_grnd
     write (fid, "(A)") "col_es%t_lake" 
     write (fid, *) col_es%t_lake
     write (fid, "(A)") "col_es%hc_soi" 
     write (fid, *) col_es%hc_soi
     write (fid, "(A)") "col_es%hc_soisno" 
     write (fid, *) col_es%hc_soisno
     
     !====================== col_ef ======================!
     
     write (fid, "(A)") "col_ef%eflx_snomelt" 
     write (fid, *) col_ef%eflx_snomelt
     write (fid, "(A)") "col_ef%imelt" 
     write (fid, *) col_ef%imelt
     write (fid, "(A)") "col_ef%errsoi" 
     write (fid, *) col_ef%errsoi
     
     !====================== col_ws ======================!
     
     write (fid, "(A)") "col_ws%h2osoi_liq" 
     write (fid, *) col_ws%h2osoi_liq
     write (fid, "(A)") "col_ws%h2osoi_ice" 
     write (fid, *) col_ws%h2osoi_ice
     write (fid, "(A)") "col_ws%h2osno" 
     write (fid, *) col_ws%h2osno
     write (fid, "(A)") "col_ws%snow_depth" 
     write (fid, *) col_ws%snow_depth
     write (fid, "(A)") "col_ws%frac_iceold" 
     write (fid, *) col_ws%frac_iceold
     
     !====================== col_wf ======================!
     
     write (fid, "(A)") "col_wf%qflx_snomelt" 
     write (fid, *) col_wf%qflx_snomelt
     write (fid, "(A)") "col_wf%qflx_snow_melt" 
     write (fid, *) col_wf%qflx_snow_melt
     write (fid, "(A)") "col_wf%qflx_snofrz_lyr" 
     write (fid, *) col_wf%qflx_snofrz_lyr
     write (fid, "(A)") "col_wf%qflx_snofrz" 
     write (fid, *) col_wf%qflx_snofrz
     
     !====================== veg_ef ======================!
     
     write (fid, "(A)") "veg_ef%eflx_sh_grnd" 
     write (fid, *) veg_ef%eflx_sh_grnd
     write (fid, "(A)") "veg_ef%eflx_sh_tot" 
     write (fid, *) veg_ef%eflx_sh_tot
     write (fid, "(A)") "veg_ef%eflx_soil_grnd" 
     write (fid, *) veg_ef%eflx_soil_grnd
     write (fid, "(A)") "veg_ef%eflx_gnet" 
     write (fid, *) veg_ef%eflx_gnet
     
     !====================== ch4_vars ======================!
     
     write (fid, "(A)") "ch4_vars%grnd_ch4_cond_col" 
     write (fid, *) ch4_vars%grnd_ch4_cond_col
     
     !====================== soilstate_vars ======================!
     
     write (fid, "(A)") "soilstate_vars%watsat_col" 
     write (fid, *) soilstate_vars%watsat_col
     write (fid, "(A)") "soilstate_vars%tkmg_col" 
     write (fid, *) soilstate_vars%tkmg_col
     write (fid, "(A)") "soilstate_vars%tkdry_col" 
     write (fid, *) soilstate_vars%tkdry_col
     write (fid, "(A)") "soilstate_vars%tksatu_col" 
     write (fid, *) soilstate_vars%tksatu_col
     write (fid, "(A)") "soilstate_vars%csol_col" 
     write (fid, *) soilstate_vars%csol_col
     
     !====================== solarabs_vars ======================!
     
     write (fid, "(A)") "solarabs_vars%sabg_patch" 
     write (fid, *) solarabs_vars%sabg_patch
     write (fid, "(A)") "solarabs_vars%sabg_lyr_patch" 
     write (fid, *) solarabs_vars%sabg_lyr_patch
     write (fid, "(A)") "solarabs_vars%fsds_nir_d_patch" 
     write (fid, *) solarabs_vars%fsds_nir_d_patch
     write (fid, "(A)") "solarabs_vars%fsds_nir_i_patch" 
     write (fid, *) solarabs_vars%fsds_nir_i_patch
     write (fid, "(A)") "solarabs_vars%fsr_nir_d_patch" 
     write (fid, *) solarabs_vars%fsr_nir_d_patch
     write (fid, "(A)") "solarabs_vars%fsr_nir_i_patch" 
     write (fid, *) solarabs_vars%fsr_nir_i_patch
     
     !====================== lakestate_vars ======================!
     
     write (fid, "(A)") "lakestate_vars%etal_col" 
     write (fid, *) lakestate_vars%etal_col
     write (fid, "(A)") "lakestate_vars%lake_raw_col" 
     write (fid, *) lakestate_vars%lake_raw_col
     write (fid, "(A)") "lakestate_vars%ks_col" 
     write (fid, *) lakestate_vars%ks_col
     write (fid, "(A)") "lakestate_vars%ws_col" 
     write (fid, *) lakestate_vars%ws_col
     write (fid, "(A)") "lakestate_vars%betaprime_col" 
     write (fid, *) lakestate_vars%betaprime_col
     write (fid, "(A)") "lakestate_vars%savedtke1_col" 
     write (fid, *) lakestate_vars%savedtke1_col
     write (fid, "(A)") "lakestate_vars%lake_icefrac_col" 
     write (fid, *) lakestate_vars%lake_icefrac_col
     write (fid, "(A)") "lakestate_vars%lake_icethick_col" 
     write (fid, *) lakestate_vars%lake_icethick_col
     write (fid, "(A)") "lakestate_vars%lakeresist_col" 
     write (fid, *) lakestate_vars%lakeresist_col
     call fio_close(fid) 
end subroutine write_vars
end module writeMod
