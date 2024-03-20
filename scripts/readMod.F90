module readMod 
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
use VegetationDataType, only : veg_ef 
use elm_instMod, only : soilstate_vars 
use elm_instMod, only : solarabs_vars 
use UrbanParamsType, only : urbanparams_vars 
use TopounitType, only : top_pp 
use LandunitDataType, only : lun_es 
use LandunitDataType, only : lun_ef 
use decompMod, only : bounds_type 
use elm_varcon 
use elm_varpar 
use elm_varctl 
use landunit_varcon 
use elm_instMod, only: glc2lnd_vars 
contains 
subroutine read_weights(in_file,numg)
     use fileio_mod, only : fio_open, fio_read, fio_close
     use elm_varsur, only : wt_lunit, urban_valid
     implicit none
     character(len=256), intent(in) :: in_file
     integer, intent(in) :: numg
     integer :: errcode = 0

     call fio_open(18,in_file,1)
     call fio_read(18,'wt_lunit',wt_lunit(1:numg,:),errcode=errcode)
     if(errcode .ne. 0) stop
     call fio_read(18,'urban_valid',urban_valid(1:numg),errcode=errcode)
     if(errcode .ne. 0) stop

     end subroutine read_weights

subroutine read_vars(in_file,bounds,mode,nsets)
     use fileio_mod, only : fio_open, fio_read, fio_close
     implicit none 
     character(len=256),intent(in) :: in_file 
     type(bounds_type), intent(in) :: bounds 
     integer, intent(in) :: mode
     integer, intent(in) :: nsets
     integer :: errcode = 0 
     integer :: begp,  endp  
     integer :: begc,  endc  
     integer :: begg,  endg; 
     integer :: begl,  endt; 
     integer :: begt,  endl; 
     begp = bounds%begp; endp = bounds%endp/nsets 
     begc = bounds%begc; endc = bounds%endc/nsets 
     begl = bounds%begl; endl = bounds%endl/nsets 
     begt = bounds%begt; endt = bounds%endt/nsets 
     begg = bounds%begg; endg = bounds%endg/nsets 
     print *,"begp range :",begp, endp
     print *,"begc range :",begc, endc
     print *,"begl range :",begl, endl
     print *,"begt range :",begt, endt
     print *,"begg range :",begg, endg
     call fio_open(18,in_file, 1) 
     if(mode == 1) then
     print *, 'reading in physical properties'
     
     !====================== grc_pp ======================!
     
     call fio_read(18,'grc_pp%gindex', grc_pp%gindex(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%area', grc_pp%area(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%lat', grc_pp%lat(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%lon', grc_pp%lon(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%latdeg', grc_pp%latdeg(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%londeg', grc_pp%londeg(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%topi', grc_pp%topi(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%topf', grc_pp%topf(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%ntopounits', grc_pp%ntopounits(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%lndi', grc_pp%lndi(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%lndf', grc_pp%lndf(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%nlandunits', grc_pp%nlandunits(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%coli', grc_pp%coli(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%colf', grc_pp%colf(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%ncolumns', grc_pp%ncolumns(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%pfti', grc_pp%pfti(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%pftf', grc_pp%pftf(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%npfts', grc_pp%npfts(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%max_dayl', grc_pp%max_dayl(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%dayl', grc_pp%dayl(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%prev_dayl', grc_pp%prev_dayl(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%elevation', grc_pp%elevation(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%froudenum', grc_pp%froudenum(begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'grc_pp%landunit_indices', grc_pp%landunit_indices(:,begg:endg), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== lun_pp ======================!
     
     call fio_read(18,'lun_pp%gridcell', lun_pp%gridcell(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%wtgcell', lun_pp%wtgcell(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%topounit', lun_pp%topounit(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%wttopounit', lun_pp%wttopounit(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%coli', lun_pp%coli(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%colf', lun_pp%colf(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%ncolumns', lun_pp%ncolumns(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%pfti', lun_pp%pfti(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%pftf', lun_pp%pftf(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%npfts', lun_pp%npfts(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%itype', lun_pp%itype(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%ifspecial', lun_pp%ifspecial(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%lakpoi', lun_pp%lakpoi(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%urbpoi', lun_pp%urbpoi(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%glcmecpoi', lun_pp%glcmecpoi(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%active', lun_pp%active(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%canyon_hwr', lun_pp%canyon_hwr(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%wtroad_perv', lun_pp%wtroad_perv(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%wtlunit_roof', lun_pp%wtlunit_roof(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%ht_roof', lun_pp%ht_roof(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%z_0_town', lun_pp%z_0_town(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_pp%z_d_town', lun_pp%z_d_town(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== col_pp ======================!
     
     call fio_read(18,'col_pp%gridcell', col_pp%gridcell(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%wtgcell', col_pp%wtgcell(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%topounit', col_pp%topounit(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%wttopounit', col_pp%wttopounit(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%landunit', col_pp%landunit(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%wtlunit', col_pp%wtlunit(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%pfti', col_pp%pfti(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%pftf', col_pp%pftf(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%npfts', col_pp%npfts(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%itype', col_pp%itype(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%active', col_pp%active(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%glc_topo', col_pp%glc_topo(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%micro_sigma', col_pp%micro_sigma(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%n_melt', col_pp%n_melt(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%topo_slope', col_pp%topo_slope(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%topo_std', col_pp%topo_std(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%hslp_p10', col_pp%hslp_p10(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%nlevbed', col_pp%nlevbed(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%zibed', col_pp%zibed(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%snl', col_pp%snl(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%dz', col_pp%dz(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%z', col_pp%z(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%zi', col_pp%zi(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%zii', col_pp%zii(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%dz_lake', col_pp%dz_lake(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%z_lake', col_pp%z_lake(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%lakedepth', col_pp%lakedepth(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%hydrologically_active', col_pp%hydrologically_active(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_pp%is_fates', col_pp%is_fates(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== veg_pp ======================!
     
     call fio_read(18,'veg_pp%gridcell', veg_pp%gridcell(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%wtgcell', veg_pp%wtgcell(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%topounit', veg_pp%topounit(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%wttopounit', veg_pp%wttopounit(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%landunit', veg_pp%landunit(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%wtlunit', veg_pp%wtlunit(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%column', veg_pp%column(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%wtcol', veg_pp%wtcol(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%itype', veg_pp%itype(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%mxy', veg_pp%mxy(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%active', veg_pp%active(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%sp_pftorder_index', veg_pp%sp_pftorder_index(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_pp%is_fates', veg_pp%is_fates(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== top_pp ======================!
     
     call fio_read(18,'top_pp%gridcell', top_pp%gridcell(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%topo_grc_ind', top_pp%topo_grc_ind(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%wtgcell', top_pp%wtgcell(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%lndi', top_pp%lndi(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%lndf', top_pp%lndf(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%nlandunits', top_pp%nlandunits(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%coli', top_pp%coli(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%colf', top_pp%colf(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%ncolumns', top_pp%ncolumns(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%pfti', top_pp%pfti(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%pftf', top_pp%pftf(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%npfts', top_pp%npfts(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%landunit_indices', top_pp%landunit_indices(:,begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%active', top_pp%active(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%area', top_pp%area(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%lat', top_pp%lat(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%lon', top_pp%lon(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%elevation', top_pp%elevation(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%slope', top_pp%slope(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%aspect', top_pp%aspect(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%emissivity', top_pp%emissivity(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%surfalb_dir', top_pp%surfalb_dir(begt:endt,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'top_pp%surfalb_dif', top_pp%surfalb_dif(begt:endt,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,"glc2lnd_vars%icemask_grc",glc2lnd_vars%icemask_grc,errcode=errcode)
     if(errcode .ne. 0) stop
     else
     
     !====================== canopystate_vars ======================!
     
     call fio_read(18,'canopystate_vars%frac_veg_nosno_patch', canopystate_vars%frac_veg_nosno_patch(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== top_af ======================!
     
     call fio_read(18,'top_af%lwrad', top_af%lwrad(begt:endt), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== col_es ======================!
     
     call fio_read(18,'col_es%t_soisno', col_es%t_soisno(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%t_ssbef', col_es%t_ssbef(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%t_h2osfc', col_es%t_h2osfc(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%t_grnd', col_es%t_grnd(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%hc_soi', col_es%hc_soi(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%hc_soisno', col_es%hc_soisno(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%emg', col_es%emg(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%fact', col_es%fact(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_es%c_h2osfc', col_es%c_h2osfc(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== col_ef ======================!
     
     call fio_read(18,'col_ef%eflx_h2osfc_to_snow', col_ef%eflx_h2osfc_to_snow(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_snomelt', col_ef%eflx_snomelt(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_snomelt_r', col_ef%eflx_snomelt_r(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_snomelt_u', col_ef%eflx_snomelt_u(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_bot', col_ef%eflx_bot(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_fgr12', col_ef%eflx_fgr12(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_fgr', col_ef%eflx_fgr(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_building_heat', col_ef%eflx_building_heat(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_urban_ac', col_ef%eflx_urban_ac(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%eflx_urban_heat', col_ef%eflx_urban_heat(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%xmf', col_ef%xmf(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%xmf_h2osfc', col_ef%xmf_h2osfc(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ef%imelt', col_ef%imelt(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== col_ws ======================!
     
     call fio_read(18,'col_ws%h2osoi_liq', col_ws%h2osoi_liq(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%h2osoi_ice', col_ws%h2osoi_ice(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%h2osfc', col_ws%h2osfc(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%bw', col_ws%bw(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%h2osno', col_ws%h2osno(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%int_snow', col_ws%int_snow(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%snow_depth', col_ws%snow_depth(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%frac_sno_eff', col_ws%frac_sno_eff(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_ws%frac_h2osfc', col_ws%frac_h2osfc(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== col_wf ======================!
     
     call fio_read(18,'col_wf%qflx_h2osfc_to_ice', col_wf%qflx_h2osfc_to_ice(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_snomelt', col_wf%qflx_snomelt(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_snow_melt', col_wf%qflx_snow_melt(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_snofrz_lyr', col_wf%qflx_snofrz_lyr(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_snofrz', col_wf%qflx_snofrz(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_glcice', col_wf%qflx_glcice(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'col_wf%qflx_glcice_melt', col_wf%qflx_glcice_melt(begc:endc), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== veg_ef ======================!
     
     call fio_read(18,'veg_ef%eflx_gnet', veg_ef%eflx_gnet(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%eflx_anthro', veg_ef%eflx_anthro(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%eflx_traffic', veg_ef%eflx_traffic(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%eflx_wasteheat', veg_ef%eflx_wasteheat(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%eflx_heat_from_ac', veg_ef%eflx_heat_from_ac(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%dlrad', veg_ef%dlrad(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'veg_ef%cgrnd', veg_ef%cgrnd(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== soilstate_vars ======================!
     
     call fio_read(18,'soilstate_vars%bsw_col', soilstate_vars%bsw_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%watsat_col', soilstate_vars%watsat_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%sucsat_col', soilstate_vars%sucsat_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%thk_col', soilstate_vars%thk_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%tkmg_col', soilstate_vars%tkmg_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%tkdry_col', soilstate_vars%tkdry_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'soilstate_vars%csol_col', soilstate_vars%csol_col(begc:endc,:), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== solarabs_vars ======================!
     
     call fio_read(18,'solarabs_vars%sabg_soil_patch', solarabs_vars%sabg_soil_patch(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'solarabs_vars%sabg_snow_patch', solarabs_vars%sabg_snow_patch(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'solarabs_vars%sabg_patch', solarabs_vars%sabg_patch(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'solarabs_vars%sabg_chk_patch', solarabs_vars%sabg_chk_patch(begp:endp), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'solarabs_vars%sabg_lyr_patch', solarabs_vars%sabg_lyr_patch(begp:endp,:), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== urbanparams_vars ======================!
     
     call fio_read(18,'urbanparams_vars%nlev_improad', urbanparams_vars%nlev_improad(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%tk_wall', urbanparams_vars%tk_wall(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%tk_roof', urbanparams_vars%tk_roof(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%tk_improad', urbanparams_vars%tk_improad(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%cv_wall', urbanparams_vars%cv_wall(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%cv_roof', urbanparams_vars%cv_roof(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%cv_improad', urbanparams_vars%cv_improad(begl:endl,:), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%t_building_max', urbanparams_vars%t_building_max(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'urbanparams_vars%t_building_min', urbanparams_vars%t_building_min(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== lun_es ======================!
     
     call fio_read(18,'lun_es%t_building', lun_es%t_building(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     
     !====================== lun_ef ======================!
     
     call fio_read(18,'lun_ef%eflx_traffic', lun_ef%eflx_traffic(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_ef%eflx_wasteheat', lun_ef%eflx_wasteheat(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     call fio_read(18,'lun_ef%eflx_heat_from_ac', lun_ef%eflx_heat_from_ac(begl:endl), errcode=errcode)
     if (errcode .ne. 0) stop
     end if 
     call fio_close(18) 
end subroutine read_vars 
end module 
