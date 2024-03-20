module duplicateMod
contains
subroutine duplicate_weights(unique_sites,total_gridcells)
   use elm_varsur, only : wt_lunit, urban_valid
   implicit none
   integer, intent(in) :: unique_sites
   integer, intent(in) :: total_gridcells
   integer :: g, dim2, l, gcopy
   dim2 = size(wt_lunit,2)
   print *, 'dim2 = ',dim2 
   do g = unique_sites+1, total_gridcells
      gcopy = mod(g-1,unique_sites)+1
      do l=1,dim2
         wt_lunit(g,l) = wt_lunit(gcopy,l)
      end do
      urban_valid(g) = urban_valid(gcopy)
   end do
end subroutine duplicate_weights
subroutine duplicate_clumps(mode,unique_sites,num_sites)
   use elm_instMod, only : canopystate_vars 
   use GridcellType, only : grc_pp 
   use TopounitDataType, only : top_af 
   use LandunitType, only : lun_pp 
   use ColumnType, only : col_pp 
   use ColumnDataType, only : col_es 
   use ColumnDataType, only : col_ef 
   use ColumnDataType, only : col_ws 
   use ColumnDataType, only : col_wf 
   use VegetationType, only : veg_pp 
   use VegetationDataType, only : veg_wf 
   use VegetationDataType, only : veg_ef 
   use elm_instMod, only : soilstate_vars 
   use elm_instMod, only : solarabs_vars 
   use UrbanParamsType, only : urbanparams_vars 
   use TopounitType, only : top_pp 
   use LandunitDataType, only : lun_es 
   use LandunitDataType, only : lun_ef 
   use decompMod, only : bounds_type, get_clump_bounds, procinfo 
   use elm_varcon 
   use elm_varpar 
   use elm_varctl 
   use landunit_varcon 
   implicit none 
   integer, intent(in) :: mode, unique_sites, num_sites 
   type(bounds_type)  :: bounds_copy, bounds
   integer :: errcode, nc,nc_copy, nclumps 
   integer :: begp_copy, endp_copy, begp, endp 
   integer :: begc_copy, endc_copy, begc, endc 
   integer :: begg_copy, endg_copy, begg, endg 
   integer :: begt_copy, endt_copy, begt, endt 
   integer :: begl_copy, endl_copy, begl, endl 
   nclumps = num_sites 
   if(mode == 0) then
      do nc=unique_sites+1, num_sites 
         nc_copy = mod(nc-1,unique_sites)+1
         call get_clump_bounds(nc,bounds)
         call get_clump_bounds(nc_copy,bounds_copy)
         begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg
         begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt
         begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl
         begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc
         begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp
         begg=bounds%begg; endg=bounds%endg
         begt=bounds%begt; endt=bounds%endt
         begl=bounds%begl; endl=bounds%endl
         begc=bounds%begc; endc=bounds%endc
         begp=bounds%begp; endp=bounds%endp
         grc_pp%gindex(begg:endg) &
            = grc_pp%gindex(begg_copy:endg_copy)
         grc_pp%area(begg:endg) &
            = grc_pp%area(begg_copy:endg_copy)
         grc_pp%lat(begg:endg) &
            = grc_pp%lat(begg_copy:endg_copy)
         grc_pp%lon(begg:endg) &
            = grc_pp%lon(begg_copy:endg_copy)
         grc_pp%latdeg(begg:endg) &
            = grc_pp%latdeg(begg_copy:endg_copy)
         grc_pp%londeg(begg:endg) &
            = grc_pp%londeg(begg_copy:endg_copy)
         grc_pp%topi(begg:endg) &
            = grc_pp%topi(begg_copy:endg_copy)
         grc_pp%topf(begg:endg) &
            = grc_pp%topf(begg_copy:endg_copy)
         grc_pp%ntopounits(begg:endg) &
            = grc_pp%ntopounits(begg_copy:endg_copy)
         grc_pp%lndi(begg:endg) &
            = grc_pp%lndi(begg_copy:endg_copy)
         grc_pp%lndf(begg:endg) &
            = grc_pp%lndf(begg_copy:endg_copy)
         grc_pp%nlandunits(begg:endg) &
            = grc_pp%nlandunits(begg_copy:endg_copy)
         grc_pp%coli(begg:endg) &
            = grc_pp%coli(begg_copy:endg_copy)
         grc_pp%colf(begg:endg) &
            = grc_pp%colf(begg_copy:endg_copy)
         grc_pp%ncolumns(begg:endg) &
            = grc_pp%ncolumns(begg_copy:endg_copy)
         grc_pp%pfti(begg:endg) &
            = grc_pp%pfti(begg_copy:endg_copy)
         grc_pp%pftf(begg:endg) &
            = grc_pp%pftf(begg_copy:endg_copy)
         grc_pp%npfts(begg:endg) &
            = grc_pp%npfts(begg_copy:endg_copy)
         grc_pp%max_dayl(begg:endg) &
            = grc_pp%max_dayl(begg_copy:endg_copy)
         grc_pp%dayl(begg:endg) &
            = grc_pp%dayl(begg_copy:endg_copy)
         grc_pp%prev_dayl(begg:endg) &
            = grc_pp%prev_dayl(begg_copy:endg_copy)
         grc_pp%elevation(begg:endg) &
            = grc_pp%elevation(begg_copy:endg_copy)
         grc_pp%froudenum(begg:endg) &
            = grc_pp%froudenum(begg_copy:endg_copy)
         grc_pp%landunit_indices(:,begg:endg) &
            = grc_pp%landunit_indices(:,begg_copy:endg_copy)
         lun_pp%gridcell(begl:endl) &
            = lun_pp%gridcell(begl_copy:endl_copy)
         lun_pp%wtgcell(begl:endl) &
            = lun_pp%wtgcell(begl_copy:endl_copy)
         lun_pp%topounit(begl:endl) &
            = lun_pp%topounit(begl_copy:endl_copy)
         lun_pp%wttopounit(begl:endl) &
            = lun_pp%wttopounit(begl_copy:endl_copy)
         lun_pp%coli(begl:endl) &
            = lun_pp%coli(begl_copy:endl_copy)
         lun_pp%colf(begl:endl) &
            = lun_pp%colf(begl_copy:endl_copy)
         lun_pp%ncolumns(begl:endl) &
            = lun_pp%ncolumns(begl_copy:endl_copy)
         lun_pp%pfti(begl:endl) &
            = lun_pp%pfti(begl_copy:endl_copy)
         lun_pp%pftf(begl:endl) &
            = lun_pp%pftf(begl_copy:endl_copy)
         lun_pp%npfts(begl:endl) &
            = lun_pp%npfts(begl_copy:endl_copy)
         lun_pp%itype(begl:endl) &
            = lun_pp%itype(begl_copy:endl_copy)
         lun_pp%ifspecial(begl:endl) &
            = lun_pp%ifspecial(begl_copy:endl_copy)
         lun_pp%lakpoi(begl:endl) &
            = lun_pp%lakpoi(begl_copy:endl_copy)
         lun_pp%urbpoi(begl:endl) &
            = lun_pp%urbpoi(begl_copy:endl_copy)
         lun_pp%glcmecpoi(begl:endl) &
            = lun_pp%glcmecpoi(begl_copy:endl_copy)
         lun_pp%active(begl:endl) &
            = lun_pp%active(begl_copy:endl_copy)
         lun_pp%canyon_hwr(begl:endl) &
            = lun_pp%canyon_hwr(begl_copy:endl_copy)
         lun_pp%wtroad_perv(begl:endl) &
            = lun_pp%wtroad_perv(begl_copy:endl_copy)
         lun_pp%wtlunit_roof(begl:endl) &
            = lun_pp%wtlunit_roof(begl_copy:endl_copy)
         lun_pp%ht_roof(begl:endl) &
            = lun_pp%ht_roof(begl_copy:endl_copy)
         lun_pp%z_0_town(begl:endl) &
            = lun_pp%z_0_town(begl_copy:endl_copy)
         lun_pp%z_d_town(begl:endl) &
            = lun_pp%z_d_town(begl_copy:endl_copy)
         col_pp%gridcell(begc:endc) &
            = col_pp%gridcell(begc_copy:endc_copy)
         col_pp%wtgcell(begc:endc) &
            = col_pp%wtgcell(begc_copy:endc_copy)
         col_pp%topounit(begc:endc) &
            = col_pp%topounit(begc_copy:endc_copy)
         col_pp%wttopounit(begc:endc) &
            = col_pp%wttopounit(begc_copy:endc_copy)
         col_pp%landunit(begc:endc) &
            = col_pp%landunit(begc_copy:endc_copy)
         col_pp%wtlunit(begc:endc) &
            = col_pp%wtlunit(begc_copy:endc_copy)
         col_pp%pfti(begc:endc) &
            = col_pp%pfti(begc_copy:endc_copy)
         col_pp%pftf(begc:endc) &
            = col_pp%pftf(begc_copy:endc_copy)
         col_pp%npfts(begc:endc) &
            = col_pp%npfts(begc_copy:endc_copy)
         col_pp%itype(begc:endc) &
            = col_pp%itype(begc_copy:endc_copy)
         col_pp%active(begc:endc) &
            = col_pp%active(begc_copy:endc_copy)
         col_pp%glc_topo(begc:endc) &
            = col_pp%glc_topo(begc_copy:endc_copy)
         col_pp%micro_sigma(begc:endc) &
            = col_pp%micro_sigma(begc_copy:endc_copy)
         col_pp%n_melt(begc:endc) &
            = col_pp%n_melt(begc_copy:endc_copy)
         col_pp%topo_slope(begc:endc) &
            = col_pp%topo_slope(begc_copy:endc_copy)
         col_pp%topo_std(begc:endc) &
            = col_pp%topo_std(begc_copy:endc_copy)
         col_pp%hslp_p10(begc:endc,:) &
            = col_pp%hslp_p10(begc_copy:endc_copy,:)
         col_pp%nlevbed(begc:endc) &
            = col_pp%nlevbed(begc_copy:endc_copy)
         col_pp%zibed(begc:endc) &
            = col_pp%zibed(begc_copy:endc_copy)
         col_pp%snl(begc:endc) &
            = col_pp%snl(begc_copy:endc_copy)
         col_pp%dz(begc:endc,:) &
            = col_pp%dz(begc_copy:endc_copy,:)
         col_pp%z(begc:endc,:) &
            = col_pp%z(begc_copy:endc_copy,:)
         col_pp%zi(begc:endc,:) &
            = col_pp%zi(begc_copy:endc_copy,:)
         col_pp%zii(begc:endc) &
            = col_pp%zii(begc_copy:endc_copy)
         col_pp%dz_lake(begc:endc,:) &
            = col_pp%dz_lake(begc_copy:endc_copy,:)
         col_pp%z_lake(begc:endc,:) &
            = col_pp%z_lake(begc_copy:endc_copy,:)
         col_pp%lakedepth(begc:endc) &
            = col_pp%lakedepth(begc_copy:endc_copy)
         col_pp%hydrologically_active(begc:endc) &
            = col_pp%hydrologically_active(begc_copy:endc_copy)
         col_pp%is_fates(begc:endc) &
            = col_pp%is_fates(begc_copy:endc_copy)
         veg_pp%gridcell(begp:endp) &
            = veg_pp%gridcell(begp_copy:endp_copy)
         veg_pp%wtgcell(begp:endp) &
            = veg_pp%wtgcell(begp_copy:endp_copy)
         veg_pp%topounit(begp:endp) &
            = veg_pp%topounit(begp_copy:endp_copy)
         veg_pp%wttopounit(begp:endp) &
            = veg_pp%wttopounit(begp_copy:endp_copy)
         veg_pp%landunit(begp:endp) &
            = veg_pp%landunit(begp_copy:endp_copy)
         veg_pp%wtlunit(begp:endp) &
            = veg_pp%wtlunit(begp_copy:endp_copy)
         veg_pp%column(begp:endp) &
            = veg_pp%column(begp_copy:endp_copy)
         veg_pp%wtcol(begp:endp) &
            = veg_pp%wtcol(begp_copy:endp_copy)
         veg_pp%itype(begp:endp) &
            = veg_pp%itype(begp_copy:endp_copy)
         veg_pp%mxy(begp:endp) &
            = veg_pp%mxy(begp_copy:endp_copy)
         veg_pp%active(begp:endp) &
            = veg_pp%active(begp_copy:endp_copy)
         veg_pp%sp_pftorder_index(begp:endp) &
            = veg_pp%sp_pftorder_index(begp_copy:endp_copy)
         veg_pp%is_fates(begp:endp) &
            = veg_pp%is_fates(begp_copy:endp_copy)
         top_pp%gridcell(begt:endt) &
            = top_pp%gridcell(begt_copy:endt_copy)
         top_pp%topo_grc_ind(begt:endt) &
            = top_pp%topo_grc_ind(begt_copy:endt_copy)
         top_pp%wtgcell(begt:endt) &
            = top_pp%wtgcell(begt_copy:endt_copy)
         top_pp%lndi(begt:endt) &
            = top_pp%lndi(begt_copy:endt_copy)
         top_pp%lndf(begt:endt) &
            = top_pp%lndf(begt_copy:endt_copy)
         top_pp%nlandunits(begt:endt) &
            = top_pp%nlandunits(begt_copy:endt_copy)
         top_pp%coli(begt:endt) &
            = top_pp%coli(begt_copy:endt_copy)
         top_pp%colf(begt:endt) &
            = top_pp%colf(begt_copy:endt_copy)
         top_pp%ncolumns(begt:endt) &
            = top_pp%ncolumns(begt_copy:endt_copy)
         top_pp%pfti(begt:endt) &
            = top_pp%pfti(begt_copy:endt_copy)
         top_pp%pftf(begt:endt) &
            = top_pp%pftf(begt_copy:endt_copy)
         top_pp%npfts(begt:endt) &
            = top_pp%npfts(begt_copy:endt_copy)
         top_pp%landunit_indices(:,begt:endt) &
            = top_pp%landunit_indices(:,begt_copy:endt_copy)
         top_pp%active(begt:endt) &
            = top_pp%active(begt_copy:endt_copy)
         top_pp%area(begt:endt) &
            = top_pp%area(begt_copy:endt_copy)
         top_pp%lat(begt:endt) &
            = top_pp%lat(begt_copy:endt_copy)
         top_pp%lon(begt:endt) &
            = top_pp%lon(begt_copy:endt_copy)
         top_pp%elevation(begt:endt) &
            = top_pp%elevation(begt_copy:endt_copy)
         top_pp%slope(begt:endt) &
            = top_pp%slope(begt_copy:endt_copy)
         top_pp%aspect(begt:endt) &
            = top_pp%aspect(begt_copy:endt_copy)
         top_pp%emissivity(begt:endt) &
            = top_pp%emissivity(begt_copy:endt_copy)
         top_pp%surfalb_dir(begt:endt,:) &
            = top_pp%surfalb_dir(begt_copy:endt_copy,:)
         top_pp%surfalb_dif(begt:endt,:) &
            = top_pp%surfalb_dif(begt_copy:endt_copy,:)
      end do
   else
      do nc=unique_sites+1, num_sites 
         nc_copy = mod(nc-1,unique_sites)+1
         call get_clump_bounds(nc,bounds)
         call get_clump_bounds(nc_copy,bounds_copy)
         begg_copy=bounds_copy%begg; endg_copy=bounds_copy%endg
         begt_copy=bounds_copy%begt; endt_copy=bounds_copy%endt
         begl_copy=bounds_copy%begl; endl_copy=bounds_copy%endl
         begc_copy=bounds_copy%begc; endc_copy=bounds_copy%endc
         begp_copy=bounds_copy%begp; endp_copy=bounds_copy%endp
         begg=bounds%begg; endg=bounds%endg
         begt=bounds%begt; endt=bounds%endt
         begl=bounds%begl; endl=bounds%endl
         begc=bounds%begc; endc=bounds%endc
         begp=bounds%begp; endp=bounds%endp
         canopystate_vars%frac_veg_nosno_patch(begp:endp) &
            = canopystate_vars%frac_veg_nosno_patch(begp_copy:endp_copy)
         top_af%lwrad(begt:endt) &
            = top_af%lwrad(begt_copy:endt_copy)
         col_es%t_soisno(begc:endc,:) &
            = col_es%t_soisno(begc_copy:endc_copy,:)
         col_es%t_ssbef(begc:endc,:) &
            = col_es%t_ssbef(begc_copy:endc_copy,:)
         col_es%t_h2osfc(begc:endc) &
            = col_es%t_h2osfc(begc_copy:endc_copy)
         col_es%t_grnd(begc:endc) &
            = col_es%t_grnd(begc_copy:endc_copy)
         col_es%emg(begc:endc) &
            = col_es%emg(begc_copy:endc_copy)
         col_es%fact(begc:endc,:) &
            = col_es%fact(begc_copy:endc_copy,:)
         col_es%c_h2osfc(begc:endc) &
            = col_es%c_h2osfc(begc_copy:endc_copy)
         col_ef%eflx_bot(begc:endc) &
            = col_ef%eflx_bot(begc_copy:endc_copy)
         col_ws%h2osoi_liq(begc:endc,:) &
            = col_ws%h2osoi_liq(begc_copy:endc_copy,:)
         col_ws%h2osoi_ice(begc:endc,:) &
            = col_ws%h2osoi_ice(begc_copy:endc_copy,:)
         col_ws%h2osfc(begc:endc) &
            = col_ws%h2osfc(begc_copy:endc_copy)
         col_ws%h2osno(begc:endc) &
            = col_ws%h2osno(begc_copy:endc_copy)
         col_ws%int_snow(begc:endc) &
            = col_ws%int_snow(begc_copy:endc_copy)
         col_ws%snow_depth(begc:endc) &
            = col_ws%snow_depth(begc_copy:endc_copy)
         col_ws%frac_sno_eff(begc:endc) &
            = col_ws%frac_sno_eff(begc_copy:endc_copy)
         col_ws%frac_h2osfc(begc:endc) &
            = col_ws%frac_h2osfc(begc_copy:endc_copy)
         col_wf%qflx_glcice(begc:endc) &
            = col_wf%qflx_glcice(begc_copy:endc_copy)
         veg_ef%dlrad(begp:endp) &
            = veg_ef%dlrad(begp_copy:endp_copy)
         veg_ef%cgrnd(begp:endp) &
            = veg_ef%cgrnd(begp_copy:endp_copy)
         soilstate_vars%bsw_col(begc:endc,:) &
            = soilstate_vars%bsw_col(begc_copy:endc_copy,:)
         soilstate_vars%watsat_col(begc:endc,:) &
            = soilstate_vars%watsat_col(begc_copy:endc_copy,:)
         soilstate_vars%sucsat_col(begc:endc,:) &
            = soilstate_vars%sucsat_col(begc_copy:endc_copy,:)
         soilstate_vars%tkmg_col(begc:endc,:) &
            = soilstate_vars%tkmg_col(begc_copy:endc_copy,:)
         soilstate_vars%tkdry_col(begc:endc,:) &
            = soilstate_vars%tkdry_col(begc_copy:endc_copy,:)
         soilstate_vars%csol_col(begc:endc,:) &
            = soilstate_vars%csol_col(begc_copy:endc_copy,:)
         solarabs_vars%sabg_soil_patch(begp:endp) &
            = solarabs_vars%sabg_soil_patch(begp_copy:endp_copy)
         solarabs_vars%sabg_snow_patch(begp:endp) &
            = solarabs_vars%sabg_snow_patch(begp_copy:endp_copy)
         solarabs_vars%sabg_patch(begp:endp) &
            = solarabs_vars%sabg_patch(begp_copy:endp_copy)
         solarabs_vars%sabg_lyr_patch(begp:endp,:) &
            = solarabs_vars%sabg_lyr_patch(begp_copy:endp_copy,:)
         urbanparams_vars%nlev_improad(begl:endl) &
            = urbanparams_vars%nlev_improad(begl_copy:endl_copy)
         urbanparams_vars%tk_wall(begl:endl,:) &
            = urbanparams_vars%tk_wall(begl_copy:endl_copy,:)
         urbanparams_vars%tk_roof(begl:endl,:) &
            = urbanparams_vars%tk_roof(begl_copy:endl_copy,:)
         urbanparams_vars%tk_improad(begl:endl,:) &
            = urbanparams_vars%tk_improad(begl_copy:endl_copy,:)
         urbanparams_vars%cv_wall(begl:endl,:) &
            = urbanparams_vars%cv_wall(begl_copy:endl_copy,:)
         urbanparams_vars%cv_roof(begl:endl,:) &
            = urbanparams_vars%cv_roof(begl_copy:endl_copy,:)
         urbanparams_vars%cv_improad(begl:endl,:) &
            = urbanparams_vars%cv_improad(begl_copy:endl_copy,:)
         urbanparams_vars%t_building_max(begl:endl) &
            = urbanparams_vars%t_building_max(begl_copy:endl_copy)
         urbanparams_vars%t_building_min(begl:endl) &
            = urbanparams_vars%t_building_min(begl_copy:endl_copy)
         lun_es%t_building(begl:endl) &
            = lun_es%t_building(begl_copy:endl_copy)
         lun_ef%eflx_traffic(begl:endl) &
            = lun_ef%eflx_traffic(begl_copy:endl_copy)
         lun_ef%eflx_wasteheat(begl:endl) &
            = lun_ef%eflx_wasteheat(begl_copy:endl_copy)
         lun_ef%eflx_heat_from_ac(begl:endl) &
            = lun_ef%eflx_heat_from_ac(begl_copy:endl_copy)
   end do
   end if 
end subroutine duplicate_clumps 
end module 
