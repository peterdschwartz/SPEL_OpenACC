module BareGroundFluxesMod

  !------------------------------------------------------------------------------
  ! !DESCRIPTION:
  ! Compute sensible and latent fluxes and their derivatives with respect
  ! to ground temperature using ground temperatures from previous time step.
  !
  ! !USES:
  use shr_kind_mod         , only : r8 => shr_kind_r8
  use decompMod            , only : bounds_type
  use CH4Mod               , only : ch4_type
  use atm2lndType          , only : atm2lnd_type
  use CanopyStateType      , only : canopystate_type
  use EnergyFluxType       , only : energyflux_type
  use FrictionVelocityType , only : frictionvel_type
  use SoilStateType        , only : soilstate_type
  use TopounitDataType     , only : top_as
  use LandunitType         , only : lun_pp
  use ColumnType           , only : col_pp
  use ColumnDataType       , only : col_es, col_ef, col_ws
  use VegetationType       , only : veg_pp
  use VegetationDataType   , only : veg_es, veg_ef, veg_ws, veg_wf
  !
  ! !PUBLIC TYPES:
  implicit none
  save
  !
  ! !PUBLIC MEMBER FUNCTIONS:
  public :: BareGroundFluxes   ! Calculate sensible and latent heat fluxes
  !------------------------------------------------------------------------------

