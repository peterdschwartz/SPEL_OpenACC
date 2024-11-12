module elm_initializeMod

   implicit None

   public :: elm_init
   public :: correct_physical_properties

contains

   subroutine elm_init(clump_input, pproc_input, dt, yr)

      use readMod, only: read_vars, read_weights
      use elm_varsur, only: wt_lunit, urban_valid, wt_glc_mec
      use duplicateMod, only: duplicate_clumps, duplicate_weights
      use ReadConstantsMod, only: readConstants
      use initializeParameters
      use elm_varctl
      use filterMod
      use decompMod, only: get_proc_bounds, get_clump_bounds, procinfo, clumps
      use decompMod, only: bounds_type, clump_pproc, nclumps
      use soilorder_varcon
      use timeInfoMod
      use pftvarcon
      use GridcellType
      use TopounitType
      use LandunitType
      use ColumnType
      use VegetationType
      use decompInitMod
      use elm_instMod
      use domainMod
      use landunit_varcon, only: max_lunit
      use UnitTestAllocatorMod

      !#USE_START
      use elm_varorb
      use GridcellDataType
      use TopounitDataType
      use LandunitDataType
      use ColumnDataType
      use VegetationDataType
      use VegetationPropertiesType
      use CNDecompCascadeConType
      use UrbanParamsType
      !#USE_END

      implicit none

      integer, intent(in)  :: clump_input, pproc_input
      real*8, intent(in) :: dt
      integer, intent(in) :: yr
      integer :: errc
      integer :: nc
      integer :: begp, endp, begc, endc, begg, endg, begl, endl, begt, endt
      integer :: i, j
      character(len=256) :: in_file_vars = 'LakeTemperature_vars.txt'
      character(len=256) :: in_file_constants = "E3SM_constants.txt"
      type(bounds_type)  :: bounds_proc
      type(bounds_type)  :: bounds_clump
      integer, parameter :: number_of_sites = 42
      integer, parameter :: maxtunits = 1  ! max_topounits = 1 -- multiple topounits/gridcell not supported yet
      integer :: ni, nj = 1
      integer :: c, l, g, t
      integer, allocatable :: amask(:)
      real*8, allocatable  :: icemask_grc(:)
      real(r8), allocatable :: h2osno_col(:)
      real(r8), allocatable :: snow_depth_col(:)
      real(r8), allocatable :: dummy_2d_arr(:, :)

      ! convert number use input of sets of sites to total number of sites
      ni = clump_input*number_of_sites
      clump_pproc = ni/pproc_input

      print *, "initializing parameters"
      call elm_varpar_init()
      call ReadConstants()

      call elm_varcon_init()
      call set_namelist_vars()
      call pftconrd()

      !#LAKECON

      call init_params(bounds_proc)

      print *, "nlevurb        ", nlevurb
      print *, "nlevlak        ", nlevlak
      print *, "nlevdecomp     ", nlevdecomp
      print *, "nlevdecomp_full", nlevdecomp_full
      allocate(amask(ni*nj)); amask(:) = 1
      print *, "calling decompInit_lnd"
      call decompInit_lnd(ni, nj, amask)

      ! Allocate surface grid dynamic memory (just gridcell bounds dependent)
      !NOTE: wt_lunit, urban_valid need to be updated to support
      !  multiple topounits if desired
      call get_proc_bounds(begg=begg, endg=endg)
      allocate(wt_lunit(begg:endg, maxtunits, max_lunit)); wt_lunit(:, 1, :) = 0d0
      allocate(urban_valid(begg:endg, maxtunits)); urban_valid(:, 1) = .true.

      !reshape((/1.6127168011336070D-312/),shape(wt_glc_mec))
      allocate(wt_glc_mec(1, maxtunits, 1)); wt_glc_mec = reshape((/0D0/), shape(wt_glc_mec)) 
      call read_weights(in_file_vars, numg=number_of_sites)
    !! Duplicate weights
      if (clump_input > 1) then
         print *, clump_input, "sets requested, making a total # of gridcells of ", ni
         print *, "max_lunit:", max_lunit
         call duplicate_weights(number_of_sites, ni)
      end if

      print *, "calling decompinit_clumps"
      call decompInit_clumps()

      ! No ghost cells
      procinfo%ncells_ghost = 0
      !--------------------------------------------------------------------------------
      procinfo%ntunits_ghost = 0
      procinfo%nlunits_ghost = 0
      procinfo%ncols_ghost = 0
      procinfo%npfts_ghost = 0
      procinfo%nCohorts_ghost = 0

      procinfo%begg_ghost = 0
      procinfo%begt_ghost = 0
      procinfo%begl_ghost = 0
      procinfo%begc_ghost = 0
      procinfo%begp_ghost = 0
      procinfo%begCohort_ghost = 0
      procinfo%endg_ghost = 0
      procinfo%endt_ghost = 0
      procinfo%endl_ghost = 0
      procinfo%endc_ghost = 0
      procinfo%endp_ghost = 0
      procinfo%endCohort_ghost = 0

      ! All = local (as no ghost cells)
      procinfo%ncells_all = procinfo%ncells
      procinfo%ntunits_all = procinfo%ntunits
      procinfo%nlunits_all = procinfo%nlunits
      procinfo%ncols_all = procinfo%ncols
      procinfo%npfts_all = procinfo%npfts
      procinfo%nCohorts_all = procinfo%nCohorts

      procinfo%begg_all = procinfo%begg
      procinfo%begt_all = procinfo%begt
      procinfo%begl_all = procinfo%begl
      procinfo%begc_all = procinfo%begc
      procinfo%begp_all = procinfo%begp
      procinfo%begCohort_all = procinfo%begCohort
      procinfo%endg_all = procinfo%endg
      procinfo%endt_all = procinfo%endt
      procinfo%endl_all = procinfo%endl
      procinfo%endc_all = procinfo%endc
      procinfo%endp_all = procinfo%endp
      procinfo%endCohort_all = procinfo%endCohort

      call get_proc_bounds(bounds_proc)
      print *, "nclumps = ", procinfo%nclumps

      deallocate (wt_lunit, urban_valid)
      begp = bounds_proc%begp_all; endp = bounds_proc%endp_all; 
      begc = bounds_proc%begc_all; endc = bounds_proc%endc_all; 
      begg = bounds_proc%begg_all; endg = bounds_proc%endg_all; 
      begl = bounds_proc%begl_all; endl = bounds_proc%endl_all; 
      begt = bounds_proc%begt_all; endt = bounds_proc%endt_all; 
      print *, "begp, endp", begp, endp
      print *, "begc, endc", begc, endc
      print *, "begg, endg", begg, endg
      print *, "begl, endl", begl, endl
      print *, "begt, endt", begt, endt
      allocate (h2osno_col(begc:endc)); h2osno_col(:) = 0d0
      allocate (snow_depth_col(begc:endc)); snow_depth_col(:) = 0d0

      print *, "allocating Physical Property derived types"
      call veg_pp%Init(begp, endp)
      call lun_pp%Init(begl, endl)
      call col_pp%Init(begc, endc)
      call grc_pp%Init(begg, endg)
      call top_pp%Init(begt, endt)

      call read_vars(in_file_vars, bounds_proc, mode=1, nsets=clump_input)
      if (clump_input > 1) then
         print *, "Duplicating physical properties"
         call duplicate_clumps(mode=0, unique_sites=number_of_sites, num_sites=ni)
         call correct_physical_properties(number_of_sites, ni)
      end if

      call init_decomp_cascade_constants()

      !#VAR_INIT_START

      if (use_century_decomp) then
