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
   use TopounitDataType, only : top_as 
   use LandunitType, only : lun_pp 
   use ColumnType, only : col_pp 
   use ColumnDataType, only : col_es 
   use ColumnDataType, only : col_ws 
   use ColumnDataType, only : col_wf 
   use ColumnDataType, only : col_nf 
   use ColumnDataType, only : col_cf 
   use VegetationType, only : veg_pp 
   use VegetationDataType, only : veg_wf 
   use VegetationDataType, only : veg_cs 
   use VegetationDataType, only : veg_cf 
   use elm_instMod, only : ch4_vars 
   use elm_instMod, only : soilstate_vars 
   use elm_instMod, only : energyflux_vars 
   use TopounitType, only : top_pp 
   use SharedParamsMod, only : ParamsShareInst 
   use elm_instMod, only : lakestate_vars 
   use elm_instMod, only : soilhydrology_vars 
   use elm_instMod, only : lnd2atm_vars 
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
         canopystate_vars%elai_patch(begp:endp) &
            = canopystate_vars%elai_patch(begp_copy:endp_copy)
         top_as%tbot(begt:endt) &
            = top_as%tbot(begt_copy:endt_copy)
         top_as%pbot(begt:endt) &
            = top_as%pbot(begt_copy:endt_copy)
         top_as%po2bot(begt:endt) &
            = top_as%po2bot(begt_copy:endt_copy)
         top_as%pco2bot(begt:endt) &
            = top_as%pco2bot(begt_copy:endt_copy)
         top_as%pch4bot(begt:endt) &
            = top_as%pch4bot(begt_copy:endt_copy)
         col_es%t_soisno(begc:endc,:) &
            = col_es%t_soisno(begc_copy:endc_copy,:)
         col_es%t_h2osfc(begc:endc) &
            = col_es%t_h2osfc(begc_copy:endc_copy)
         col_es%t_grnd(begc:endc) &
            = col_es%t_grnd(begc_copy:endc_copy)
         col_ws%h2osoi_liq(begc:endc,:) &
            = col_ws%h2osoi_liq(begc_copy:endc_copy,:)
         col_ws%h2osoi_ice(begc:endc,:) &
            = col_ws%h2osoi_ice(begc_copy:endc_copy,:)
         col_ws%h2osoi_vol(begc:endc,:) &
            = col_ws%h2osoi_vol(begc_copy:endc_copy,:)
         col_ws%h2osfc(begc:endc) &
            = col_ws%h2osfc(begc_copy:endc_copy)
         col_ws%frac_h2osfc(begc:endc) &
            = col_ws%frac_h2osfc(begc_copy:endc_copy)
         col_wf%qflx_surf(begc:endc) &
            = col_wf%qflx_surf(begc_copy:endc_copy)
         col_nf%pot_f_nit_vr(begc:endc,:) &
            = col_nf%pot_f_nit_vr(begc_copy:endc_copy,:)
         col_cf%hr_vr(begc:endc,:) &
            = col_cf%hr_vr(begc_copy:endc_copy,:)
         col_cf%o_scalar(begc:endc,:) &
            = col_cf%o_scalar(begc_copy:endc_copy,:)
         col_cf%fphr(begc:endc,:) &
            = col_cf%fphr(begc_copy:endc_copy,:)
         col_cf%lithr(begc:endc) &
            = col_cf%lithr(begc_copy:endc_copy)
         col_cf%somhr(begc:endc) &
            = col_cf%somhr(begc_copy:endc_copy)
         veg_wf%qflx_tran_veg(begp:endp) &
            = veg_wf%qflx_tran_veg(begp_copy:endp_copy)
         veg_cs%frootc(begp:endp) &
            = veg_cs%frootc(begp_copy:endp_copy)
         veg_cf%rr(begp:endp) &
            = veg_cf%rr(begp_copy:endp_copy)
         veg_cf%agnpp(begp:endp) &
            = veg_cf%agnpp(begp_copy:endp_copy)
         veg_cf%bgnpp(begp:endp) &
            = veg_cf%bgnpp(begp_copy:endp_copy)
         veg_cf%annsum_npp(begp:endp) &
            = veg_cf%annsum_npp(begp_copy:endp_copy)
         veg_cf%annavg_agnpp(begp:endp) &
            = veg_cf%annavg_agnpp(begp_copy:endp_copy)
         veg_cf%annavg_bgnpp(begp:endp) &
            = veg_cf%annavg_bgnpp(begp_copy:endp_copy)
         veg_cf%tempavg_agnpp(begp:endp) &
            = veg_cf%tempavg_agnpp(begp_copy:endp_copy)
         ch4_vars%ch4_prod_depth_sat_col(begc:endc,:) &
            = ch4_vars%ch4_prod_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_prod_depth_unsat_col(begc:endc,:) &
            = ch4_vars%ch4_prod_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_oxid_depth_sat_col(begc:endc,:) &
            = ch4_vars%ch4_oxid_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_oxid_depth_unsat_col(begc:endc,:) &
            = ch4_vars%ch4_oxid_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_aere_depth_sat_col(begc:endc,:) &
            = ch4_vars%ch4_aere_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_aere_depth_unsat_col(begc:endc,:) &
            = ch4_vars%ch4_aere_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_ebul_depth_sat_col(begc:endc,:) &
            = ch4_vars%ch4_ebul_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_ebul_depth_unsat_col(begc:endc,:) &
            = ch4_vars%ch4_ebul_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_ebul_total_sat_col(begc:endc) &
            = ch4_vars%ch4_ebul_total_sat_col(begc_copy:endc_copy)
         ch4_vars%ch4_ebul_total_unsat_col(begc:endc) &
            = ch4_vars%ch4_ebul_total_unsat_col(begc_copy:endc_copy)
         ch4_vars%ch4_surf_aere_sat_col(begc:endc) &
            = ch4_vars%ch4_surf_aere_sat_col(begc_copy:endc_copy)
         ch4_vars%ch4_surf_aere_unsat_col(begc:endc) &
            = ch4_vars%ch4_surf_aere_unsat_col(begc_copy:endc_copy)
         ch4_vars%ch4_surf_ebul_sat_col(begc:endc) &
            = ch4_vars%ch4_surf_ebul_sat_col(begc_copy:endc_copy)
         ch4_vars%ch4_surf_ebul_unsat_col(begc:endc) &
            = ch4_vars%ch4_surf_ebul_unsat_col(begc_copy:endc_copy)
         ch4_vars%o2_oxid_depth_sat_col(begc:endc,:) &
            = ch4_vars%o2_oxid_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%o2_oxid_depth_unsat_col(begc:endc,:) &
            = ch4_vars%o2_oxid_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%o2_aere_depth_sat_col(begc:endc,:) &
            = ch4_vars%o2_aere_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%o2_aere_depth_unsat_col(begc:endc,:) &
            = ch4_vars%o2_aere_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%conc_ch4_sat_col(begc:endc,:) &
            = ch4_vars%conc_ch4_sat_col(begc_copy:endc_copy,:)
         ch4_vars%conc_ch4_unsat_col(begc:endc,:) &
            = ch4_vars%conc_ch4_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%ch4_surf_diff_sat_col(begc:endc) &
            = ch4_vars%ch4_surf_diff_sat_col(begc_copy:endc_copy)
         ch4_vars%ch4_surf_diff_unsat_col(begc:endc) &
            = ch4_vars%ch4_surf_diff_unsat_col(begc_copy:endc_copy)
         ch4_vars%fsat_bef_col(begc:endc) &
            = ch4_vars%fsat_bef_col(begc_copy:endc_copy)
         ch4_vars%lake_soilc_col(begc:endc,:) &
            = ch4_vars%lake_soilc_col(begc_copy:endc_copy,:)
         ch4_vars%totcolch4_col(begc:endc) &
            = ch4_vars%totcolch4_col(begc_copy:endc_copy)
         ch4_vars%annsum_counter_col(begc:endc) &
            = ch4_vars%annsum_counter_col(begc_copy:endc_copy)
         ch4_vars%annavg_finrw_col(begc:endc) &
            = ch4_vars%annavg_finrw_col(begc_copy:endc_copy)
         ch4_vars%qflx_surf_lag_col(begc:endc) &
            = ch4_vars%qflx_surf_lag_col(begc_copy:endc_copy)
         ch4_vars%finundated_lag_col(begc:endc) &
            = ch4_vars%finundated_lag_col(begc_copy:endc_copy)
         ch4_vars%layer_sat_lag_col(begc:endc,:) &
            = ch4_vars%layer_sat_lag_col(begc_copy:endc_copy,:)
         ch4_vars%zwt0_col(begc:endc) &
            = ch4_vars%zwt0_col(begc_copy:endc_copy)
         ch4_vars%f0_col(begc:endc) &
            = ch4_vars%f0_col(begc_copy:endc_copy)
         ch4_vars%p3_col(begc:endc) &
            = ch4_vars%p3_col(begc_copy:endc_copy)
         ch4_vars%c_atm_grc(begg:endg,:) &
            = ch4_vars%c_atm_grc(begg_copy:endg_copy,:)
         ch4_vars%ch4co2f_grc(begg:endg) &
            = ch4_vars%ch4co2f_grc(begg_copy:endg_copy)
         ch4_vars%ch4prodg_grc(begg:endg) &
            = ch4_vars%ch4prodg_grc(begg_copy:endg_copy)
         ch4_vars%finundated_col(begc:endc) &
            = ch4_vars%finundated_col(begc_copy:endc_copy)
         ch4_vars%conc_o2_sat_col(begc:endc,:) &
            = ch4_vars%conc_o2_sat_col(begc_copy:endc_copy,:)
         ch4_vars%conc_o2_unsat_col(begc:endc,:) &
            = ch4_vars%conc_o2_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%o2_decomp_depth_sat_col(begc:endc,:) &
            = ch4_vars%o2_decomp_depth_sat_col(begc_copy:endc_copy,:)
         ch4_vars%o2_decomp_depth_unsat_col(begc:endc,:) &
            = ch4_vars%o2_decomp_depth_unsat_col(begc_copy:endc_copy,:)
         ch4_vars%grnd_ch4_cond_patch(begp:endp) &
            = ch4_vars%grnd_ch4_cond_patch(begp_copy:endp_copy)
         ch4_vars%grnd_ch4_cond_col(begc:endc) &
            = ch4_vars%grnd_ch4_cond_col(begc_copy:endc_copy)
         soilstate_vars%cellorg_col(begc:endc,:) &
            = soilstate_vars%cellorg_col(begc_copy:endc_copy,:)
         soilstate_vars%smp_l_col(begc:endc,:) &
            = soilstate_vars%smp_l_col(begc_copy:endc_copy,:)
         soilstate_vars%bsw_col(begc:endc,:) &
            = soilstate_vars%bsw_col(begc_copy:endc_copy,:)
         soilstate_vars%watsat_col(begc:endc,:) &
            = soilstate_vars%watsat_col(begc_copy:endc_copy,:)
         soilstate_vars%rootr_patch(begp:endp,:) &
            = soilstate_vars%rootr_patch(begp_copy:endp_copy,:)
         soilstate_vars%rootfr_col(begc:endc,:) &
            = soilstate_vars%rootfr_col(begc_copy:endc_copy,:)
         soilstate_vars%rootfr_patch(begp:endp,:) &
            = soilstate_vars%rootfr_patch(begp_copy:endp_copy,:)
         lakestate_vars%lake_icefrac_col(begc:endc,:) &
            = lakestate_vars%lake_icefrac_col(begc_copy:endc_copy,:)
         soilhydrology_vars%zwt_col(begc:endc) &
            = soilhydrology_vars%zwt_col(begc_copy:endc_copy)
         soilhydrology_vars%zwt_perched_col(begc:endc) &
            = soilhydrology_vars%zwt_perched_col(begc_copy:endc_copy)
         lnd2atm_vars%nem_grc(begg:endg) &
            = lnd2atm_vars%nem_grc(begg_copy:endg_copy)
   end do
   end if 
end subroutine duplicate_clumps 
end module 
