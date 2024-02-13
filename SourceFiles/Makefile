FC = pgfortran
FC_FLAGS_ACC = -g -O0 -ta=tesla:deepcopy -Minfo=accel
FC_FLAGS_DEBUG =  -g -O0 -Mbounds -Mchkptr -Mchkstk
MODEL_FLAGS = -DMODAL_AER -DCPL_BYPASS
FC_FLAGS = $(FC_FLAGS_DEBUG) $(MODEL_FLAGS)
objs = duplicateMod.o update_accMod.o initializeParameters.o readConstants.o histFileMod.o main.o
mods = DaylengthMod.o \
				QSatMod.o \
				atm2lndMod.o \
				CanopyHydrologyMod.o \
				AerosolMod.o \
				SnowSnicarMod.o \
				SurfaceRadiationMod.o \
				EnergyFluxType.o \
				UrbanRadiationMod.o \
				SurfaceResistanceMod.o \
				LakeCon.o \
				SimpleMathMod.o \
				SoilHydrologyType.o \
				AllocationMod.o \
				quadraticMod.o \
				PhotosynthesisMod.o \
				CanopyTemperatureMod.o \
				FrictionVelocityMod.o \
				TridiagonalMod.o \
				CH4Mod.o \
				BareGroundFluxesMod.o \
				SoilWaterRetentionCurveMod.o \
				SoilMoistStressMod.o \
				CanopyFluxesMod.o \
				UrbanFluxesMod.o \
				LakeFluxesMod.o \
				DUSTMod.o \
				LakeTemperatureMod.o \
				BandDiagonalMod.o \
				SoilTemperatureMod.o \
				SoilFluxesMod.o \
				SoilWaterMovementMod.o \
				SoilHydrologyMod.o \
				SnowHydrologyMod.o \
				HydrologyNoDrainageMod.o \
				LakeHydrologyMod.o \
				VerticalProfileMod.o \
				NitrifDenitrifMod.o \
				DecompCascadeBGCMod.o \
				DecompCascadeCNMod.o \
				SoilLittDecompMod.o \
				RootDynamicsMod.o \
				dynHarvestMod.o \
				SoilLittVertTranspMod.o \
				CropHarvestPoolsMod.o \
				WoodProductsMod.o \
				CarbonIsoFluxMod.o \
				CarbonStateUpdate3Mod.o \
				PhosphorusStateUpdate2Mod.o \
				NitrogenStateUpdate2Mod.o \
				CarbonStateUpdate2Mod.o \
				GapMortalityMod.o \
				PhosphorusStateUpdate1Mod.o \
				NitrogenStateUpdate1Mod.o \
				CarbonStateUpdate1Mod.o \
				GrowthRespMod.o \
				MaintenanceRespMod.o \
				PrecisionControlMod.o \
				PhosphorusStateUpdate3Mod.o \
				NitrogenStateUpdate3Mod.o \
				NitrogenDynamicsMod.o \
				PhosphorusDynamicsMod.o \
				C14DecayMod.o \
				dynSubgridControlMod.o \
				dynColumnTemplateMod.o \
				dynColumnStateUpdaterMod.o \
				dynPriorWeightsMod.o \
				ComputeSeedMod.o \
				ForcingUpdateMod.o \
				dynTimeInfoMod.o \
				dynPatchStateUpdaterMod.o \
				dynUpdateModAcc.o \
				dynSubgridAdjustmentsMod.o \
				dynConsBiogeochemMod.o \
				TotalWaterAndHeatMod.o \
				dynConsBiogeophysMod.o \
				dynInitColumnsMod.o \
				dynLandunitAreaMod.o \
				reweightMod.o \
				FireMod.o \
				timeinfoMod.o \
				ErosionMod.o \
				SedYieldMod.o \
				CropMod.o \
				PhenologyMod.o \
				LSparseMatMod.o \
				PhenologyFluxLimitMod.o \
				EcosystemDynMod.o \
				VegStructUpdateMod.o \
				EcosystemBalanceCheckMod.o \
				AnnualUpdateMod.o \
				DryDepVelocity.o \
				HydrologyDrainageMod.o \
				SurfaceAlbedoMod.o \
				UrbanAlbedoMod.o \
				SatellitePhenologyMod.o \
				WaterBudgetMod.o \
				clm_instMod.o \
				BalanceCheckMod.o \
				ActiveLayerMod.o \
				lnd2glcMod.o \
				readMod.o

const_mods = shr_kind_mod.o \
							clm_varorb.o \
							shr_const_mod.o \
							shr_orb_mod_elm.o \
							seq_drydep_mod_elm.o \
							clm_varctl.o \
							landunit_varcon.o \
							fileio_mod.o \
							clm_varpar.o \
							clm_varcon.o \
							pftvarcon.o \
							topounit_varcon.o \
							column_varcon.o  \
							soilorder_varcon.o \
							CH4varcon.o \
							domainMod.o \
							decompMod.o \
							VegetationType.o \
							ColumnType.o \
							TopounitType.o \
							LandunitType.o \
							GridcellType.o \
							UrbanParamsType.o \
							filterMod.o \
							CanopyStateType.o \
							subgridAveMod.o \
							VegetationPropertiesType.o \
							SpeciesMod.o \
							CNStateType.o \
							betr_constants.o \
							Tracer_varcon.o \
							CNDecompCascadeConType.o \
							LandunitDataType.o \
							ColumnDataType.o \
							VegetationDataType.o \
							TopounitDataType.o \
							subgridMod.o \
							decompInitMod.o \
							atm2lndType.o \
							SharedParamsMod.o \
							RootBiophysMod.o \
							SoilStateType.o \
							FrictionVelocityType.o \
							SolarAbsorbedType.o \
							SurfaceAlbedoType.o \
							PhotosynthesisType.o \
							AerosolType.o \
							clm_interface_bgcType.o \
							clm_interface_thType.o \
							clm_interface_dataType.o \
							CropType.o \
							ChemStateType.o \
							AnnualFluxDribbler.o \
							GridcellDataType.o \
							CNCarbonFluxType.o \
							LakeStateType.o \
							lnd2atmType.o \
							SoilorderConType.o \
							subgridWeightsMod.o \
							glc2lndMod.o \
							WaterfluxType.o \
							SedFluxType.o \
							Method_procs_acc.o \
							lapack_acc_seq.o



all_objects = $(const_mods) $(mods) $(objs)
elmtest.exe : $(all_objects)
	$(FC) $(FC_FLAGS) -o elmtest.exe $(all_objects)


#.SUFFIXES: .o .F90
%.o : %.F90
	$(FC) $(FC_FLAGS) -c $<

.PHONY: clean
clean:
	rm -f *.mod *.o *.exe