contains

  !------------------------------------------------------------------------------
  subroutine BareGroundFluxes(num_nolakeurbanp, filter_nolakeurbanp, &
       atm2lnd_vars, canopystate_vars, soilstate_vars, &
       frictionvel_vars, ch4_vars)
    !
    ! !DESCRIPTION:
    ! Compute sensible and latent fluxes and their derivatives with respect
    ! to ground temperature using ground temperatures from previous time step.
    !
    ! !USES:
      !$acc routine seq
    use shr_const_mod        , only : SHR_CONST_RGAS
    use elm_varpar           , only : nlevgrnd
    use elm_varcon           , only : cpair, vkc, grav, denice, denh2o
    use elm_varctl           , only : use_lch4
    use landunit_varcon      , only : istsoil, istcrop
    use FrictionVelocityMod  , only : FrictionVelocity, MoninObukIni
    use QSatMod              , only : QSat
    use SurfaceResistanceMod , only : do_soilevap_beta
    !
    ! !ARGUMENTS:
    integer                , intent(in)    :: num_nolakeurbanp          ! number of pft non-lake, non-urban points in pft filter
    integer                , intent(in)    :: filter_nolakeurbanp(:)    ! patch filter for non-lake, non-urban points
    type(atm2lnd_type)     , intent(in)    :: atm2lnd_vars
    type(canopystate_type) , intent(in)    :: canopystate_vars
    type(soilstate_type)   , intent(in)    :: soilstate_vars
    type(frictionvel_type) , intent(inout) :: frictionvel_vars
    type(ch4_type)         , intent(inout) :: ch4_vars
    !
    ! !LOCAL VARIABLES:
    integer, parameter  :: niters = 3            ! maximum number of iterations for surface temperature
    integer  :: p,c,t,g,f,j,l                    ! indices
    integer  :: filterp(num_nolakeurbanp) ! patch filter for vegetated patches
    integer  :: fn                               ! number of values in local pft filter
    integer  :: fp                               ! lake filter pft index
    integer  :: iter                             ! iteration index
    real(r8) :: zldis  ! reference height "minus" zero displacement height [m]
    real(r8) :: displa ! displacement height [m]
    real(r8) :: zeta                             ! dimensionless height used in Monin-Obukhov theory
    real(r8) :: beta                             ! coefficient of convective velocity [-]
    real(r8) :: wc                               ! convective velocity [m/s]
    real(r8) :: dth      ! diff of virtual temp. between ref. height and surface
    real(r8) :: dthv                             ! diff of vir. poten. temp. between ref. height and surface
    real(r8) :: dqh      ! diff of humidity between ref. height and surface
    real(r8) :: obu     ! Monin-Obukhov length (m)
    real(r8) :: ur      ! wind speed at reference height [m/s]
    real(r8) :: um      ! wind speed including the stablity effect [m/s]
    real(r8) :: temp1   ! relation for potential temperature profile
    real(r8) :: temp12m ! relation for potential temperature profile applied at 2-m
    real(r8) :: temp2   ! relation for specific humidity profile
    real(r8) :: temp22m ! relation for specific humidity profile applied at 2-m
    real(r8) :: ustar   ! friction velocity [m/s]
    real(r8) :: tstar                            ! temperature scaling parameter
    real(r8) :: qstar                            ! moisture scaling parameter
    real(r8) :: thvstar                          ! virtual potential temperature scaling parameter
    real(r8) :: cf                               ! heat transfer coefficient from leaves [-]
    real(r8) :: ram                              ! aerodynamical resistance [s/m]
    real(r8) :: rah                              ! thermal resistance [s/m]
    real(r8) :: raw                              ! moisture resistance [s/m]
    real(r8) :: raih                             ! temporary variable [kg/m2/s]
    real(r8) :: raiw                             ! temporary variable [kg/m2/s]
    real(r8) :: fm      ! needed for BGC only to diagnose 10m wind speed
    real(r8) :: z0mg_patch
    real(r8) :: z0hg_patch
    real(r8) :: z0qg_patch
    real(r8) :: e_ref2m                ! 2 m height surface saturated vapor pressure [Pa]
    real(r8) :: de2mdT                 ! derivative of 2 m height surface saturated vapor pressure on t_ref2m
    real(r8) :: qsat_ref2m             ! 2 m height surface saturated specific humidity [kg/kg]
    real(r8) :: dqsat2mdT              ! derivative of 2 m height surface saturated specific humidity on t_ref2m
    real(r8) :: www                    ! surface soil wetness [-]
    !------------------------------------------------------------------------------

    associate(                                                          &
         snl              =>    col_pp%snl                            , & ! Input:  [integer  (:)   ]  number of snow layers
         dz               =>    col_pp%dz                             , & ! Input:  [real(r8) (:,:) ]  layer depth (m)
         zii              =>    col_pp%zii                            , & ! Input:  [real(r8) (:)   ]  convective boundary height [m]
         forc_u           =>    top_as%ubot                           , & ! Input:  [real(r8) (:)   ]  atmospheric wind speed in east direction (m/s)
         forc_v           =>    top_as%vbot                           , & ! Input:  [real(r8) (:)   ]  atmospheric wind speed in north direction (m/s)
         forc_th          =>    top_as%thbot                          , & ! Input:  [real(r8) (:)   ]  atmospheric potential temperature (Kelvin)
         forc_pbot        =>    top_as%pbot                           , & ! Input:  [real(r8) (:)   ]  atmospheric pressure (Pa)
         forc_rho         =>    top_as%rhobot                         , & ! Input:  [real(r8) (:)   ]  density (kg/m**3)
         forc_q           =>    top_as%qbot                           , & ! Input:  [real(r8) (:)   ]  atmospheric specific humidity (kg/kg)

         forc_hgt_u_patch =>    frictionvel_vars%forc_hgt_u_patch     , & ! Input:

         frac_veg_nosno   =>    canopystate_vars%frac_veg_nosno_patch , & ! Input:  [logical  (:)   ]  true=> pft is bare ground (elai+esai = zero)

         htvp             =>    col_ef%htvp             , & ! Input:  [real(r8) (:)   ]  latent heat of evaporation (/sublimation) [J/kg]

         watsat           =>    soilstate_vars%watsat_col             , & ! Input:  [real(r8) (:,:) ]  volumetric soil water at saturation (porosity)
         soilbeta         =>    soilstate_vars%soilbeta_col           , & ! Input:  [real(r8) (:)   ]  soil wetness relative to field capacity

         t_soisno         =>    col_es%t_soisno         , & ! Input:  [real(r8) (:,:) ]  soil temperature (Kelvin)
         t_grnd           =>    col_es%t_grnd           , & ! Input:  [real(r8) (:)   ]  ground surface temperature [K]
         thv              =>    col_es%thv              , & ! Input:  [real(r8) (:)   ]  virtual potential temperature (kelvin)
         thm              =>    veg_es%thm              , & ! Input:  [real(r8) (:)   ]  intermediate variable (forc_t+0.0098*forc_hgt_t_patch)
         t_h2osfc         =>    col_es%t_h2osfc         , & ! Input:  [real(r8) (:)   ]  surface water temperature

         frac_sno         =>    col_ws%frac_sno          , & ! Input:  [real(r8) (:)   ]  fraction of ground covered by snow (0 to 1)
         qg_snow          =>    col_ws%qg_snow           , & ! Input:  [real(r8) (:)   ]  specific humidity at snow surface [kg/kg]
         qg_soil          =>    col_ws%qg_soil           , & ! Input:  [real(r8) (:)   ]  specific humidity at soil surface [kg/kg]
         qg_h2osfc        =>    col_ws%qg_h2osfc         , & ! Input:  [real(r8) (:)   ]  specific humidity at h2osfc surface [kg/kg]
         qg               =>    col_ws%qg                , & ! Input:  [real(r8) (:)   ]  specific humidity at ground surface [kg/kg]
         dqgdT            =>    col_ws%dqgdT             , & ! Input:  [real(r8) (:)   ]  temperature derivative of "qg"
         h2osoi_ice       =>    col_ws%h2osoi_ice        , & ! Input:  [real(r8) (:,:) ]  ice lens (kg/m2)
         h2osoi_liq       =>    col_ws%h2osoi_liq        , & ! Input:  [real(r8) (:,:) ]  liquid water (kg/m2)

         grnd_ch4_cond    =>    ch4_vars%grnd_ch4_cond_patch          , & ! Output: [real(r8) (:)   ]  tracer conductance for boundary layer [m/s]

         eflx_sh_snow     =>    veg_ef%eflx_sh_snow    , & ! Output: [real(r8) (:)   ]  sensible heat flux from snow (W/m**2) [+ to atm]
         eflx_sh_soil     =>    veg_ef%eflx_sh_soil    , & ! Output: [real(r8) (:)   ]  sensible heat flux from soil (W/m**2) [+ to atm]
         eflx_sh_h2osfc   =>    veg_ef%eflx_sh_h2osfc  , & ! Output: [real(r8) (:)   ]  sensible heat flux from soil (W/m**2) [+ to atm]
         eflx_sh_grnd     =>    veg_ef%eflx_sh_grnd    , & ! Output: [real(r8) (:)   ]  sensible heat flux from ground (W/m**2) [+ to atm]
         eflx_sh_tot      =>    veg_ef%eflx_sh_tot     , & ! Output: [real(r8) (:)   ]  total sensible heat flux (W/m**2) [+ to atm]
         taux             =>    veg_ef%taux            , & ! Output: [real(r8) (:)   ]  wind (shear) stress: e-w (kg/m/s**2)
         tauy             =>    veg_ef%tauy            , & ! Output: [real(r8) (:)   ]  wind (shear) stress: n-s (kg/m/s**2)
         dlrad            =>    veg_ef%dlrad           , & ! Output: [real(r8) (:)   ]  downward longwave radiation below the canopy [W/m2]
         ulrad            =>    veg_ef%ulrad           , & ! Output: [real(r8) (:)   ]  upward longwave radiation above the canopy [W/m2]
         cgrnds           =>    veg_ef%cgrnds          , & ! Output: [real(r8) (:)   ]  deriv, of soil sensible heat flux wrt soil temp [w/m2/k]
         cgrndl           =>    veg_ef%cgrndl          , & ! Output: [real(r8) (:)   ]  deriv of soil latent heat flux wrt soil temp [w/m**2/k]
         cgrnd            =>    veg_ef%cgrnd           , & ! Output: [real(r8) (:)   ]  deriv. of soil energy flux wrt to soil temp [w/m2/k]

         t_ref2m          =>    veg_es%t_ref2m        , & ! Output: [real(r8) (:)   ]  2 m height surface air temperature (Kelvin)
         t_ref2m_r        =>    veg_es%t_ref2m_r      , & ! Output: [real(r8) (:)   ]  Rural 2 m height surface air temperature (Kelvin)

         q_ref2m          =>    veg_ws%q_ref2m         , & ! Output: [real(r8) (:)   ]  2 m height surface specific humidity (kg/kg)
         rh_ref2m_r       =>    veg_ws%rh_ref2m_r      , & ! Output: [real(r8) (:)   ]  Rural 2 m height surface relative humidity (%)
         rh_ref2m         =>    veg_ws%rh_ref2m        , & ! Output: [real(r8) (:)   ]  2 m height surface relative humidity (%)

         z0mg_col         =>    frictionvel_vars%z0mg_col             , & ! Output: [real(r8) (:)   ]  roughness length, momentum [m]
         z0hg_col         =>    frictionvel_vars%z0hg_col             , & ! Output: [real(r8) (:)   ]  roughness length, sensible heat [m]
         z0qg_col         =>    frictionvel_vars%z0qg_col             , & ! Output: [real(r8) (:)   ]  roughness length, latent heat [m]
         ram1             =>    frictionvel_vars%ram1_patch           , & ! Output: [real(r8) (:)   ]  aerodynamical resistance (s/m)

         qflx_ev_snow     =>    veg_wf%qflx_ev_snow     , & ! Output: [real(r8) (:)   ]  evaporation flux from snow (W/m**2) [+ to atm]
         qflx_ev_soil     =>    veg_wf%qflx_ev_soil     , & ! Output: [real(r8) (:)   ]  evaporation flux from soil (W/m**2) [+ to atm]
         qflx_ev_h2osfc   =>    veg_wf%qflx_ev_h2osfc   , & ! Output: [real(r8) (:)   ]  evaporation flux from h2osfc (W/m**2) [+ to atm]
         qflx_evap_soi    =>    veg_wf%qflx_evap_soi    , & ! Output: [real(r8) (:)   ]  soil evaporation (mm H2O/s) (+ = to atm)
         qflx_evap_tot    =>    veg_wf%qflx_evap_tot     & ! Output: [real(r8) (:)   ]  qflx_evap_soi + qflx_evap_can + qflx_tran_veg
         )

      !---------------------------------------------------
      ! Filter patches where frac_veg_nosno IS ZERO
      !---------------------------------------------------

      beta = 1._r8 ! previously set as a constant for all columns in CanopyTemperature()

      fn = 0
      do fp = 1,num_nolakeurbanp
         p = filter_nolakeurbanp(fp)
         if (frac_veg_nosno(p) == 0) then
            fn = fn + 1
            filterp(fn) = p
         end if
      end do

      ! Compute sensible and latent fluxes and their derivatives with respect
      ! to ground temperature using ground temperatures from previous time step

      do f = 1, fn
         p = filterp(f)
         c = veg_pp%column(p)
         g = veg_pp%gridcell(p)
         t = veg_pp%topounit(p)
         l = veg_pp%landunit(p)

         iter = 0

         ! Initialization variables

         displa = 0._r8
         dlrad(p)  = 0._r8
         ulrad(p)  = 0._r8

         ur    = max(1.0_r8,sqrt(forc_u(t)*forc_u(t)+forc_v(t)*forc_v(t)))
         dth   = thm(p)-t_grnd(c)
         dqh   = forc_q(t) - qg(c)
         dthv     = dth*(1._r8+0.61_r8*forc_q(t))+0.61_r8*forc_th(t)*dqh
         zldis = forc_hgt_u_patch(p)

         ! Copy column roughness to local pft-level arrays

         z0mg_patch = z0mg_col(c)
         z0hg_patch = z0hg_col(c)
         z0qg_patch = z0qg_col(c)

         ! Initialize Monin-Obukhov length and wind speed

         call MoninObukIni(ur, thv(c), dthv, zldis, z0mg_patch, um, obu )


      ! Perform stability iteration
      ! Determine friction velocity, and potential temperature and humidity
      ! profiles of the surface boundary layer
      ITERATION : do while( iter < niters)



           call FrictionVelocity(f,p, &
                displa, z0mg_patch, z0hg_patch, z0qg_patch, &
                obu, iter+1, ur, um, ustar, &
                temp1, temp2, temp12m, temp22m, fm, &
                frictionvel_vars)


            tstar = temp1*dth
            qstar = temp2*dqh
            z0hg_patch = z0mg_patch/exp(0.13_r8 * (ustar*z0mg_patch/1.5e-5_r8)**0.45_r8)
            z0qg_patch = z0hg_patch
            thvstar = tstar*(1._r8+0.61_r8*forc_q(t)) + 0.61_r8*forc_th(t)*qstar
            zeta = zldis*vkc*grav*thvstar/(ustar**2*thv(c))

            if (zeta >= 0._r8) then                   !stable
               zeta = min(2._r8,max(zeta,0.01_r8))
               um = max(ur,0.1_r8)
            else                                      !unstable
               zeta = max(-100._r8,min(zeta,-0.01_r8))
               wc = beta*(-grav*ustar*thvstar*zii(c)/thv(c))**0.333_r8
               um = sqrt(ur*ur + wc*wc)
            end if
            obu = zldis/zeta

         !end do
         iter = iter + 1
      end do ITERATION! end stability iteration



         ! Determine aerodynamic resistances

         ram  = 1._r8/(ustar*ustar/um)
         rah  = 1._r8/(temp1*ustar)
         raw  = 1._r8/(temp2*ustar)
         raih = forc_rho(t)*cpair/rah
         if (use_lch4) then
            grnd_ch4_cond(p) = 1._r8/raw
         end if

         ! Soil evaporation resistance
         www = (h2osoi_liq(c,1)/denh2o+h2osoi_ice(c,1)/denice)/dz(c,1)/watsat(c,1)
         www = min(max(www,0.0_r8),1._r8)

         !changed by K.Sakaguchi. Soilbeta is used for evaporation
         if (dqh > 0._r8) then  !dew  (beta is not applied, just like rsoil used to be)
            raiw = forc_rho(t)/(raw)
         else
            if(do_soilevap_beta())then
               ! Lee and Pielke 1992 beta is applied
               raiw    = soilbeta(c)*forc_rho(t)/(raw)
            endif
         end if

         ram1(p) = ram  !pass value to global variable

         ! Output to pft-level data structures
         ! Derivative of fluxes with respect to ground temperature
         cgrnds(p) = raih
         cgrndl(p) = raiw*dqgdT(c)
         cgrnd(p)  = cgrnds(p) + htvp(c)*cgrndl(p)

         ! Surface fluxes of momentum, sensible and latent heat
         ! using ground temperatures from previous time step
         taux(p)          = -forc_rho(t)*forc_u(t)/ram
         tauy(p)          = -forc_rho(t)*forc_v(t)/ram
         eflx_sh_grnd(p)  = -raih*dth
         eflx_sh_tot(p)   = eflx_sh_grnd(p)

         ! compute sensible heat fluxes individually
         eflx_sh_snow(p)   = -raih*(thm(p)-t_soisno(c,snl(c)+1))
         eflx_sh_soil(p)   = -raih*(thm(p)-t_soisno(c,1))
         eflx_sh_h2osfc(p) = -raih*(thm(p)-t_h2osfc(c))

         ! water fluxes from soil
         qflx_evap_soi(p)  = -raiw*dqh
         qflx_evap_tot(p)  = qflx_evap_soi(p)

         ! compute latent heat fluxes individually
         qflx_ev_snow(p)   = -raiw*(forc_q(t) - qg_snow(c))
         qflx_ev_soil(p)   = -raiw*(forc_q(t) - qg_soil(c))
         qflx_ev_h2osfc(p) = -raiw*(forc_q(t) - qg_h2osfc(c))

         ! 2 m height air temperature
         t_ref2m(p) = thm(p) + temp1*dth*(1._r8/temp12m - 1._r8/temp1)

         ! 2 m height specific humidity
         q_ref2m(p) = forc_q(t) + temp2*dqh*(1._r8/temp22m - 1._r8/temp2)

         ! 2 m height relative humidity
         call QSat(t_ref2m(p), forc_pbot(t), e_ref2m, de2mdT, qsat_ref2m, dqsat2mdT)

         rh_ref2m(p) = min(100._r8, q_ref2m(p) / qsat_ref2m * 100._r8)

         if (lun_pp%itype(l) == istsoil .or. lun_pp%itype(l) == istcrop) then
            rh_ref2m_r(p) = rh_ref2m(p)
            t_ref2m_r(p) = t_ref2m(p)
         end if

      end do

    end associate

  end subroutine BareGroundFluxes

end module BareGroundFluxesMod