#ifdef DECOMPCASCADEBGCMOD
         call init_decompcascade_bgc(bounds_proc, cnstate_vars, soilstate_vars)
#endif
      else
#ifdef DECOMPCASCADECNMOD
         call init_decompcascade_cn(bounds_proc, cnstate_vars)
#endif
      end if

      print *, "setting nv in main"
      ldomain%nv = 2

      call domain_init(ldomain, .false., ni, nj, begg, endg, 'lndgrid')
      call domain_check(ldomain)
    !!read for first clumps only

      call get_clump_bounds(1, bounds_clump)
      print *, "READING IN REST OF VARIABLES"
      call read_vars(in_file_vars, bounds_proc, mode=0, nsets=clump_input)

      ! Only duplicate if desired simulation is greater than
      ! number of gridcells in input data file
      if (clump_input > 1) then
         print *, "Duplicating the remaining variables"
         call duplicate_clumps(mode=1, unique_sites=number_of_sites, num_sites=ni)
      end if

      print *, "Setting up Filters"
      call allocFilters()

      nclumps = procinfo%nclumps
      allocate (icemask_grc(ni)); icemask_grc(:) = 0d0

      do nc = 1, nclumps
         call get_clump_bounds(nc, bounds_clump)
         call setFilters(bounds_clump, icemask_grc)
      end do
      !! call createProcessorFilter(nclumps, bounds_proc, proc_filter, icemask_grc)
#ifdef DYNSUBGRID
      print *, "dynSubgrid _init:"
      call init_subgrid_weights_mod(bounds_proc)
      call dynSubgrid_init(bounds_proc, glc2lnd_vars, crop_vars)
#endif

      deallocate (icemask_grc)
      deallocate (h2osno_col)
      deallocate (snow_depth_col)
      deallocate (amask)
      deallocate (dummy_2d_arr)

   end subroutine elm_init

   subroutine correct_physical_properties(unique_sites, num_sites)
      use landunit_varcon, only: max_lunit
      use GridcellType, only: grc_pp
      use VegetationType, only: veg_pp
      use ColumnType, only: col_pp
      use LandunitType, only: lun_pp
      use TopounitType, only: top_pp
      use landunit_varcon, only: max_lunit
      use elm_varcon, only: ispval
      use decompMod, only: bounds_type, procinfo, nclumps, get_clump_bounds
      implicit none
      integer, intent(in) :: num_sites, unique_sites
      integer :: nc, nc_copy, i, stride, j
      type(bounds_type)  :: bounds
      integer :: begt, endt, begl, endl, begc, endc, begp, endp
      integer :: total_landunit_indices, total_columns
      integer :: total_lu, total_pft
      integer :: l, c, p, l_copy, c_copy, p_copy

      total_landunit_indices = 0
      !get total_landunit_indices for the set of unique sites
      nc = unique_sites
      do j = 1, max_lunit
         i = top_pp%landunit_indices(j, nc)
         if (i /= ispval) then
            total_landunit_indices = max(total_landunit_indices, i)
         end if
      end do

      do nc = unique_sites + 1, num_sites
         nc_copy = mod(nc - 1, unique_sites) + 1
         call get_clump_bounds(nc, bounds)
         begt = bounds%begt; endt = bounds%endt
         begl = bounds%begl; endl = bounds%endl

         grc_pp%gindex(nc) = nc
         grc_pp%topi(nc) = begt
         grc_pp%topf(nc) = endt
         grc_pp%ntopounits(nc) = grc_pp%ntopounits(nc_copy) !endt-begt+1

         lun_pp%gridcell(begl:endl) = nc
         !NOTE: this won't work for multiple Topounits
         lun_pp%topounit(begl:endl) = nc

         do j = 1, max_lunit
            if (top_pp%landunit_indices(j, 1) == ispval) cycle
            top_pp%landunit_indices(j, nc) = top_pp%landunit_indices(j, nc_copy) + total_landunit_indices
         end do
      end do

      ! get total number of cols and landunits for the set
      call get_clump_bounds(unique_sites, bounds)
      total_columns = bounds%endc
      total_lu = bounds%endl
      total_pft = bounds%endp

      do nc = unique_sites + 1, num_sites
         nc_copy = mod(nc - 1, unique_sites) + 1
         call get_clump_bounds(nc, bounds)
         begl = bounds%begl; endl = bounds%endl
         begc = bounds%begc; endc = bounds%endc
         begp = bounds%begp; endp = bounds%endp

         do l = begl, endl
            l_copy = l - total_lu
            lun_pp%coli(l) = lun_pp%coli(l_copy) + total_columns
            lun_pp%colf(l) = lun_pp%colf(l_copy) + total_columns
            lun_pp%pfti(l) = lun_pp%pfti(l_copy) + total_pft
            lun_pp%pftf(l) = lun_pp%pftf(l_copy) + total_pft
         end do
         col_pp%gridcell(begc:endc) = nc
         col_pp%topounit(begc:endc) = nc !Need To change to allow multi topo

         do c = begc, endc
            c_copy = c - total_columns
            col_pp%landunit(c) = col_pp%landunit(c_copy) + total_lu
            col_pp%pfti(c) = col_pp%pfti(c_copy) + total_pft
            col_pp%pftf(c) = col_pp%pftf(c_copy) + total_pft
         end do
         veg_pp%gridcell(begp:endp) = nc
         veg_pp%topounit(begp:endp) = nc !Need to change
         do p = begp, endp
            p_copy = p - total_pft
            veg_pp%landunit(p) = veg_pp%landunit(p_copy) + total_lu
            veg_pp%column(p) = veg_pp%column(p_copy) + total_columns
         end do
      end do

   end subroutine

end module elm_initializeMod
