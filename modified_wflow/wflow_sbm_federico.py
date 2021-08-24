#!/usr/bin/python

# Wflow is Free software, see below:
#
# Copyright (c) J. Schellekens/Deltares 2005-2014
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Run the wflow_sbm hydrological model..

usage

::

    wflow_sbm [-h][-v level][-F runinfofile][-L logfile][-C casename][-R runId]
          [-c configfile][-T last_step][-S first_step][-s seconds][-W][-E][-N][-U discharge]
          [-P parameter multiplication][-X][-f][-I][-i tbl_dir][-x subcatchId][-u updatecols]
          [-p inputparameter multiplication][-l loglevel][-r config_reservoir_file]


    -X: save state at the end of the run over the initial conditions at the start

    -f: Force overwrite of existing results

    -T: Set end time of the run: yyyy-mm-dd hh:mm:ss

    -S: Set start time of the run: yyyy-mm-dd hh:mm:ss

    -s: Set the model timesteps in seconds

    -I: re-initialize the initial model conditions with default

    -i: Set input table directory (default is intbl)

    -x: Apply multipliers (-P/-p ) for subcatchment only (e.g. -x 1)

    -C: set the name  of the case (directory) to run

    -R: set the name runId within the current case

    -L: set the logfile

    -E: Switch on reinfiltration of overland flow

    -c: name of wflow the configuration file (default: Casename/wflow_sbm.ini).

    -h: print usage information

    -W: If set, this flag indicates that an ldd is created for the water level
        for each timestep. If not the water is assumed to flow according to the
        DEM. Wflow will run a lot slower with this option. Most of the time
        (shallow soil, steep topography) you do not need this option. Also, if you
        need it you migth actually need another model.

    -U: The argument to this option should be a .tss file with measured discharge in
        [m^3/s] which the progam will use to update the internal state to match
        the measured flow. The number of columns in this file should match the
        number of gauges in the wflow_gauges.map file.

    -u: list of gauges/columns to use in update. Format:
        -u [1 , 4 ,13]
        The above example uses column 1, 4 and 13

    -P: set parameter change string (e.g: -P "self.FC = self.FC * 1.6") for non-dynamic variables

    -p: set parameter change string (e.g: -P "self.Precipitation = self.Precipitation * 1.11") for
        dynamic variables


    -l: loglevel (most be one of DEBUG, WARNING, ERROR)
    
    -r: config_reservoir_file, file in ini format pointing at files of reservoir subset, coordinates, characteristics (damID, depth, storage, outflow, endTerms) in dataframe format

"""

import numpy
import pandas as pd

# import pcrut
import sys
import os
import os.path
import getopt

#try:
from wflow.wf_DynamicFramework_federico import *
from wflow.wflow_funcs import *
from wflow.wflow_adapt import *
#except:
#    from wf_DynamicFramework_federico import *
#    from wflow_funcs import *
#    from wflow_adapt import *
import gdal
from gdalconst import *
driver = gdal.GetDriverByName('PCRaster')
driver.Register()


wflow = "wflow_sbm: "

updateCols = []


def usage(*args):
    sys.stdout = sys.stderr
    """Way"""
    for msg in args:
        print(msg)
    print(__doc__)
    sys.exit(0)


def actEvap_sat_SBM(RootingDepth, WTable, FirstZoneDepth, PotTrans, smoothpar):
    # Step 1 from saturated zone, use rootingDepth as a limiting factor
    # new method:
    # use sCurve to determine if the roots are wet.At the moment this ise set
    # to be a 0-1 curve
    wetroots = sCurve(WTable, a=RootingDepth, c=smoothpar)
    ActEvapSat = min(PotTrans * wetroots, FirstZoneDepth)

    FirstZoneDepth = FirstZoneDepth - ActEvapSat
    RestPotEvap = PotTrans - ActEvapSat

    return RestPotEvap, FirstZoneDepth, ActEvapSat


def actEvap_unsat_SBM(
    RootingDepth,
    WTable,
    UStoreDepth,
    zi_layer,
    UStoreLayerThickness,
    sumLayer,
    RestPotEvap,
    maskLayer,
    ZeroMap,
    layerIndex,
    sumActEvapUStore,
    c,
    L,
    thetaS,
    thetaR,
    ust=0,
):
    """
    Actual evaporation function:

    - first try to get demand from the saturated zone, using the rootingdepth as a limiting factor
    - secondly try to get the remaining water from the unsaturated store
    - it uses an S-Curve the make sure roots het wet/dry gradually (basically)
      representing a root-depth distribution
 
      if ust is True, all ustore is deems to be avaiable fro the roots a

    Input:

        - RootingDepth,WTable, UStoreDepth,FirstZoneDepth, PotTrans, smoothpar

    Output:

        - ActEvap,  FirstZoneDepth,  UStoreDepth ActEvapUStore
    """

    # AvailCap is fraction of unsat zone containing roots
    if ust >= 1:
        AvailCap = UStoreDepth * 0.99
    else:
        AvailCap = ifthenelse(
            layerIndex < zi_layer,
            min(1.0, max(0.0, (RootingDepth - sumLayer) / UStoreLayerThickness)),
            min(1.0, max(0.0, (RootingDepth - sumLayer) / (WTable + 1 - sumLayer))),
        )

    MaxExtr = AvailCap * UStoreDepth

    # Calculate the reduction of RestPotEvap due to differences in rooting density in the soil column
    # The used model is based on Vrugt et al. (2001) and uses as input parameters for z* and Pz the
    # values of Hoffman and van Genuchten (z* = 0.20 and Pz = 1.00)

    # Next step is to make use of the Feddes curve in order to decrease ActEvapUstore when soil moisture values
    # occur above or below ideal plant growing conditions (see also Feddes et al., 1978). h1-h4 values are
    # actually negative, but all values are made positive for simplicity.
    hb = 1  # cm (pF 1 for atmospheric pressure)
    h1 = 1  # cm
    h2 = 100  # cm (pF 2 for field capacity)
    h3 = 400  # cm (pF 3, critical pF value)
    h4 = 15849  # cm (pF 4.2, wilting point)

    # According to Brooks-Corey
    par_lambda = 2 / (c - 3)
    L = cover(L, 0)
    UStoreDepth = cover(UStoreDepth, 0)
    vwc = ifthenelse(L > 0, UStoreDepth / L, 0)
    vwc = ifthenelse(vwc > 0, vwc, 0.0000001)
    head = hb / (
        ((vwc) / (thetaS - thetaR)) ** (1 / par_lambda)
    )  # Note that in the original formula, thetaR is extracted from vwc, but thetaR is not part of the numerical vwc calculation
    head = ifthenelse(head <= hb, 1, head)
    head = cover(head, 0)

    # Transform h to a reduction coefficient value according to Feddes et al. (1978).
    alpha = ifthenelse(
        head <= h1,
        0,
        ifthenelse(
            head >= h4,
            0,
            ifthenelse(
                head < h2,
                (head - h1) / (h2 - h1),
                ifthenelse(head > h3, 1 - (head - h3) / (h4 - h3), 1),
            ),
        ),
    )

    ActEvapUStore = (
        ifthenelse(
            layerIndex > zi_layer, ZeroMap, min(MaxExtr, RestPotEvap, UStoreDepth)
        )
    ) * alpha

    UStoreDepth = ifthenelse(
        layerIndex > zi_layer, maskLayer, UStoreDepth - ActEvapUStore
    )

    RestPotEvap = RestPotEvap - ActEvapUStore
    sumActEvapUStore = ActEvapUStore + sumActEvapUStore

    return UStoreDepth, sumActEvapUStore, RestPotEvap, ActEvapUStore


def soilevap_SBM_unsat(
    CanopyGapFraction,
    PotTransSoil,
    SoilWaterCapacity,
    SatWaterDepth,
    UStoreLayerDepth,
    zi,
    thetaS,
    thetaR,
    UStoreLayerThickness,
):
    # Split between bare soil and vegetation
    # potsoilevap = (1.0 - CanopyGapFraction) * PotTransSoil

    # PotTrans = CanopyGapFraction * PotTransSoil
    SaturationDeficit = SoilWaterCapacity - SatWaterDepth

    # Linear reduction of soil moisture evaporation based on deficit
    soilevap = ifthenelse(
        len(UStoreLayerThickness) == 1,
        PotTransSoil * min(1.0, SaturationDeficit / SoilWaterCapacity),
        PotTransSoil
        * min(
            1.0,
            ifthenelse(
                zi >= UStoreLayerThickness[0],
                UStoreLayerDepth[0] / (UStoreLayerThickness[0] * (thetaS - thetaR)),
                UStoreLayerDepth[0] / ((zi + 1.0) * (thetaS - thetaR)),
            ),
        ),
    )

    return soilevap

def soilevap_SBM_sat(PotTransSoil,zi,thetaS,thetaR,UStoreLayerThickness, UStoreLayerDepth):
    # Follows after soilevap_SBM_unsat and requires the PotTranSoil that remains after
    # soilevap_SBM_unsat. 
    # soilevap_SBM_sat only takes place in the upper layer.
    
    # Only works when more than 1 layer is used, otherwise soilevap_sat equals 0.
    # PotTranSoil is reduced when there is either no saturated water layer in the 
    # upper soil layer (reduced to zero), or when the saturated layer is only a 
    # fraction of the upper soil layer (reduced to that fraction).
    
    # In case water is ponding, zi is negative - Start with setting negative values 
    # to 0.0 to assure positive soilevap values
    zi = ifthenelse(zi < 0.0, 0.0, zi)
    
    # Calculate soilevap
    soilevap_sat = ifthenelse(len(UStoreLayerThickness)==1, 0.0, PotTransSoil * min(1.0, ifthenelse(zi >= UStoreLayerThickness[0], 0.0, (UStoreLayerThickness[0] - zi)/UStoreLayerThickness[0])))
    
    # Set soilevap to demand (soilevap_sat) or, if less than the demand, the depth
    # of the saturated water layer
    soilevapsat = ifthenelse(len(UStoreLayerThickness)==1, 0.0, min(soilevap_sat, ifthenelse(zi >= UStoreLayerThickness[0], 0.0, (UStoreLayerThickness[0] - zi)*(thetaS-thetaR))))
    
    return soilevapsat


def sum_UstoreLayerDepth(UStoreLayerThickness, ZeroMap, UStoreLayerDepth):
    sum_UstoreLayerDepth = ZeroMap
    for n in np.arange(0, len(UStoreLayerThickness)):
        sum_UstoreLayerDepth = sum_UstoreLayerDepth + cover(
            UStoreLayerDepth[n], ZeroMap
        )

    return sum_UstoreLayerDepth


def SnowPackHBV(Snow, SnowWater, Precipitation, Temperature, TTI, TT, TTM, Cfmax, WHC):
    """
    HBV Type snowpack modelling using a Temperature degree factor. All correction
    factors (RFCF and SFCF) are set to 1. The refreezing efficiency factor is set to 0.05.

    :param Snow:
    :param SnowWater:
    :param Precipitation:
    :param Temperature:
    :param TTI:
    :param TT:
    :param TTM:
    :param Cfmax:
    :param WHC:
    :return: Snow,SnowMelt,Precipitation
    """

    RFCF = 1.0  # correction factor for rainfall
    CFR = 0.05000  # refreeing efficiency constant in refreezing of freewater in snow
    SFCF = 1.0  # correction factor for snowfall

    RainFrac = ifthenelse(
        1.0 * TTI == 0.0,
        ifthenelse(Temperature <= TT, scalar(0.0), scalar(1.0)),
        min((Temperature - (TT - TTI / 2)) / TTI, scalar(1.0)),
    )
    RainFrac = max(
        RainFrac, scalar(0.0)
    )  # fraction of precipitation which falls as rain
    SnowFrac = 1 - RainFrac  # fraction of precipitation which falls as snow
    Precipitation = (
        SFCF * SnowFrac * Precipitation + RFCF * RainFrac * Precipitation
    )  # different correction for rainfall and snowfall

    SnowFall = SnowFrac * Precipitation  # snowfall depth
    RainFall = RainFrac * Precipitation  # rainfall depth
    PotSnowMelt = ifthenelse(
        Temperature > TTM, Cfmax * (Temperature - TTM), scalar(0.0)
    )  # Potential snow melt, based on temperature
    PotRefreezing = ifthenelse(
        Temperature < TTM, Cfmax * CFR * (TTM - Temperature), 0.0
    )  # Potential refreezing, based on temperature
    Refreezing = ifthenelse(
        Temperature < TTM, min(PotRefreezing, SnowWater), 0.0
    )  # actual refreezing
    # No landuse correction here
    SnowMelt = min(PotSnowMelt, Snow)  # actual snow melt
    Snow = Snow + SnowFall + Refreezing - SnowMelt  # dry snow content
    SnowWater = SnowWater - Refreezing  # free water content in snow
    MaxSnowWater = Snow * WHC  # Max water in the snow
    SnowWater = (
        SnowWater + SnowMelt + RainFall
    )  # Add all water and potentially supersaturate the snowpack
    RainFall = max(SnowWater - MaxSnowWater, 0.0)  # rain + surpluss snowwater
    SnowWater = SnowWater - RainFall

    return Snow, SnowWater, SnowMelt, RainFall, SnowFall


def GlacierMelt(GlacierStore, Snow, Temperature, TT, Cfmax):
    """
    Glacier modelling using a Temperature degree factor. Melting
    only occurs if the snow cover > 10 mm


    :ivar GlacierStore:
    :ivar Snow: Snow pack on top of Glacier
    :ivar Temperature:

    :returns: GlacierStore,GlacierMelt,
    """

    PotMelt = ifthenelse(
        Temperature > TT, Cfmax * (Temperature - TT), scalar(0.0)
    )  # Potential snow melt, based on temperature

    GlacierMelt = ifthenelse(
        Snow > 10.0, min(PotMelt, GlacierStore), cover(0.0)
    )  # actual Glacier melt
    GlacierStore = GlacierStore - GlacierMelt  # dry snow content

    return GlacierStore, GlacierMelt


class WflowModel(DynamicModel):
    """
    .. versionchanged:: 0.91
        - Calculation of GWScale moved to resume() to allow fitting.

    .. versionadded:: 0.91
        - added S-curve for freezing soil infiltration reduction calculations

    .. todo::
        - add slope based quick-runoff -> less percolation on hillslopes...
  """

    def __init__(self, cloneMap, Dir, RunDir, configfile, config_reservoir_file=None):
        DynamicModel.__init__(self)

        self.UStoreLayerDepth = []
        self.caseName = os.path.abspath(Dir)
        self.clonemappath = os.path.join(os.path.abspath(Dir), "staticmaps", cloneMap)
        setclone(self.clonemappath)
        self.runId = RunDir
        self.Dir = os.path.abspath(Dir)
        self.configfile = configfile
        if not(config_reservoir_file == None):
            self.config_reservoir_file = config_reservoir_file
        self.SaveDir = os.path.join(self.Dir, self.runId)
        ds_studyarea = gdal.Open(os.path.join(self.Dir, "staticmaps/step2/wflow_dem.map"), GA_ReadOnly)
        coords_system = ds_studyarea.GetProjection()
        self.coords_system = coords_system
        ds_studyarea = None

    def irrigationdemand(self, pottrans, acttrans, irareas):
        """
        Determine irrigation water demand from the difference bewteen potential
        transpiration and actual transpiration.

        :param pottrans: potential transpiration (epot minus interception and soil/open water evaporation)
        :param acttrans: actual transpiration
        :param ir_areas: maps of irrigation areas

        :return: demand
        """

        Et_diff = areaaverage(pottrans - acttrans, nominal(irareas))
        # Now determine demand in m^3/s for each area
        sqmarea = areatotal(self.reallength * self.reallength, nominal(irareas))
        m3sec = Et_diff * sqmarea / 1000.0 / self.timestepsecs

        return Et_diff, m3sec

    def updateRunOff(self):
        """
      Updates the kinematic wave reservoir. Should be run after updates to Q
      """
        self.WaterLevel = (self.Alpha * pow(self.SurfaceRunoff, self.Beta)) / self.Bw
        # wetted perimeter (m)
        P = self.Bw + (2 * self.WaterLevel)
        # Alpha
        self.Alpha = self.AlpTerm * pow(P, self.AlpPow)
        self.OldKinWaveVolume = self.KinWaveVolume
        self.KinWaveVolume = self.WaterLevel * self.Bw * self.DCL

    def stateVariables(self):
        """
        returns a list of state variables that are essential to the model.
        This list is essential for the resume and suspend functions to work.

        This function is specific for each model and **must** be present.

       :var self.SurfaceRunoff: Surface runoff in the kin-wave resrvoir [m^3/s]
       :var self.SurfaceRunoffDyn: Surface runoff in the dyn-wave resrvoir [m^3/s]
       :var self.WaterLevel: Water level in the kin-wave resrvoir [m]
       :var self.WaterLevelDyn: Water level in the dyn-wave resrvoir [m^]
       :var self.Snow: Snow pack [mm]
       :var self.SnowWater: Snow pack water [mm]
       :var self.TSoil: Top soil temperature [oC]
       :var self.UStoreDepth: Water in the Unsaturated Store [mm]
       :var self.SatWaterDepth: Water in the saturated store [mm]
       :var self.CanopyStorage: Amount of water on the Canopy [mm]
       :var self.ReservoirVolume: Volume of each reservoir [m^3]
       :var self.OutflowSR: discharge out of each reservoir [m^3/s]
       :var self.GlacierStore: Thickness of the Glacier in a gridcell [mm]
       """
        states = [
            "SurfaceRunoff",
            "WaterLevel",
            "SatWaterDepth",
            "Snow",
            "TSoil",
            "UStoreLayerDepth",
            "SnowWater",
            "CanopyStorage",
        ]
        if hasattr(self, "GlacierFrac"):
            states.append("GlacierStore")

        #if hasattr(self, "ReserVoirSimpleLocs"):
        if hasattr(self, "config_reservoir_file"):
            states.append("ReservoirVolume")
            states.append("OutflowSR")

        if hasattr(self, "ReserVoirComplexLocs"):
            states.append("ReservoirWaterLevel")

        if hasattr(self, "nrpaddyirri"):
            if self.nrpaddyirri > 0:
                states.append("PondingDepth")
        return states

    def supplyCurrentTime(self):
        """
      gets the current time in seconds after the start of the run
      """
        return self.currentTimeStep() * self.timestepsecs

    def suspend(self):

        self.logger.info("Saving initial conditions...")
        self.wf_suspend(os.path.join(self.SaveDir, "outstate"))

        if self.OverWriteInit:
            self.logger.info("Saving initial conditions over start conditions...")
            self.wf_suspend(self.SaveDir + "/instate/")

    def parameters(self):
        """
        Define all model parameters here that the framework should handle for the model
        See wf_updateparameters and the parameters section of the ini file
        If you use this make sure to all wf_updateparameters at the start of the dynamic section
        and at the start/end of the initial section
        """
        modelparameters = []

        # Static model parameters e.g.
        # modelparameters.append(self.ParamType(name="RunoffGeneratingGWPerc",stack="intbl/RunoffGeneratingGWPerc.tbl",type="static",default=0.1))
        # 3: Input time series ###################################################
        self.P_mapstack = self.Dir + configget(
            self.config, "inputmapstacks", "Precipitation", "/inmaps/P"
        )  # timeseries for rainfall
        self.PET_mapstack = self.Dir + configget(
            self.config, "inputmapstacks", "EvapoTranspiration", "/inmaps/PET"
        )  # timeseries for rainfall"/inmaps/PET"          # potential evapotranspiration
        self.TEMP_mapstack = self.Dir + configget(
            self.config, "inputmapstacks", "Temperature", "/inmaps/TEMP"
        )  # timeseries for rainfall "/inmaps/TEMP"          # global radiation
        self.Inflow_mapstack = self.Dir + configget(
            self.config, "inputmapstacks", "Inflow", "/inmaps/IF"
        )  # timeseries for rainfall "/inmaps/IF" # in/outflow locations (abstractions)

        # Meteo and other forcing
        modelparameters.append(
            self.ParamType(
                name="Precipitation",
                stack=self.P_mapstack,
                type="timeseries",
                default=0.0,
                verbose=True,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="PotenEvap",
                stack=self.PET_mapstack,
                type="timeseries",
                default=0.0,
                verbose=True,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="Temperature",
                stack=self.TEMP_mapstack,
                type="timeseries",
                default=10.0,
                verbose=True,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="Inflow",
                stack=self.Inflow_mapstack,
                type="timeseries",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )

        modelparameters.append(
            self.ParamType(
                name="IrrigationAreas",
                stack="staticmaps/wflow_irrigationareas.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="IrrigationSurfaceIntakes",
                stack="staticmaps/wflow_irrisurfaceintake.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="IrrigationPaddyAreas",
                stack="staticmaps/wflow_irrigationpaddyareas.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="IrrigationSurfaceReturn",
                stack="staticmaps/wflow_irrisurfacereturns.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )

        modelparameters.append(
            self.ParamType(
                name="h_max",
                stack="staticmaps/wflow_hmax.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="h_min",
                stack="staticmaps/wflow_hmin.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )
        modelparameters.append(
            self.ParamType(
                name="h_p",
                stack="staticmaps/wflow_hp.map",
                type="staticmap",
                default=0.0,
                verbose=False,
                lookupmaps=[],
            )
        )

        return modelparameters

    def initial(self):
        """
    Initial part of the model, executed only once. Reads all static data
    (staticmaps) from disk


    *Soil*

    :var M.tbl: M parameter in the SBM model. Governs the decay of Ksat with depth [-]
    :var thetaR.tbl: Residual water content [mm/mm]
    :var thetaS.tbl: Saturated water content (porosity) [mm/mm]
    :var KsatVer.tbl: Saturated conductivity [mm/d]
    :var PathFrac.tbl: Fraction of compacted area per grid cell [-]
    :var InfiltCapSoil.tbl: Soil infiltration capacity [m/d]
    :var InfiltCapPath.tbl: Infiltration capacity of the compacted areas [mm/d]
    :var SoilMinThickness.tbl: Minimum wdepth of the soil [mm]
    :var SoilThickness.tbl: Maximum depth of the soil [m]
    :var RootingDepth.tbl: Depth of the roots [mm]
    :var MaxLeakage.tbl: Maximum leakage out of the soil profile [mm/d]
    :var CapScale.tbl: Scaling factor in the Capilary rise calculations (100) [mm/d]
    :var RunoffGeneratingGWPerc: Fraction of the soil depth that contributes to subcell runoff (0.1) [-]
    :var rootdistpar.tbl: Determine how roots are linked to water table. The number
        should be negative. A more negative  number means that all roots are wet if the water
        table is above the lowest part of the roots.
        A less negative number smooths this. [mm] (default = -80000)



    *Canopy*

    :var CanopyGapFraction.tbl: Fraction of precipitation that does not hit the canopy directly [-]
    :var MaxCanopyStorage.tbl: Canopy interception storage capacity [mm]
    :var EoverR.tbl: Ratio of average wet canopy evaporation rate over rainfall rate [-]

    *Surface water*

    :var N.tbl: Manning's N parameter
    :var N_river.tbl: Manning's N parameter for cells marked as river


    *Snow and frozen soil modelling parameters*

    :var cf_soil.tbl: Soil infiltration reduction factor when soil is frozen [-] (< 1.0)
    :var TTI.tbl: critical temperature for snowmelt and refreezing  (1.000) [oC]
    :var TT.tbl: defines interval in which precipitation falls as rainfall and snowfall (-1.41934) [oC]
    :var Cfmax.tbl: meltconstant in temperature-index ( 3.75653) [-]
    :var WHC.tbl: fraction of Snowvolume that can store water (0.1) [-]
    :var w_soil.tbl: Soil temperature smooth factor. Given for daily timesteps. (0.1125) [-] Wigmosta, M. S., L. J. Lane, J. D. Tagestad, and A. M. Coleman (2009).

    """
        global statistics
        global multpars
        global updateCols

        self.thestep = scalar(0)
        self.basetimestep = 3600
        self.SSSF = False
        setglobaloption("unittrue")

        self.logger.info("running for " + str(self.nrTimeSteps()) + " timesteps")

        # Set and get defaults from ConfigFile here ###################################

        self.Tslice = int(configget(self.config, "model", "Tslice", "1"))
        self.reinit = int(configget(self.config, "run", "reinit", "0"))
        self.OverWriteInit = int(configget(self.config, "model", "OverWriteInit", "0"))
        self.updating = int(configget(self.config, "model", "updating", "0"))
        self.updateFile = configget(self.config, "model", "updateFile", "no_set")
        self.LateralMethod = int(configget(self.config, "model", "lateralmethod", "1"))
        self.TransferMethod = int(
            configget(self.config, "model", "transfermethod", "1")
        )
        self.maxitsupply = int(configget(self.config, "model", "maxitsupply", "5"))
        self.UST = int(configget(self.config, "model", "Whole_UST_Avail", "0"))
        self.NRiverMethod = int(configget(self.config, "model", "nrivermethod", "1"))

        if self.LateralMethod == 1:
            self.logger.info(
                "Applying the original topog_sbm lateral transfer formulation"
            )
        elif self.LateralMethod == 2:
            self.logger.warning("Using alternate wflow lateral transfer formulation")

        if self.TransferMethod == 1:
            self.logger.info(
                "Applying the original topog_sbm vertical transfer formulation"
            )
        elif self.TransferMethod == 2:
            self.logger.warning("Using alternate wflow vertical transfer formulation")

        self.sCatch = int(configget(self.config, "model", "sCatch", "0"))
        self.intbl = configget(self.config, "model", "intbl", "intbl")

        self.modelSnow = int(configget(self.config, "model", "ModelSnow", "1"))
        sizeinmetres = int(configget(self.config, "layout", "sizeinmetres", "0"))
        alf = float(configget(self.config, "model", "Alpha", "60"))
        # TODO: make this into a list for all gauges or a map
        Qmax = float(configget(self.config, "model", "AnnualDischarge", "300"))
        self.UpdMaxDist = float(configget(self.config, "model", "UpdMaxDist", "100"))

        self.MaxUpdMult = float(configget(self.config, "model", "MaxUpdMult", "1.3"))
        self.MinUpdMult = float(configget(self.config, "model", "MinUpdMult", "0.7"))
        self.UpFrac = float(configget(self.config, "model", "UpFrac", "0.8"))

        # self.ExternalQbase=int(configget(self.config,'model','ExternalQbase','0'))
        self.waterdem = int(configget(self.config, "model", "waterdem", "0"))
        WIMaxScale = float(configget(self.config, "model", "WIMaxScale", "0.8"))
        self.reInfilt = int(configget(self.config, "model", "reInfilt", "0"))
        self.MassWasting = int(configget(self.config, "model", "MassWasting", "0"))

        self.nrLayers = int(configget(self.config, "model", "nrLayers", "1"))

        # static maps to use (normally default)
        wflow_subcatch = configget(
            self.config, "model", "wflow_subcatch", "staticmaps/wflow_subcatch.map"
        )
        
        wflow_dem = configget(
            self.config, "model", "wflow_dem", "staticmaps/wflow_dem.map"
        )
        wflow_ldd = configget(
            self.config, "model", "wflow_ldd", "staticmaps/wflow_ldd.map"
        )
        wflow_river = configget(
            self.config, "model", "wflow_river", "staticmaps/wflow_river.map"
        )
        wflow_riverlength = configget(
            self.config,
            "model",
            "wflow_riverlength",
            "staticmaps/wflow_riverlength.map",
        )
        wflow_riverlength_fact = configget(
            self.config,
            "model",
            "wflow_riverlength_fact",
            "staticmaps/wflow_riverlength_fact.map",
        )
        wflow_landuse = configget(
            self.config, "model", "wflow_landuse", "staticmaps/wflow_landuse.map"
        )
        wflow_soil = configget(
            self.config, "model", "wflow_soil", "staticmaps/wflow_soil.map"
        )
        wflow_gauges = configget(
            self.config, "model", "wflow_gauges", "staticmaps/wflow_gauges.map"
        )
        wflow_inflow = configget(
            self.config, "model", "wflow_inflow", "staticmaps/wflow_inflow.map"
        )
        wflow_riverwidth = configget(
            self.config, "model", "wflow_riverwidth", "staticmaps/wflow_riverwidth.map"
        )
        wflow_streamorder = configget(
            self.config,
            "model",
            "wflow_streamorder",
            "staticmaps/wflow_streamorder.map",
        )

        # 2: Input base maps ########################################################
        subcatch = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_subcatch), 0.0, fail=True)
        )  # Determines the area of calculations (all cells > 0)
        subcatch = ifthen(subcatch > 0, subcatch)

        self.Altitude = self.wf_readmap(
            os.path.join(self.Dir, wflow_dem), 0.0, fail=True
        )  # * scalar(defined(subcatch)) # DEM
        self.TopoLdd = ldd(
            self.wf_readmap(os.path.join(self.Dir, wflow_ldd), 0.0, fail=True)
        )  # Local
        self.TopoId = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_subcatch), 0.0, fail=True)
        )  # area map
        self.River = cover(
            boolean(
                self.wf_readmap(os.path.join(self.Dir, wflow_river), 0.0, fail=True)
            ),
            0,
        )
        self.streamorder = self.wf_readmap(os.path.join(self.Dir, wflow_streamorder), 0.0, fail=True)
        # self.streamorder_remapped = self.wf_readmap(os.path.join(self.Dir, wflow_streamorder_mapped), 0.0, fail=True)
        
        self.RiverLength = cover(
            self.wf_readmap(os.path.join(self.Dir, wflow_riverlength), 0.0), 0.0
        )
        # Factor to multiply riverlength with (defaults to 1.0)
        self.RiverLengthFac = self.wf_readmap(
            os.path.join(self.Dir, wflow_riverlength_fact), 1.0
        )

        # read landuse and soilmap and make sure there are no missing points related to the
        # subcatchment map. Currently sets the lu and soil type  type to 1
        self.LandUse = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_landuse), 0.0, fail=True)
        )
        self.LandUse = cover(self.LandUse, ordinal(subcatch > 0))
        self.Soil = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_soil), 0.0, fail=True)
        )
        self.Soil = cover(self.Soil, ordinal(subcatch > 0))
        self.OutputLoc = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_gauges), 0.0, fail=True)
        )  # location of output gauge(s)
        self.InflowLoc = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_inflow), 0.0)
        )  # location abstractions/inflows.
        self.RiverWidth = self.wf_readmap(os.path.join(self.Dir, wflow_riverwidth), 0.0)
        # Experimental
        self.RunoffGenSigmaFunction = int(
            configget(self.config, "model", "RunoffGenSigmaFunction", "0")
        )
        self.SubCatchFlowOnly = int(
            configget(self.config, "model", "SubCatchFlowOnly", "0")
        )
        self.OutputId = ordinal(
            self.wf_readmap(os.path.join(self.Dir, wflow_subcatch), 0.0, fail=True)
        )  # location of subcatchment
        # Temperature correction poer cell to add

        self.TempCor = self.wf_readmap(
            self.Dir
            + "\\"
            + configget(
                self.config,
                "model",
                "TemperatureCorrectionMap",
                "staticmaps/wflow_tempcor.map",
            ),
            0.0,
        )

        self.ZeroMap = 0.0 * scalar(subcatch)  # map with only zero's

        # Set static initial values here #########################################
        self.pi = 3.1416
        self.e = 2.7183
        self.SScale = 100.0
        self.Latitude = ycoordinate(boolean(self.Altitude))
        self.Longitude = xcoordinate(boolean(self.Altitude))

        # Read parameters NEW Method
        self.logger.info("Linking parameters to landuse, catchment and soil...")
        self.wf_updateparameters()

        self.RunoffGeneratingGWPerc = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/RunoffGeneratingGWPerc.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.1,
        )

        if hasattr(self, "LAI"):
            # Sl must also be defined
            if not hasattr(self, "Sl"):
                logging.error(
                    "Sl (specific leaf storage) not defined! Needed becausee LAI is defined."
                )
                logging.error("Please add it to the modelparameters section. e.g.:")
                logging.error(
                    "Sl=inmaps/clim/LCtoSpecificLeafStorage.tbl,tbl,0.5,1,inmaps/clim/LC.map"
                )
            if not hasattr(self, "Kext"):
                logging.error(
                    "Kext (canopy extinction coefficient) not defined! Needed becausee LAI is defined."
                )
                logging.error("Please add it to the modelparameters section. e.g.:"
                    "Kext=inmaps/clim/LCtoExtinctionCoefficient.tbl,tbl,0.5,1,inmaps/clim/LC.map"
                )
            if not hasattr(self, "Swood"):
                logging.error(
                    "Swood wood (branches, trunks) canopy storage not defined! Needed becausee LAI is defined."
                )
                logging.error("Please add it to the modelparameters section. e.g.:")
                logging.error(
                    "Swood=inmaps/clim/LCtoBranchTrunkStorage.tbl,tbl,0.5,1,inmaps/clim/LC.map"
                )

            self.Cmax = self.Sl * self.LAI + self.Swood
            self.CanopyGapFraction = exp(-self.Kext * self.LAI)
            # TODO: Add MAXLAI and CWf lookup
        else:
            self.Cmax = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/MaxCanopyStorage.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                1.0,
            )
            self.CanopyGapFraction = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/CanopyGapFraction.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.1,
            )
            self.EoverR = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/EoverR.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.1,
            )

        if not hasattr(self, "DemandReturnFlowFraction"):
            self.DemandReturnFlowFraction = self.ZeroMap

        self.RootingDepth = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/RootingDepth.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            750.0,
        )  # rooting depth
        #: rootdistpar determine how roots are linked to water table.

        self.rootdistpar = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/rootdistpar.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            -8000,
        )  # rrootdistpar

        # Soil parameters
        # infiltration capacity if the soil [mm/day]
        self.InfiltCapSoil = (
            self.readtblDefault(
                self.Dir + "/" + self.intbl + "/InfiltCapSoil.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                100.0,
            )
            * self.timestepsecs
            / self.basetimestep
        )
        self.CapScale = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/CapScale.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            100.0,
        )  #

        # infiltration capacity of the compacted
        self.InfiltCapPath = (
            self.readtblDefault(
                self.Dir + "/" + self.intbl + "/InfiltCapPath.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                10.0,
            )
            * self.timestepsecs
            / self.basetimestep
        )
        self.MaxLeakage = (
            self.readtblDefault(
                self.Dir + "/" + self.intbl + "/MaxLeakage.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.0,
            )
            * self.timestepsecs
            / self.basetimestep
        )
        self.MaxPercolation = (
            self.readtblDefault(
                self.Dir + "/" + self.intbl + "/MaxPercolation.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.0,
            )
            * self.timestepsecs
            / self.basetimestep
        )

        # areas (paths) in [mm/day]
        # Fraction area with compacted soil (Paths etc.)
        self.PathFrac = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/PathFrac.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.01,
        )
        # thickness of the soil
        self.SoilThickness = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/SoilThickness.tbl",
            #self.Dir + "/" + self.intbl + "/SoilThickness_bylanduse.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            2000.0,
        )
        self.thetaR = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/thetaR.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.01,
        )
        self.thetaS = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/thetaS.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.6,
        )
        # minimum thickness of soild
        self.SoilMinThickness = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/SoilMinThickness.tbl",
            #self.Dir + "/" + self.intbl + "/SoilMinThickness.tbl",
            #self.Dir + "/" + self.intbl + "/SoilMinThickness_40mm.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            500.0,
        )

        # KsatVer = $2\inmaps\KsatVer.map
        self.KsatVer = (
            self.readtblDefault(
                self.Dir + "/" + self.intbl + "/KsatVer.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                3000.0,
            )
            * self.timestepsecs
            / self.basetimestep
        )
        self.MporeFrac = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/MporeFrac.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.0,
        )

        self.KsatHorFrac = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/KsatHorFrac.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            1.0,
        )

        # Check if we have irrigation areas
        tt = pcr2numpy(self.IrrigationAreas, 0.0)
        self.nrirri = tt.max()
        # Check of we have paddy irrigation areas
        tt = pcr2numpy(self.IrrigationPaddyAreas, 0.0)
        self.nrpaddyirri = tt.max()

        self.Beta = scalar(0.6)  # For sheetflow

        self.M = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/M.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            300.0,
        )  # Decay parameter in Topog_sbm
        self.N = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/N.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.072,
        )  # Manning overland flow
        if self.NRiverMethod == 1:
            self.NRiver = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/N_River.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.036,
            )  # Manning river
        if self.NRiverMethod == 2:
            self.NRiver = self.readtblFlexDefault(
                self.Dir + "/" + self.intbl + "/N_River.tbl", 0.036, wflow_streamorder
            )

        self.WaterFrac = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/WaterFrac.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            0.0,
        )  # Fraction Open water
        self.et_RefToPot = self.readtblDefault(
            self.Dir + "/" + self.intbl + "/et_reftopot.tbl",
            self.LandUse,
            subcatch,
            self.Soil,
            1.0,
        )  # Fraction Open water

        if self.modelSnow:
            # HBV Snow parameters
            # critical temperature for snowmelt and refreezing:  TTI= 1.000
            self.TTI = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/TTI.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                1.0,
            )
            # TT = -1.41934 # defines interval in which precipitation falls as rainfall and snowfall
            self.TT = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/TT.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                -1.41934,
            )
            self.TTM = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/TTM.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                -1.41934,
            )
            # Cfmax = 3.75653 # meltconstant in temperature-index
            self.Cfmax = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/Cfmax.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                3.75653,
            )
            # WHC= 0.10000        # fraction of Snowvolume that can store water
            self.WHC = self.readtblDefault(
                self.Dir + "/" + self.intbl + "/WHC.tbl",
                self.LandUse,
                subcatch,
                self.Soil,
                0.1,
            )
            # Wigmosta, M. S., L. J. Lane, J. D. Tagestad, and A. M. Coleman (2009).
            self.w_soil = (
                self.readtblDefault(
                    self.Dir + "/" + self.intbl + "/w_soil.tbl",
                    self.LandUse,
                    subcatch,
                    self.Soil,
                    0.9 * 3.0 / 24.0,
                )
                * self.timestepsecs
                / self.basetimestep
            )

            self.cf_soil = min(
                0.99,
                self.readtblDefault(
                    self.Dir + "/" + self.intbl + "/cf_soil.tbl",
                    self.LandUse,
                    subcatch,
                    self.Soil,
                    0.038,
                ),
            )  # Ksat reduction factor fro frozen soi
            # We are modelling gletchers

        # Determine real slope and cell length

        self.xl, self.yl, self.reallength = pcrut.detRealCellLength(
            self.ZeroMap, sizeinmetres
        )
        self.Slope = slope(self.Altitude)
        # self.Slope=ifthen(boolean(self.TopoId),max(0.001,self.Slope*celllength()/self.reallength))
        self.Slope = max(0.00001, self.Slope * celllength() / self.reallength)
        Terrain_angle = scalar(atan(self.Slope))

        self.N = ifthenelse(self.River, self.NRiver, self.N)
        
        if hasattr(self, "ReserVoirSimpleLocs") or hasattr(
            self, "ReserVoirComplexLocs"
        ):
            self.ReservoirLocs = self.ZeroMap
            self.filter_P_PET = self.ZeroMap + 1.0

        if hasattr(self, "config_reservoir_file"):
            print("                       YES, THE RESERVOIR IS IN THE HOUSE !!!                       ")
            #Check if we have simple and or complex reservoirs
            #self.ReservoirSimpleLocs = nominal(self.ReservoirSimpleLocs)
#            self.reservoir_IDs = pd.read_table(os.path.join(self.Dir, self.reservoir_txtfile), squeeze=True)
#            all_reservoirLocs_df = pd.read_table(os.path.join(self.Dir, self.reservoir_coords), index_col='damID')
#            self.reservoirLocs_df = all_reservoirLocs_df[all_reservoirLocs_df.index.isin(self.reservoir_IDs)]
#            reservoirLocs_X = numpy.array(list(self.reservoirLocs_df['X']))
#            reservoirLocs_Y = numpy.array(list(self.reservoirLocs_df['Y']))
#            print(reservoirLocs_X, type(reservoirLocs_X))
#            #print(type(numpy.array(self.reservoir_IDs)[0]))
#            self.ReservoirLocs_map = reservoirs_to_map(self.streamorder, reservoirLocs_X, reservoirLocs_Y, 0.5, numpy.array(self.reservoir_IDs), self.Dir, self.coords_system)
#            #for n in range(0, reservoirLocs_X.size):
#            #    self.ReservoirLocs_map = self.ReservoirLocs_map + numpy2pcr(Scalar, ((col_ * row_) * (self.reservoir_IDs[n])), numpy.nan)
#            report(self.ReservoirLocs_map, os.path.join(self.Dir, "reservoirs/ReservoirLocs_map___.map"))
#            ds = gdal.Open(os.path.join(self.Dir, "reservoirs/ReservoirLocs_map___.map"),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
            self.ReservoirLocs_arr = pcr2numpy(self.ReservoirLocs_map, numpy.nan)
            self.ReservoirLocs_arr = self.ReservoirLocs_arr[~numpy.isnan(self.ReservoirLocs_arr)]
            self.ReservoirLocs_arr = self.ReservoirLocs_arr[~(self.ReservoirLocs_arr<=0)]
            # reservoirs are and MUST BE in the order of the map-wise array, left to right, top to bottom, NOT in ascending damID order!
            print("\n\nThese are the reservoirs: {}\n\n".format(self.ReservoirLocs_arr))  
            #create a dataframe with reservoir locations and their values read from each files
            self.Reservoir_df = pd.read_table(os.path.join(self.Dir, self.reservoir_charact), index_col=['damID', 'depth'])
            self.Reservoir_df['endTerms'] = 2*self.Reservoir_df['storage']/self.timestepsecs + self.Reservoir_df['outflow_rect']
            self.Reservoir_df.to_csv(os.path.join(self.SaveDir, "reservoirs/all_reservoirs_df.txt"), sep='\t')
            #self.ReservoirSimpleAreas = nominal(self.ReservoirSimpleAreas)
            tt_simple = pcr2numpy(self.ReservoirLocs_map, 0.0)
            self.nrresSimple = numpy.size(numpy.where(tt_simple > 0.0)[0])
#            self.ReserVoirLocs = self.ReserVoirLocs + cover(scalar(self.ReservoirLocs_map), 0.0)
#            areamap = self.reallength * self.reallength
#            res_area = areatotal(spatial(areamap), self.ReservoirSimpleAreas)
#
#            resarea_pnt = ifthen(boolean(self.ReserVoirSimpleLocs), res_area)
#            self.ResSimpleArea = ifthenelse(
#                cover(self.ResSimpleArea, scalar(0.0)) > 0,
#                self.ResSimpleArea,
#                cover(resarea_pnt, scalar(0.0)),
#            )
#            self.filter_P_PET = ifthenelse(
#                boolean(cover(res_area, scalar(0.0))), res_area * 0.0, self.filter_P_PET
#            )
        else:
            self.nrresSimple = 0
            print("                       NO, THERE ARE NO RESERVOIR !!!                       ")

        if hasattr(self, "ReserVoirComplexLocs"):
            tt_complex = pcr2numpy(self.ReserVoirComplexLocs, 0.0)
            self.nrresComplex = tt_complex.max()
            self.ReserVoirLocs = self.ReserVoirLocs + cover(
                scalar(self.ReserVoirComplexLocs)
            )
            res_area = cover(scalar(self.ReservoirComplexAreas), 0.0)
            self.filter_P_PET = ifthenelse(
                res_area > 0, res_area * 0.0, self.filter_P_PET
            )

            # read files
            self.sh = {}
            res_ids = ifthen(self.ResStorFunc == 2, self.ReserVoirComplexLocs)
            np_res_ids = pcr2numpy(res_ids, 0)
            np_res_ids_u = np.unique(np_res_ids[nonzero(np_res_ids)])
            if np.size(np_res_ids_u) > 0:
                for item in nditer(np_res_ids_u):
                    self.sh[int(item)] = loadtxt(
                        self.Dir
                        + "/"
                        + self.intbl
                        + "/Reservoir_SH_"
                        + str(item)
                        + ".tbl"
                    )
            self.hq = {}
            res_ids = ifthen(self.ResOutflowFunc == 1, self.ReserVoirComplexLocs)
            np_res_ids = pcr2numpy(res_ids, 0)
            np_res_ids_u = np.unique(np_res_ids[nonzero(np_res_ids)])
            if size(np_res_ids_u) > 0:
                for item in nditer(np_res_ids_u):
                    self.hq[int(item)] = loadtxt(
                        self.Dir
                        + "/"
                        + self.intbl
                        + "/Reservoir_HQ_"
                        + str(item)
                        + ".tbl",
                        skiprows=3,
                    )

        else:
            self.nrresComplex = 0

        if (self.nrresSimple + self.nrresComplex) > 0:
            self.ReservoirLocs = ordinal(self.ReservoirLocs_map)
            self.logger.info(
                "A total of "
                + str(self.nrresSimple)
                + " simple reservoirs and "
                + str(self.nrresComplex)
                + " complex reservoirs found."
            )
            self.ReservoirDownstreamLocs = downstream(self.TopoLdd, self.ReservoirLocs)
            self.TopoLddOrg = self.TopoLdd
#            report(self.TopoLddOrg, os.path.join(self.Dir, self.runId, "TopoLddOrg.map"))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "TopoLddOrg.map"),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
            report(cover(ifthen(self.ReservoirLocs>0, ldd(5)), self.TopoLddOrg), os.path.join(self.Dir, self.runId, "coverLdd.map"))
            ds = gdal.Open(os.path.join(self.Dir, self.runId, "coverLdd.map"),GA_Update)
            ds.SetProjection(self.coords_system)
            ds = None
            self.TopoLdd = lddrepair(
                cover(ifthen(self.ReservoirLocs>0, ldd(5)), self.TopoLddOrg)
            )

            #tt_filter = pcr2numpy(self.filter_P_PET, 1.0)
            #self.filterResArea = tt_filter.min()

        # Determine river width from DEM, upstream area and yearly average discharge
        # Scale yearly average Q at outlet with upstream are to get Q over whole catchment
        # Alf ranges from 5 to > 60. 5 for hardrock. large values for sediments
        # "Noah J. Finnegan et al 2005 Controls on the channel width of rivers:
        # Implications for modeling fluvial incision of bedrock"

        upstr = catchmenttotal(1, self.TopoLdd)
        Qscale = upstr / mapmaximum(upstr) * Qmax
        W = (
            (alf * (alf + 2.0) ** (0.6666666667)) ** (0.375)
            * Qscale ** (0.375)
            * (max(0.0001, windowaverage(self.Slope, celllength() * 4.0))) ** (-0.1875)
            * self.N ** (0.375)
        )
        # Use supplied riverwidth if possible, else calulate
        self.RiverWidth = ifthenelse(self.RiverWidth <= 0.0, W, self.RiverWidth)

        # Only allow reinfiltration in river cells by default

        if not hasattr(self, "MaxReinfilt"):
            self.MaxReinfilt = ifthenelse(
                self.River, self.ZeroMap + 999.0, self.ZeroMap
            )

        # soil thickness based on topographical index (see Environmental modelling: finding simplicity in complexity)
        # 1: calculate wetness index
        # 2: Scale the capacity (now actually a max capacity) based on the index, also apply a minmum capacity
        WI = ln(
            accuflux(self.TopoLdd, 1) / self.Slope
        )  # Topographical wetnesss. Scale WI by zone/subcatchment assuming these ara also geological units
        WIMax = areamaximum(WI, self.TopoId) * WIMaxScale
        self.SoilThickness = max(
            min(self.SoilThickness, (WI / WIMax) * self.SoilThickness),
            self.SoilMinThickness,
        )

        self.SoilWaterCapacity = self.SoilThickness * (self.thetaS - self.thetaR)

        # determine number of layers based on total soil thickness
        # assign thickness, unsaturated water store and transfer to these layers (initializing)
        UStoreLayerThickness = configget(
            self.config, "model", "UStoreLayerThickness", "0"
        )
        if UStoreLayerThickness != "0":
            self.USatLayers = len(UStoreLayerThickness.split(","))
            self.maxLayers = self.USatLayers + 1
        else:
            UStoreLayerThickness = self.SoilThickness
            self.USatLayers = 1
            self.maxLayers = self.USatLayers

        self.UStoreLayerThickness = []
        self.UStoreLayerDepth = []
        self.T = []
        self.maskLayer = []

        self.SumThickness = self.ZeroMap
        self.nrLayersMap = self.ZeroMap

        for n in np.arange(0, self.maxLayers):
            self.SumLayer = self.SumThickness
            if self.USatLayers > 1 and n < self.USatLayers:
                UstoreThick_temp = (
                    float(UStoreLayerThickness.split(",")[n]) + self.ZeroMap
                )
                UstoreThick = min(
                    UstoreThick_temp, max(self.SoilThickness - self.SumLayer, 0.0)
                )
            else:
                UstoreThick_temp = mapmaximum(self.SoilThickness) - self.SumLayer
                UstoreThick = min(
                    UstoreThick_temp, max(self.SoilThickness - self.SumLayer, 0.0)
                )

            self.SumThickness = UstoreThick_temp + self.SumThickness
            self.nrLayersMap = ifthenelse(
                (self.SoilThickness >= self.SumThickness)
                | (self.SoilThickness - self.SumLayer > self.ZeroMap),
                self.nrLayersMap + 1,
                self.nrLayersMap,
            )

            self.UStoreLayerThickness.append(
                ifthenelse(
                    (self.SumThickness <= self.SoilThickness)
                    | (self.SoilThickness - self.SumLayer > self.ZeroMap),
                    UstoreThick,
                    0.0,
                )
            )
            self.UStoreLayerDepth.append(
                ifthen(
                    (self.SumThickness <= self.SoilThickness)
                    | (self.SoilThickness - self.SumLayer > self.ZeroMap),
                    self.SoilThickness * 0.0,
                )
            )
            self.T.append(
                ifthen(
                    (self.SumThickness <= self.SoilThickness)
                    | (self.SoilThickness - self.SumLayer > self.ZeroMap),
                    self.SoilThickness * 0.0,
                )
            )
            self.maskLayer.append(
                ifthen(
                    (self.SumThickness <= self.SoilThickness)
                    | (self.SoilThickness - self.SumLayer > self.ZeroMap),
                    self.SoilThickness * 0.0,
                )
            )

        self.KsatVerFrac = []
        self.c = []
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            self.KsatVerFrac.append(
                self.readtblLayersDefault(
                    self.Dir + "/" + self.intbl + "/KsatVerFrac.tbl",
                    self.LandUse,
                    subcatch,
                    self.Soil,
                    n,
                    1.0,
                )
            )
            self.c.append(
                self.readtblLayersDefault(
                    self.Dir + "/" + self.intbl + "/c.tbl",
                    self.LandUse,
                    subcatch,
                    self.Soil,
                    n,
                    10.0,
                )
            )

        # limit roots to top 99% of first zone
        self.RootingDepth = min(self.SoilThickness * 0.99, self.RootingDepth)

        # subgrid runoff generation, determine CC (sharpness of S-Curve) for upper
        # en lower part and take average
        self.DemMax = readmap(self.Dir + "/staticmaps/step2/wflow_demmax")
        self.DrainageBase = readmap(self.Dir + "/staticmaps/step2/wflow_demmin")
        self.CClow = min(
            100.0, -ln(1.0 / 0.1 - 1) / min(-0.1, self.DrainageBase - self.Altitude)
        )
        self.CCup = min(
            100.0, -ln(1.0 / 0.1 - 1) / min(-0.1, self.Altitude - self.DemMax)
        )
        self.CC = (self.CClow + self.CCup) * 0.5

        # Which columns/gauges to use/ignore in updating
        self.UpdateMap = self.ZeroMap

        if self.updating:
            _tmp = pcr2numpy(self.OutputLoc, 0.0)
            gaugear = _tmp
            touse = numpy.zeros(gaugear.shape, dtype="int")

            for thecol in updateCols:
                idx = (gaugear == thecol).nonzero()
                touse[idx] = thecol

            self.UpdateMap = numpy2pcr(Nominal, touse, 0.0)
            # Calculate distance to updating points (upstream) annd use to scale the correction
            # ldddist returns zero for cell at the gauges so add 1.0 tp result
            self.DistToUpdPt = cover(
                min(
                    ldddist(self.TopoLdd, boolean(cover(self.UpdateMap, 0)), 1)
                    * self.reallength
                    / celllength(),
                    self.UpdMaxDist,
                ),
                self.UpdMaxDist,
            )

        # Initializing of variables
        self.logger.info("Initializing of model variables..")
        self.TopoLdd = lddmask(self.TopoLdd, boolean(self.TopoId))
        catchmentcells = maptotal(scalar(self.TopoId))

        # Limit lateral flow per subcatchment (make pits at all subcatch boundaries)
        # This is very handy for Ribasim etc...
        if self.SubCatchFlowOnly > 0:
            self.logger.info("Creating subcatchment-only drainage network (ldd)")
            ds = downstream(self.TopoLdd, self.TopoId)
            usid = ifthenelse(ds != self.TopoId, self.TopoId, 0)
            self.TopoLdd = lddrepair(ifthenelse(boolean(usid), ldd(5), self.TopoLdd))

        # Used to seperate output per LandUse/management classes
        OutZones = self.LandUse

        self.QMMConv = self.timestepsecs / (
            self.reallength * self.reallength * 0.001
        )  # m3/s --> actial mm of water over the cell
        # self.QMMConvUp = 1000.0 * self.timestepsecs / ( catchmenttotal(cover(1.0), self.TopoLdd) * self.reallength * self.reallength)  #m3/s --> mm over upstreams
        temp = (
            catchmenttotal(cover(1.0), self.TopoLdd)
            * self.reallength
            * 0.001
            * 0.001
            * self.reallength
        )
        self.QMMConvUp = cover(self.timestepsecs * 0.001) / temp
        self.ToCubic = (
            self.reallength * self.reallength * 0.001
        ) / self.timestepsecs  # m3/s
        self.KinWaveVolume = self.ZeroMap
        self.OldKinWaveVolume = self.ZeroMap
        self.OldInflow = self.ZeroMap
        self.sumprecip = self.ZeroMap  # accumulated rainfall for water balance
        self.sumevap = self.ZeroMap  # accumulated evaporation for water balance
        self.sumrunoff = self.ZeroMap  # accumulated runoff for water balance
        self.sumint = self.ZeroMap  # accumulated interception for water balance
        self.sumleakage = self.ZeroMap
        self.CumReinfilt = self.ZeroMap
        self.sumoutflow = self.ZeroMap
        self.sumsnowmelt = self.ZeroMap
        self.CumRad = self.ZeroMap
        self.SnowMelt = self.ZeroMap
        self.CumPrec = self.ZeroMap
        self.CumInwaterMM = self.ZeroMap
        self.CumInfiltExcess = self.ZeroMap
        self.CumExfiltWater = self.ZeroMap
        self.CumSurfaceWater = self.ZeroMap
        self.watbal = self.ZeroMap
        self.CumEvap = self.ZeroMap
        self.CumPotenEvap = self.ZeroMap
        self.CumPotenTrans = self.ZeroMap
        self.CumInt = self.ZeroMap
        self.CumRad = self.ZeroMap
        self.CumLeakage = self.ZeroMap
        self.CumPrecPol = self.ZeroMap
        self.SatWaterFlux = self.ZeroMap
        self.SumCellWatBal = self.ZeroMap
        self.PathInfiltExceeded = self.ZeroMap
        self.SoilInfiltExceeded = self.ZeroMap
        self.CumOutFlow = self.ZeroMap
        self.CumCellInFlow = self.ZeroMap
        self.CumIF = self.ZeroMap
        self.CumActInfilt = self.ZeroMap
        self.IRSupplymm = self.ZeroMap
        self.Aspect = scalar(aspect(self.Altitude))  # aspect [deg]
        self.Aspect = ifthenelse(self.Aspect <= 0.0, scalar(0.001), self.Aspect)
        # On Flat areas the Aspect function fails, fill in with average...
        self.Aspect = ifthenelse(
            defined(self.Aspect), self.Aspect, areaaverage(self.Aspect, self.TopoId)
        )
        # Set DCL to riverlength if that is longer that the basic length calculated from grid
        drainlength = detdrainlength(self.TopoLdd, self.xl, self.yl)

        # Multiply with Factor (taken from upscaling operation, defaults to 1.0 if no map is supplied
        self.DCL = drainlength * max(1.0, self.RiverLengthFac)     

        self.DCL = max(self.DCL, self.RiverLength)  # m
        
        # water depth (m)
        # set width for kinematic wave to cell width for all cells
        self.Bw = detdrainwidth(self.TopoLdd, self.xl, self.yl)
        # However, in the main river we have real flow so set the width to the
        # width of the river

        self.Bw = ifthenelse(self.River, self.RiverWidth, self.Bw)

        # Add rivers to the WaterFrac, but check with waterfrac map and correct
        self.RiverFrac = min(
            1.0,
            ifthenelse(
                self.River, (self.RiverWidth * self.DCL) / (self.xl * self.yl), 0
            ),
        )
        self.WaterFrac = min(1.0, self.WaterFrac + self.RiverFrac)

        # term for Alpha
        # Correct slope for extra length of the river in a gridcel
        riverslopecor = drainlength / self.DCL
        # report(riverslopecor,"cor.map")
        # report(self.Slope * riverslopecor,"slope.map")
        self.AlpTerm = pow((self.N / (sqrt(self.Slope * riverslopecor))), self.Beta)
        # power for Alpha
        self.AlpPow = (2.0 / 3.0) * self.Beta
        # initial approximation for Alpha
        # calculate catchmentsize
        self.upsize = catchmenttotal(self.xl * self.yl, self.TopoLdd)
        self.csize = areamaximum(self.upsize, self.TopoId)
        self.wf_multparameters()
        # Save some summary maps
        self.logger.info("Saving summary maps...")

        # self.IF = self.ZeroMap
        self.logger.info("End of initial section")

    def default_summarymaps(self):
        """
          Returns a list of default summary-maps at the end of a run.
          This is model specific. You can also add them to the [summary]section of the ini file but stuff
          you think is crucial to the model should be listed here
          """
        lst = [
            "self.RiverWidth",
            "self.Cmax",
            "self.csize",
            "self.upsize",
            "self.EoverR",
            "self.RootingDepth",
            "self.CanopyGapFraction",
            "self.InfiltCapSoil",
            "self.InfiltCapPath",
            "self.PathFrac",
            "self.thetaR",
            "self.thetaS",
            "self.SoilMinThickness",
            "self.SoilThickness",
            "self.nrLayersMap",
            "self.KsatVer",
            "self.M",
            "self.SoilWaterCapacity",
            "self.et_RefToPot",
            "self.Slope",
            "self.CC",
            "self.N",
            "self.RiverFrac",
            "self.WaterFrac",
            "self.xl",
            "self.yl",
            "self.reallength",
            "self.DCL",
            "self.Bw",
            "self.PathInfiltExceeded",
            "self.SoilInfiltExceeded",
        ]

        return lst

    def resume(self):

        if self.reinit == 1:
            self.logger.info("Setting initial conditions to default")
            self.SatWaterDepth = self.SoilWaterCapacity * 0.85

            # for n in np.arange(0,self.nrLayers):
            #    self.UStoreLayerDepth[n] = self.ZeroMap
            # TODO: move UStoreLayerDepth from initial to here

            self.WaterLevel = self.ZeroMap
            self.SurfaceRunoff = self.ZeroMap
            self.Snow = self.ZeroMap
            self.SnowWater = self.ZeroMap
            self.TSoil = self.ZeroMap + 10.0
            self.CanopyStorage = self.ZeroMap
            #if hasattr(self, "ReserVoirSimpleLocs"):
            if hasattr(self, "config_reservoir_file") and self.nrresSimple > 0:
                #self.ReservoirVolume = self.ResMaxVolume * self.ResTargetFullFrac
                self.ReservoirVolume = ifthen(self.ReservoirLocs_map>0, self.ZeroMap)#self.ResMaxVolume * self.ResInitialFullFrac
                self.OutflowSR = ifthen(self.ReservoirLocs_map>0, self.ZeroMap)
#                report(self.ReservoirVolume, os.path.join(self.Dir, "init/resvol.map"))
#                ds = gdal.Open(os.path.join(self.Dir, "init/resvol.map"),GA_Update)
#                ds.SetProjection(self.coords_system)
#                ds = None
#                report(self.OutflowSR, os.path.join(self.Dir, "init/outflow.map"))
#                ds = gdal.Open(os.path.join(self.Dir, "init/outflow.map"),GA_Update)
#                ds.SetProjection(self.coords_system)
#                ds = None
                
            if hasattr(self, "ReserVoirComplexLocs"):
                self.ReservoirWaterLevel = cover(0.0)
            if hasattr(self, "GlacierFrac"):
                self.GlacierStore = self.wf_readmap(
                    os.path.join(self.Dir, "staticmaps", "GlacierStore.map"),
                    55.0 * 1000,
                )
            if self.nrpaddyirri > 0:
                self.PondingDepth = self.ZeroMap

        else:
            self.logger.info("Setting initial conditions from state files")
            self.wf_resume(os.path.join(self.Dir, "instate"))

        P = self.Bw + (2.0 * self.WaterLevel)
        self.Alpha = self.AlpTerm * pow(P, self.AlpPow)
        self.OldSurfaceRunoff = self.SurfaceRunoff

        self.SurfaceRunoffMM = self.SurfaceRunoff * self.QMMConv
        # Determine initial kinematic wave volume
        self.KinWaveVolume = self.WaterLevel * self.Bw * self.DCL
        self.OldKinWaveVolume = self.KinWaveVolume

        self.QCatchmentMM = self.SurfaceRunoff * self.QMMConvUp
        self.InitialStorage = (
            self.SatWaterDepth
            + sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)
            + self.CanopyStorage
        )
        self.CellStorage = self.SatWaterDepth + sum_list_cover(
            self.UStoreLayerDepth, self.ZeroMap
        )

        # Determine actual water depth
        self.zi = max(
            0.0, self.SoilThickness - self.SatWaterDepth / (self.thetaS - self.thetaR)
        )
        # TOPOG_SBM type soil stuff
        self.f = (self.thetaS - self.thetaR) / self.M
        # NOTE:: This line used to be in the initial section. As a result
        # simulations will now be different as it used to be before
        # the rescaling of the FirstZoneThickness
        self.GWScale = (
            (self.DemMax - self.DrainageBase)
            / self.SoilThickness
            / self.RunoffGeneratingGWPerc
        )

    def dynamic(self):
        """
        Stuf that is done for each timestep of the model

        Below a list of variables that can be save to disk as maps or as
        timeseries (see ini file for syntax):

        Dynamic variables
        ~~~~~~~~~~~~~~~~~

        All these can be saved per timestep if needed (see the config file [outputmaps] section).

        :var self.Precipitation: Gross precipitation [mm]
        :var self.Temperature: Air temperature [oC]
        :var self.PotenEvap: Potential evapotranspiration [mm]
        :var self.PotTransSoil: Potential Transpiration/Openwater and soil evap (after subtracting Interception from PotenEvap) [mm]
        :var self.Transpiration: plant/tree transpiration [mm]
        :var self.ActEvapOpenWater: actual open water evaporation [mm]
        :var self.soilevap: base soil evaporation [mm]
        :var self.Interception: Actual rainfall interception [mm]
        :var self.ActEvap: Actual evaporation (transpiration + Soil evap + open water evap) [mm]
        :var self.SurfaceRunoff: Surface runoff in the kinematic wave [m^3/s]
        :var self.SurfaceRunoffDyn: Surface runoff in the dyn-wave resrvoir [m^3/s]
        :var self.SurfaceRunoffCatchmentMM: Surface runoff in the dyn-wave reservoir expressed in mm over the upstream (catchment) area
        :var self.WaterLevelDyn: Water level in the dyn-wave resrvoir [m^]
        :var self.ActEvap: Actual EvapoTranspiration [mm] (minus interception losses)
        :var self.ExcessWater: Water that cannot infiltrate due to saturated soil [mm]
        :var self.InfiltExcess: Infiltration excess water [mm]
        :var self.WaterLevel: Water level in the kinematic wave [m] (above the bottom)
        :var self.ActInfilt: Actual infiltration into the unsaturated zone [mm]
        :var self.CanopyStorage: actual canopystorage (only for subdaily timesteps) [mm]
        :var self.SatWaterDepth: Amount of water in the saturated store [mm]
        :var self.UStoreDepth: Amount of water in the unsaturated store [mm]
        :var self.zi: depth of the water table in mm below the surface [mm]
        :var self.Snow: Snow depth [mm]
        :var self.SnowWater: water content of the snow [mm]
        :var self.TSoil: Top soil temperature [oC]
        :var self.SatWaterDepth: amount of available water in the saturated part of the soil [mm]
        :var self.UStoreDepth: amount of available water in the unsaturated zone [mm]
        :var self.Transfer: downward flux from unsaturated to saturated zone [mm]
        :var self.CapFlux: capilary flux from saturated to unsaturated zone [mm]
        :var self.CanopyStorage: Amount of water on the Canopy [mm]
        :var self.RunoffCoeff: Runoff coefficient (Q/P) for each cell taking into account the whole upstream area [-]
        :var self.SurfaceWaterSupply: the negative Inflow (water demand) that could be met from the surfacewater [m^3/s]


        Static variables
        ~~~~~~~~~~~~~~~~

        :var self.Altitude: The altitude of each cell [m]
        :var self.Bw: Width of the river [m]
        :var self.River: booolean map indicating the presence of a river [-]
        :var self.DLC: length of the river within a cell [m]
        :var self.ToCubic: Mutiplier to convert mm to m^3/s for fluxes
        """

        # Read forcing data and dynamic parameters

        self.wf_updateparameters()
        self.Precipitation = max(0.0, self.Precipitation)

        # NB This may interfere with lintul link
        if hasattr(self, "LAI"):
            # Sl must also be defined
            ##TODO: add MAXLAI and CWf
            self.Cmax = self.Sl * self.LAI + self.Swood
            self.CanopyGapFraction = exp(-self.Kext * self.LAI)
            self.Ewet = (1 - exp(-self.Kext * self.LAI)) * self.PotenEvap
            self.EoverR = ifthenelse(
                self.Precipitation > 0.0,
                min(0.25, cover(self.Ewet / max(0.0001, self.Precipitation), 0.0)),
                0.0,
            )
            if hasattr(self, "MAXLAI") and hasattr(self, "CWf"):
                # Adjust rootinggdepth
                self.ActRootingDepth = self.CWf * (
                    self.RootingDepth * self.LAI / max(0.001, self.MAXLAI)
                ) + ((1 - self.CWf) * self.RootingDepth)
            else:
                self.ActRootingDepth = self.RootingDepth
        else:
            self.ActRootingDepth = self.RootingDepth

        # Apply forcing data corrections
        self.PotenEvap = self.PotenEvap * self.et_RefToPot
        if self.modelSnow:
            self.Temperature = self.Temperature + self.TempCor

        self.wf_multparameters()

#        if (self.nrresSimple + self.nrresComplex) > 0 and self.filterResArea == 0:
#            self.ReserVoirPotEvap = self.PotenEvap
#            self.ReserVoirPrecip = self.Precipitation
#
#            self.PotenEvap = self.filter_P_PET * self.PotenEvap
#            self.Precipitation = self.filter_P_PET * self.Precipitation

        self.OrgStorage = (
            sum_list_cover(self.UStoreLayerDepth, self.ZeroMap) + self.SatWaterDepth
        )
        self.OldCanopyStorage = self.CanopyStorage
        if self.nrpaddyirri > 0:
            self.OldPondingDepth = self.PondingDepth
        self.PotEvap = self.PotenEvap  #

        if self.modelSnow:
            self.TSoil = self.TSoil + self.w_soil * (self.Temperature - self.TSoil)
            # return Snow,SnowWater,SnowMelt,RainFall
            self.Snow, self.SnowWater, self.SnowMelt, self.PrecipitationPlusMelt, self.SnowFall = SnowPackHBV(
                self.Snow,
                self.SnowWater,
                self.Precipitation,
                self.Temperature,
                self.TTI,
                self.TT,
                self.TTM,
                self.Cfmax,
                self.WHC,
            )
            MaxSnowPack = 10000.0
            if self.MassWasting:
                # Masswasting of dry snow
                # 5.67 = tan 80 graden
                SnowFluxFrac = min(0.5, self.Slope / 5.67) * min(
                    1.0, self.Snow / MaxSnowPack
                )
                MaxFlux = SnowFluxFrac * self.Snow
                self.Snow = accucapacitystate(self.TopoLdd, self.Snow, MaxFlux)
            else:
                SnowFluxFrac = self.ZeroMap
                MaxFlux = self.ZeroMap

            self.SnowCover = ifthenelse(self.Snow > 0, scalar(1), scalar(0))
            self.NrCell = areatotal(self.SnowCover, self.TopoId)

            if hasattr(self, "GlacierFrac"):
                """
                Run Glacier module and add the snowpack on-top of it.
                Snow becomes ice when pressure is about 830 k/m^2, e.g 8300 mm
                If below that a max amount of 2mm/day can be converted to glacier-ice
                """
                # TODO: document glacier module
                self.snowdist = sCurve(self.Snow, a=8300.0, c=0.06)
                self.Snow2Glacier = ifthenelse(
                    self.Snow > 8300, self.snowdist * (self.Snow - 8300), self.ZeroMap
                )

                self.Snow2Glacier = ifthenelse(
                    self.GlacierFrac > 0.0, self.Snow2Glacier, self.ZeroMap
                )
                # Max conversion to 8mm/day
                self.Snow2Glacier = (
                    min(self.Snow2Glacier, 8.0) * self.timestepsecs / self.basetimestep
                )

                self.Snow = self.Snow - (self.Snow2Glacier * self.GlacierFrac)

                self.GlacierStore, self.GlacierMelt = GlacierMelt(
                    self.GlacierStore + self.Snow2Glacier,
                    self.Snow,
                    self.Temperature,
                    self.G_TT,
                    self.G_Cfmax,
                )
                # Convert to mm per grid cell and add to snowmelt
                self.GlacierMelt = self.GlacierMelt * self.GlacierFrac
                self.PrecipitationPlusMelt = (
                    self.PrecipitationPlusMelt + self.GlacierMelt
                )
        else:
            self.PrecipitationPlusMelt = self.Precipitation

        ##########################################################################
        # Interception according to a modified Gash model
        ##########################################################################
        if self.timestepsecs >= (23 * 3600):
            self.ThroughFall, self.Interception, self.StemFlow, self.CanopyStorage = rainfall_interception_gash(
                self.Cmax,
                self.EoverR,
                self.CanopyGapFraction,
                self.PrecipitationPlusMelt,
                self.CanopyStorage,
                maxevap=self.PotEvap,
            )

            self.PotTransSoil = cover(
                max(0.0, self.PotEvap - self.Interception), 0.0
            )  # now in mm

        else:
            NetInterception, self.ThroughFall, self.StemFlow, LeftOver, Interception, self.CanopyStorage = rainfall_interception_modrut(
                self.PrecipitationPlusMelt,
                self.PotEvap,
                self.CanopyStorage,
                self.CanopyGapFraction,
                self.Cmax,
            )
            self.PotTransSoil = cover(max(0.0, LeftOver), 0.0)  # now in mm
            self.Interception = NetInterception

        # Start with the soil calculations
        # --------------------------------
        # Code to be able to force zi from the outside
        #
        self.SatWaterDepth = (self.thetaS - self.thetaR) * (
            self.SoilThickness - self.zi
        )

        self.AvailableForInfiltration = (
            self.ThroughFall + self.StemFlow + self.IRSupplymm
        )
        self.oldIRSupplymm = self.IRSupplymm

        UStoreCapacity = (
            self.SoilWaterCapacity
            - self.SatWaterDepth
            - sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)
        )

        # Runoff from water bodies and river network
        self.RunoffOpenWater = (
            min(1.0, self.RiverFrac + self.WaterFrac) * self.AvailableForInfiltration
        )
        # self.RunoffOpenWater = self.ZeroMap
        self.AvailableForInfiltration = (
            self.AvailableForInfiltration - self.RunoffOpenWater
        )

        if self.RunoffGenSigmaFunction:
            self.AbsoluteGW = self.DemMax - (self.zi * self.GWScale)
            # Determine saturated fraction of cell
            self.SubCellFrac = sCurve(self.AbsoluteGW, c=self.CC, a=self.Altitude + 1.0)
            # Make sure total of SubCellFRac + WaterFRac + RiverFrac <=1 to avoid double counting
            Frac_correction = ifthenelse(
                (self.SubCellFrac + self.RiverFrac + self.WaterFrac) > 1.0,
                self.SubCellFrac + self.RiverFrac + self.WaterFrac - 1.0,
                0.0,
            )
            self.SubCellRunoff = (
                self.SubCellFrac - Frac_correction
            ) * self.AvailableForInfiltration
            self.SubCellGWRunoff = min(
                self.SubCellFrac * self.SatWaterDepth,
                max(
                    0.0,
                    self.SubCellFrac
                    * self.Slope
                    * self.KsatVer
                    * self.KsatHorFrac
                    * exp(-self.f * self.zi),
                ),
            )
            self.SatWaterDepth = self.SatWaterDepth - self.SubCellGWRunoff
            self.AvailableForInfiltration = (
                self.AvailableForInfiltration - self.SubCellRunoff
            )
        else:
            self.AbsoluteGW = self.DemMax - (self.zi * self.GWScale)
            self.SubCellFrac = spatial(scalar(0.0))
            self.SubCellGWRunoff = spatial(scalar(0.0))
            self.SubCellRunoff = spatial(scalar(0.0))

        # First determine if the soil infiltration capacity can deal with the
        # amount of water
        # split between infiltration in undisturbed soil and compacted areas (paths)
        SoilInf = self.AvailableForInfiltration * (1 - self.PathFrac)
        PathInf = self.AvailableForInfiltration * self.PathFrac
        if self.modelSnow:
            bb = 1.0 / (1.0 - self.cf_soil)
            soilInfRedu = sCurve(self.TSoil, a=self.ZeroMap, b=bb, c=8.0) + self.cf_soil
        else:
            soilInfRedu = 1.0
        MaxInfiltSoil = min(self.InfiltCapSoil * soilInfRedu, SoilInf)
        self.SoilInfiltExceeded = self.SoilInfiltExceeded + scalar(
            self.InfiltCapSoil * soilInfRedu < SoilInf
        )

        MaxInfiltPath = min(self.InfiltCapPath * soilInfRedu, PathInf)
        self.PathInfiltExceeded = self.PathInfiltExceeded + scalar(
            self.InfiltCapPath * soilInfRedu < PathInf
        )

        InfiltSoilPath = min(MaxInfiltPath + MaxInfiltSoil, max(0.0, UStoreCapacity))
        self.In = InfiltSoilPath
        self.ActInfilt = InfiltSoilPath  # JS Ad this to be compatible with rest

        self.SumThickness = self.ZeroMap
        self.ZiLayer = self.ZeroMap

        # Limit rootingdepth (if set externally)
        self.ActRootingDepth = min(self.SoilThickness * 0.99, self.ActRootingDepth)

        # Determine Open Water EVAP based on waterfrac. Later subtract this from water that
        # enters the Kinematic wave
        self.ActEvapOpenWater = min(
            self.WaterLevel * 1000.0 * self.WaterFrac,
            self.WaterFrac * self.PotTransSoil,
        )

        self.RestEvap = self.PotTransSoil - self.ActEvapOpenWater

        self.ActEvapPond = self.ZeroMap
        if self.nrpaddyirri > 0:
            self.ActEvapPond = min(self.PondingDepth, self.RestEvap)
            self.PondingDepth = self.PondingDepth - self.ActEvapPond
            self.RestEvap = self.RestEvap - self.ActEvapPond

        # Go from top to bottom layer
        self.zi_t = self.zi
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            # Find layer with  zi level
            self.ZiLayer = ifthenelse(
                self.zi > self.SumThickness,
                min(self.ZeroMap + float(n), self.nrLayersMap - 1),
                self.ZiLayer,
            )

            self.SumThickness = self.UStoreLayerThickness[n] + self.SumThickness

        self.SaturationDeficit = self.SoilWaterCapacity - self.SatWaterDepth

        # evap available for soil evaporation
        self.RestEvap = self.RestEvap * self.CanopyGapFraction

        self.ActEvapUStore = self.ZeroMap

        self.SumThickness = self.ZeroMap
        l_Thickness = []
        self.storage = []
        l_T = []
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            l_T.append(self.SumThickness)
            self.SumLayer = self.SumThickness
            self.SumThickness = self.UStoreLayerThickness[n] + self.SumThickness

            l_Thickness.append(self.SumThickness)
            # Height of unsat zone in layer n
            self.L = ifthenelse(
                self.ZiLayer == float(n),
                ifthenelse(
                    self.ZeroMap + float(n) > 0, self.zi - l_Thickness[n - 1], self.zi
                ),
                self.UStoreLayerThickness[n],
            )
            # Depth for calculation of vertical fluxes (bottom layer or zi)
            self.z = ifthenelse(self.ZiLayer == float(n), self.zi, self.SumThickness)
            self.storage.append(self.L * (self.thetaS - self.thetaR))

            # First layer is treated differently than layers below first layer
            if n == 0:
                DownWard = InfiltSoilPath  # MaxInfiltPath+MaxInfiltSoil
                self.UStoreLayerDepth[n] = self.UStoreLayerDepth[n] + DownWard
                self.soilevapunsat = soilevap_SBM_unsat(
                    self.CanopyGapFraction,
                    self.RestEvap,
                    self.SoilWaterCapacity,
                    self.SatWaterDepth,
                    self.UStoreLayerDepth,
                    self.zi,
                    self.thetaS,
                    self.thetaR,
                    self.UStoreLayerThickness,
                )
                # assume soil evaporation is from first soil layer
                if self.nrpaddyirri > 0:
                    self.soilevapunsat = ifthenelse(
                        self.PondingDepth > 0.0,
                        0.0,
                        min(self.soilevapunsat, self.UStoreLayerDepth[0]),
                    )
                else:
                    self.soilevapunsat = min(self.soilevapunsat, self.UStoreLayerDepth[n])

                # The remaining 'RestEvap' can be used for evaporation from the saturated layer
                self.RestEvap = self.RestEvap - self.soilevapunsat
                self.soilevapsat = soilevap_SBM_sat(self.RestEvap,self.zi,self.thetaS,self.thetaR,self.UStoreLayerThickness,self.UStoreLayerDepth)
                
                # Total soil evaporation from the first soil layer
                self.soilevap = self.soilevapunsat + self.soilevapsat

                # Recalculate the water depths in the unsaturated and saturated buckets
                self.UStoreLayerDepth[n] = self.UStoreLayerDepth[n] - self.soilevapunsat
                self.SatWaterDepth = self.SatWaterDepth - self.soilevapsat

                # evap available for transpiration
                self.PotTrans = (
                    self.PotTransSoil - self.soilevap - self.ActEvapOpenWater
                )
                self.RestPotEvap, self.SatWaterDepth, self.ActEvapSat = actEvap_sat_SBM(
                    self.ActRootingDepth,
                    self.zi,
                    self.SatWaterDepth,
                    self.PotTrans,
                    self.rootdistpar,
                )
                self.UStoreLayerDepth[
                    n
                ], self.ActEvapUStore, self.RestPotEvap, self.ET = actEvap_unsat_SBM(
                    self.ActRootingDepth,
                    self.zi,
                    self.UStoreLayerDepth[n],
                    self.ZiLayer,
                    self.UStoreLayerThickness[n],
                    self.SumLayer,
                    self.RestPotEvap,
                    self.maskLayer[n],
                    self.ZeroMap,
                    self.ZeroMap + float(n),
                    self.ActEvapUStore,
                    self.c[n],
                    self.L,
                    self.thetaS,
                    self.thetaR,
                    self.UST,
                )

                if len(self.UStoreLayerThickness) > 1:
                    st = (
                        self.KsatVerFrac[n]
                        * self.KsatVer
                        * exp(-self.f * self.z)
                        * min(
                            (
                                (
                                    self.UStoreLayerDepth[n]
                                    / (self.L * (self.thetaS - self.thetaR))
                                )
                                ** self.c[n]
                            ),
                            1.0,
                        )
                    )
                    self.T[n] = ifthenelse(
                        self.SaturationDeficit <= 0.00001,
                        0.0,
                        min(self.UStoreLayerDepth[n], st),
                    )
                    self.T[n] = ifthenelse(
                        self.ZiLayer == float(n), self.maskLayer[n], self.T[n]
                    )
                    self.UStoreLayerDepth[n] = self.UStoreLayerDepth[n] - self.T[n]
            else:
                self.UStoreLayerDepth[n] = ifthenelse(
                    self.ZiLayer < float(n),
                    self.maskLayer[n],
                    self.UStoreLayerDepth[n] + self.T[n - 1],
                )
                self.UStoreLayerDepth[
                    n
                ], self.ActEvapUStore, self.RestPotEvap, self.ET = actEvap_unsat_SBM(
                    self.ActRootingDepth,
                    self.zi,
                    self.UStoreLayerDepth[n],
                    self.ZiLayer,
                    self.UStoreLayerThickness[n],
                    self.SumLayer,
                    self.RestPotEvap,
                    self.maskLayer[n],
                    self.ZeroMap,
                    self.ZeroMap + float(n),
                    self.ActEvapUStore,
                    self.c[n],
                    self.L,
                    self.thetaS,
                    self.thetaR,
                    self.UST,
                )
                st = (
                    self.KsatVerFrac[n]
                    * self.KsatVer
                    * exp(-self.f * self.z)
                    * min(
                        (
                            (
                                self.UStoreLayerDepth[n]
                                / (self.L * (self.thetaS - self.thetaR))
                            )
                            ** self.c[n]
                        ),
                        1.0,
                    )
                )

                # Transfer in layer with zi is not yet substracted from layer (set to zero)
                self.T[n] = ifthenelse(
                    self.ZiLayer <= float(n),
                    self.maskLayer[n],
                    min(self.UStoreLayerDepth[n], st),
                )
                self.UStoreLayerDepth[n] = ifthenelse(
                    self.ZiLayer < float(n),
                    self.maskLayer[n],
                    self.UStoreLayerDepth[n] - self.T[n],
                )

        # Determine transpiration
        self.Transpiration = self.ActEvapUStore + self.ActEvapSat
        self.ActEvap = (
            self.Transpiration
            + self.soilevap
            + self.ActEvapOpenWater
            + self.ActEvapPond
        )

        # Run only if we have irrigation areas or an externally given demand, determine irrigation demand based on potrans and acttrans
        if self.nrirri > 0 or hasattr(self, "IrriDemandExternal"):
            if not hasattr(self, "IrriDemandExternal"):  # if not given
                self.IrriDemand, self.IrriDemandm3 = self.irrigationdemand(
                    self.PotTrans, self.Transpiration, self.IrrigationAreas
                )
                IRDemand = (
                    idtoid(
                        self.IrrigationAreas,
                        self.IrrigationSurfaceIntakes,
                        self.IrriDemandm3,
                    )
                    * -1.0
                )
            else:
                IRDemand = self.IrriDemandExternal
            # loop over irrigation areas and assign Q to linked river extraction points
            self.Inflow = cover(IRDemand, self.Inflow)

        ##########################################################################
        # Transfer of water from unsaturated to saturated store...################
        ##########################################################################
        # Determine saturation deficit. NB, as noted by Vertessy and Elsenbeer 1997
        # this deficit does NOT take into account the water in the unsaturated zone

        # Optional Macrco-Pore transfer (not yet implemented for # layers > 1)
        self.MporeTransfer = self.ActInfilt * self.MporeFrac
        self.SatWaterDepth = self.SatWaterDepth + self.MporeTransfer
        # self.UStoreLayerDepth = self.UStoreLayerDepth - self.MporeTransfer

        self.SaturationDeficit = self.SoilWaterCapacity - self.SatWaterDepth

        Ksat = self.ZeroMap
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            Ksat = Ksat + ifthenelse(
                self.ZiLayer == float(n),
                self.KsatVerFrac[n] * self.KsatVer * exp(-self.f * self.zi),
                0.0,
            )

        self.DeepKsat = self.KsatVer * exp(-self.f * self.SoilThickness)

        # now the actual transfer to the saturated store from layers with zi
        self.Transfer = self.ZeroMap
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            if self.TransferMethod == 1:
                self.L = ifthen(
                    self.ZiLayer == float(n),
                    ifthenelse(
                        self.ZeroMap + float(n) > 0,
                        self.zi - l_Thickness[n - 1],
                        self.zi,
                    ),
                )
                self.Transfer = self.Transfer + ifthenelse(
                    self.ZiLayer == float(n),
                    min(
                        cover(self.UStoreLayerDepth[n], 0.0),
                        ifthenelse(
                            self.SaturationDeficit <= 0.00001,
                            0.0,
                            self.KsatVerFrac[n]
                            * self.KsatVer
                            * exp(-self.f * self.zi)
                            * (
                                min(
                                    cover(self.UStoreLayerDepth[n], 0.0),
                                    (self.L + 0.0001) * (self.thetaS - self.thetaR),
                                )
                            )
                            / (self.SaturationDeficit + 1),
                        ),
                    ),
                    0.0,
                )

            if self.TransferMethod == 2:
                self.L = ifthen(
                    self.ZiLayer == float(n),
                    ifthenelse(
                        self.ZeroMap + float(n) > 0,
                        self.zi - l_Thickness[n - 1],
                        self.zi,
                    ),
                )
                st = ifthen(
                    self.ZiLayer == float(n),
                    self.KsatVer
                    * exp(-self.f * self.zi)
                    * min(
                        (
                            self.UStoreLayerDepth[n]
                            / ((self.L + 0.0001) * (self.thetaS - self.thetaR))
                        ),
                        1.0,
                    )
                    ** self.c[n],
                )
                self.Transfer = self.Transfer + ifthenelse(
                    self.ZiLayer == float(n),
                    min(
                        self.UStoreLayerDepth[n],
                        ifthenelse(self.SaturationDeficit <= 0.00001, 0.0, st),
                    ),
                    0.0,
                )

        # check soil moisture
        self.ToExtra = self.ZeroMap

        for n in np.arange(len(self.UStoreLayerThickness) - 1, -1, -1):
            # self.UStoreLayerDepth[n] = ifthenelse(self.ZiLayer<=n, self.UStoreLayerDepth[n] + self.ToExtra,self.UStoreLayerDepth[n])
            diff = ifthenelse(
                self.ZiLayer == float(n),
                max(
                    0.0,
                    (cover(self.UStoreLayerDepth[n], 0.0) - self.Transfer)
                    - self.storage[n],
                ),
                max(
                    self.ZeroMap,
                    cover(self.UStoreLayerDepth[n], 0.0)
                    - ifthenelse(self.zi <= l_T[n], 0.0, self.storage[n]),
                ),
            )
            self.ToExtra = ifthenelse(diff > 0, diff, self.ZeroMap)
            self.UStoreLayerDepth[n] = self.UStoreLayerDepth[n] - diff

            if n > 0:
                self.UStoreLayerDepth[n - 1] = (
                    self.UStoreLayerDepth[n - 1] + self.ToExtra
                )

            # self.UStoreLayerDepth[n] = ifthenelse(self.ZiLayer<=n, self.UStoreLayerDepth[n]-diff,self.UStoreLayerDepth[n])

        SatFlow = self.ToExtra
        UStoreCapacity = (
            self.SoilWaterCapacity
            - self.SatWaterDepth
            - sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)
        )

        MaxCapFlux = max(
            0.0, min(Ksat, self.ActEvapUStore, UStoreCapacity, self.SatWaterDepth)
        )

        # No capilary flux is roots are in water, max flux if very near to water, lower flux if distance is large
        CapFluxScale = ifthenelse(
            self.zi > self.ActRootingDepth,
            self.CapScale
            / (self.CapScale + self.zi - self.ActRootingDepth)
            * self.timestepsecs
            / self.basetimestep,
            0.0,
        )
        self.CapFlux = MaxCapFlux * CapFluxScale
        ToAdd = self.CapFlux

        sumLayer = self.ZeroMap

        # Now add capflux to the layers one by one (from bottom to top)
        for n in np.arange(len(self.UStoreLayerThickness) - 1, -1, -1):

            L = ifthenelse(
                self.ZiLayer == float(n),
                ifthenelse(
                    self.ZeroMap + float(n) > 0, self.zi - l_Thickness[n - 1], self.zi
                ),
                self.UStoreLayerThickness[n],
            )
            thisLayer = ifthenelse(
                self.ZiLayer <= float(n),
                min(
                    ToAdd,
                    max(
                        L * (self.thetaS - self.thetaR) - self.UStoreLayerDepth[n], 0.0
                    ),
                ),
                0.0,
            )
            self.UStoreLayerDepth[n] = ifthenelse(
                self.ZiLayer <= float(n),
                self.UStoreLayerDepth[n] + thisLayer,
                self.UStoreLayerDepth[n],
            )
            ToAdd = ToAdd - cover(thisLayer, 0.0)
            sumLayer = sumLayer + cover(thisLayer, 0.0)

        # Determine Ksat at base
        self.DeepTransfer = min(self.SatWaterDepth, self.DeepKsat)
        # ActLeakage = 0.0
        # Now add leakage. to deeper groundwater
        self.ActLeakage = cover(max(0.0, min(self.MaxLeakage, self.DeepTransfer)), 0)
        self.Percolation = cover(
            max(0.0, min(self.MaxPercolation, self.DeepTransfer)), 0
        )

        # self.ActLeakage = ifthenelse(self.Seepage > 0.0, -1.0 * self.Seepage, self.ActLeakage)
        self.SatWaterDepth = (
            self.SatWaterDepth
            + self.Transfer
            - sumLayer
            - self.ActLeakage
            - self.Percolation
        )

        for n in np.arange(0, len(self.UStoreLayerThickness)):
            self.UStoreLayerDepth[n] = ifthenelse(
                self.ZiLayer == float(n),
                self.UStoreLayerDepth[n] - self.Transfer,
                self.UStoreLayerDepth[n],
            )

        # Determine % saturated taking into account subcell fraction
        self.Sat = max(
            self.SubCellFrac,
            scalar(self.SatWaterDepth >= (self.SoilWaterCapacity * 0.999)),
        )

        ##########################################################################
        # Horizontal (downstream) transport of water #############################
        ##########################################################################

        self.zi = max(
            0.0, self.SoilThickness - self.SatWaterDepth / (self.thetaS - self.thetaR)
        )  # Determine actual water depth

        # Re-Determine saturation deficit. NB, as noted by Vertessy and Elsenbeer 1997
        # this deficit does NOT take into account the water in the unsaturated zone
        self.SaturationDeficit = self.SoilWaterCapacity - self.SatWaterDepth

        # self.logger.debug("Waterdem set to Altitude....")
        self.WaterDem = self.Altitude - (self.zi * 0.001)
        self.waterSlope = max(
            0.000001, slope(self.WaterDem) * celllength() / self.reallength
        )
        if self.waterdem:
            self.waterLdd = lddcreate(self.WaterDem, 1e35, 1e35, 1e35, 1e35)
            # waterLdd = lddcreate(waterDem,1,1,1,1)

        # TODO: We should make a couple of itterations here...

        if self.waterdem:
            if self.LateralMethod == 1:
                Lateral = (
                    self.KsatHorFrac
                    * self.KsatVer
                    * self.waterSlope
                    * exp(-self.SaturationDeficit / self.M)
                )
            elif self.LateralMethod == 2:
                # Lateral = Ksat * self.waterSlope
                Lateral = (
                    self.KsatHorFrac
                    * self.KsatVer
                    * (exp(-self.f * self.zi) - exp(-self.f * self.SoilThickness))
                    * (1 / self.f)
                    / (self.SoilThickness - self.zi)
                    * self.waterSlope
                )
            else:
                Lateral = 0.0
            MaxHor = max(0.0, min(Lateral, self.SatWaterDepth))
            self.SatWaterFlux = accucapacityflux(
                self.waterLdd, self.SatWaterDepth, MaxHor
            )
            self.SatWaterDepth = accucapacitystate(
                self.waterLdd, self.SatWaterDepth, MaxHor
            )
        else:
            #
            # MaxHor = max(0,min(self.KsatVer * self.Slope * exp(-SaturationDeficit/self.M),self.SatWaterDepth*(self.thetaS-self.thetaR))) * timestepsecs/basetimestep
            # MaxHor = max(0.0, min(self.KsatVer * self.Slope * exp(-selield' object does not support item assignmentf.SaturationDeficit / self.M),
            #                      self.SatWaterDepth))
            if self.LateralMethod == 1:
                Lateral = (
                    self.KsatHorFrac
                    * self.KsatVer
                    * self.waterSlope
                    * exp(-self.SaturationDeficit / self.M)
                )
            elif self.LateralMethod == 2:
                # Lateral = Ksat * self.waterSlope
                Lateral = (
                    self.KsatHorFrac
                    * self.KsatVer
                    * (exp(-self.f * self.zi) - exp(-self.f * self.SoilThickness))
                    * (1 / self.f)
                    / (self.SoilThickness - self.zi + 1.0)
                    * self.waterSlope
                )
            else:
                Lateral = 0.0
            MaxHor = max(0.0, min(Lateral, self.SatWaterDepth))

            # MaxHor = self.ZeroMap
            self.SatWaterFlux = accucapacityflux(
                self.TopoLdd, self.SatWaterDepth, MaxHor
            )
            self.SatWaterDepth = accucapacitystate(
                self.TopoLdd, self.SatWaterDepth, MaxHor
            )

        ##########################################################################
        # Determine returnflow from first zone          ##########################
        ##########################################################################
        self.ExfiltWaterFrac = sCurve(
            self.SatWaterDepth, a=self.SoilWaterCapacity, c=5.0
        )
        self.ExfiltWater = self.ExfiltWaterFrac * (
            self.SatWaterDepth - self.SoilWaterCapacity
        )
        # self.ExfiltWater=ifthenelse (self.SatWaterDepth - self.SoilWaterCapacity > 0 , self.SatWaterDepth - self.SoilWaterCapacity , 0.0)
        self.SatWaterDepth = self.SatWaterDepth - self.ExfiltWater

        # Re-determine UStoreCapacity
        self.zi = max(
            0.0, self.SoilThickness - self.SatWaterDepth / (self.thetaS - self.thetaR)
        )  # Determine actual water depth

        self.SumThickness = self.ZeroMap
        self.ZiLayer = self.ZeroMap
        for n in np.arange(0, len(self.UStoreLayerThickness)):
            # Find layer with  zi level
            self.ZiLayer = ifthenelse(
                self.zi > self.SumThickness,
                min(self.ZeroMap + float(n), self.nrLayersMap - 1),
                self.ZiLayer,
            )

            self.SumThickness = self.UStoreLayerThickness[n] + self.SumThickness

        self.SumThickness = self.ZeroMap
        l_Thickness = []
        self.storage = []
        self.L = []
        l_T = []

        # redistribute soil moisture (balance)
        for n in np.arange(len(self.UStoreLayerThickness)):
            self.SumLayer = self.SumThickness
            l_T.append(self.SumThickness)
            self.SumThickness = self.UStoreLayerThickness[n] + self.SumThickness

            l_Thickness.append(self.SumThickness)
            # Height of unsat zone in layer n
            self.L.append(
                ifthenelse(
                    self.ZiLayer == float(n),
                    ifthenelse(
                        self.ZeroMap + float(n) > 0,
                        self.zi - l_Thickness[n - 1],
                        self.zi,
                    ),
                    self.UStoreLayerThickness[n],
                )
            )

            self.storage.append(self.L[n] * (self.thetaS - self.thetaR))

        self.ExfiltFromUstore = self.ZeroMap

        for n in np.arange(len(self.UStoreLayerThickness) - 1, -1, -1):
            diff = max(
                self.ZeroMap,
                cover(self.UStoreLayerDepth[n], 0.0)
                - ifthenelse(self.zi <= l_T[n], 0.0, self.storage[n]),
            )
            self.ExfiltFromUstore = ifthenelse(diff > 0, diff, self.ZeroMap)
            self.UStoreLayerDepth[n] = self.UStoreLayerDepth[n] - diff

            if n > 0:
                self.UStoreLayerDepth[n - 1] = (
                    self.UStoreLayerDepth[n - 1] + self.ExfiltFromUstore
                )

        # Re-determine UStoreCapacityield' object does not support item assignment
        UStoreCapacity = (
            self.SoilWaterCapacity
            - self.SatWaterDepth
            - sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)
        )

        # self.AvailableForInfiltration = self.AvailableForInfiltration - InfiltSoilPath - SatFlow #MaxInfiltPath+MaxInfiltSoil + SatFlow

        self.ActInfilt = (
            InfiltSoilPath - SatFlow
        )  # MaxInfiltPath+MaxInfiltSoil - SatFlow

        self.InfiltExcess = self.AvailableForInfiltration - InfiltSoilPath + SatFlow

        self.ExcessWater = self.AvailableForInfiltration - InfiltSoilPath + SatFlow

        self.CumInfiltExcess = self.CumInfiltExcess + self.InfiltExcess

        # self.ExfiltFromUstore = ifthenelse(self.zi == 0.0,self.ExfiltFromUstore,self.ZeroMap)

        self.ExfiltWater = self.ExfiltWater + self.ExfiltFromUstore

        self.inund = self.ExfiltWater + self.ExcessWater

        ponding_add = self.ZeroMap
        if self.nrpaddyirri > 0:
            ponding_add = cover(
                min(ifthen(self.h_p > 0, self.inund), self.h_p - self.PondingDepth), 0.0
            )
            self.PondingDepth = self.PondingDepth + ponding_add
            irr_depth = (
                ifthenelse(
                    self.PondingDepth < self.h_min, self.h_max - self.PondingDepth, 0.0
                )
                * self.CRPST
            )
            sqmarea = areatotal(
                self.reallength * self.reallength, self.IrrigationPaddyAreas
            )
            self.IrriDemandm3 = cover((irr_depth / 1000.0) * sqmarea, 0)
            IRDemand = idtoid(
                self.IrrigationPaddyAreas,
                self.IrrigationSurfaceIntakes,
                self.IrriDemandm3,
            ) * (-1.0 / self.timestepsecs)

            self.IRDemand = IRDemand
            self.Inflow = cover(IRDemand, self.Inflow)
            self.irr_depth = irr_depth

        UStoreCapacity = (
            self.SoilWaterCapacity
            - self.SatWaterDepth
            - sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)
        )
        self.UStoreDepth = sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)

        Ksat = self.KsatVer * exp(-self.f * self.zi)

        SurfaceWater = self.WaterLevel / 1000.0  # SurfaceWater (mm)
        self.CumSurfaceWater = self.CumSurfaceWater + SurfaceWater

        # Estimate water that may re-infiltrate
        # - Never more that 70% of the available water
        # - self.MaxReinFilt: a map with reinfilt locations (usually the river mak) can be supplied)
        # - take into account that the river may not cover the whole cell
        if self.reInfilt:
            self.reinfiltwater = min(
                self.MaxReinfilt,
                max(
                    0,
                    min(
                        SurfaceWater * self.RiverWidth / self.reallength * 0.7,
                        min(self.InfiltCapSoil * (1.0 - self.PathFrac), UStoreCapacity),
                    ),
                ),
            )
            self.CumReinfilt = self.CumReinfilt + self.reinfiltwater
            # TODO: This still has to be reworked fro the differnt layers
            self.UStoreDepth = self.UStoreDepth + self.reinfiltwater
        else:
            self.reinfiltwater = self.ZeroMap

        # The Max here may lead to watbal error. However, if inwaterMMM becomes < 0, the kinematic wave becomes very slow......
        if self.reInfilt:
            self.InwaterMM = (
                self.ExfiltWater
                + self.ExcessWater
                + self.SubCellRunoff
                + self.SubCellGWRunoff
                + self.RunoffOpenWater
                - self.reinfiltwater
                - self.ActEvapOpenWater
                - ponding_add
            )
        else:
            self.InwaterMM = max(
                0.0,
                self.ExfiltWater
                + self.ExcessWater
                + self.SubCellRunoff
                + self.SubCellGWRunoff
                + self.RunoffOpenWater
                - self.reinfiltwater
                - self.ActEvapOpenWater
                - ponding_add,
            )
        self.Inwater = self.InwaterMM * self.ToCubic  # m3/s
        print(self.currentTimeStep())
#        report(self.Inwater, os.path.join(self.Dir, self.runId, "firstInwater{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "firstInwater{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
        
        self.ExfiltWaterCubic = self.ExfiltWater * self.ToCubic
        self.SubCellGWRunoffCubic = self.SubCellGWRunoff * self.ToCubic
        self.SubCellRunoffCubic = self.SubCellRunoff * self.ToCubic
        self.InfiltExcessCubic = self.InfiltExcess * self.ToCubic
        self.ReinfiltCubic = -1.0 * self.reinfiltwater * self.ToCubic
        # self.Inwater = self.Inwater + self.Inflow  # Add abstractions/inflows in m^3/sec

        # Check if we do not try to abstract more runoff then present
        self.InflowKinWaveCell = upstream(
            self.TopoLdd, self.SurfaceRunoff
        )  # NG The extraction should be equal to the discharge upstream cell. You should not make the abstraction depended on the downstream cell, because they are correlated. During a stationary sum they will get equal to each other.
        MaxExtract = self.InflowKinWaveCell + self.Inwater  # NG
        # MaxExtract = self.SurfaceRunoff + self.Inwater
        self.SurfaceWaterSupply = ifthenelse(
            self.Inflow < 0.0, min(MaxExtract, -1.0 * self.Inflow), self.ZeroMap
        )
        self.OldSurfaceRunoff = self.SurfaceRunoff  # NG Store for iteration
        self.OldInwater = self.Inwater
        self.Inwater = self.Inwater + ifthenelse(
            self.SurfaceWaterSupply > 0, -1.0 * self.SurfaceWaterSupply, self.Inflow
        )
        self.Inwater = self.Inwater + self.OldInflow

        ##########################################################################
        # Runoff calculation via Kinematic wave ##################################
        ##########################################################################
        # per distance along stream
        q = self.Inwater / self.DCL
        
#        report(self.OldSurfaceRunoff, os.path.join(self.Dir, self.runId, "surfacerunoff.map"))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "surfacerunoff.map"),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
#        report(self.OldInwater, os.path.join(self.Dir, self.runId, "secondInwater{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "secondInwater{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
#        report(self.Inwater, os.path.join(self.Dir, self.runId, "thirdInwater{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "thirdInwater{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
#        report(q, os.path.join(self.Dir, self.runId, "q{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "q{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
#        report(self.SurfaceRunoff, os.path.join(self.Dir, self.runId, "SurfRunoffprekin{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "SurfRunoffprekin{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None
        # discharge (m3/s)
        self.SurfaceRunoff = kinematic(
            self.TopoLdd,
            self.SurfaceRunoff,
            q,
            self.Alpha,
            self.Beta,
            self.Tslice,
            self.timestepsecs,
            self.DCL,
        )  # m3/s
#        report(self.SurfaceRunoff, os.path.join(self.Dir, self.runId, "SurfRunoffpostkin{}.map".format(self.currentTimeStep())))
#        ds = gdal.Open(os.path.join(self.Dir, self.runId, "SurfRunoffpostkin{}.map".format(self.currentTimeStep())),GA_Update)
#        ds.SetProjection(self.coords_system)
#        ds = None

        # If inflow is negative we have abstractions. Check if demand can be met (by looking
        # at the flow in the upstream cell) and iterate if needed
        self.nrit = 0
        self.breakoff = 0.0001
        if float(mapminimum(spatial(self.Inflow))) < 0.0:
            while True:
                self.nrit += 1
                oldsup = self.SurfaceWaterSupply
                self.InflowKinWaveCell = upstream(self.TopoLdd, self.SurfaceRunoff)
                ##########################################################################
                # Iterate to make a better estimation for the supply #####################
                # (Runoff calculation via Kinematic wave) ################################
                ##########################################################################
                MaxExtract = self.InflowKinWaveCell + self.OldInwater
                self.SurfaceWaterSupply = ifthenelse(
                    self.Inflow < 0.0, min(MaxExtract, -1.0 * self.Inflow), self.ZeroMap
                )
                # Fraction of demand that is not used but flows back into the river get fracttion and move to return locations
                self.DemandReturnFlow = cover(
                    idtoid(
                        self.IrrigationSurfaceIntakes,
                        self.IrrigationSurfaceReturn,
                        self.DemandReturnFlowFraction * self.SurfaceWaterSupply,
                    ),
                    0.0,
                )

                self.Inwater = (
                    self.OldInwater
                    + ifthenelse(
                        self.SurfaceWaterSupply > 0,
                        -1.0 * self.SurfaceWaterSupply,
                        self.Inflow,
                    )
                    + self.DemandReturnFlow
                )
                # per distance along stream
                q = self.Inwater / self.DCL
                # discharge (m3/s)
                self.SurfaceRunoff = kinematic(
                    self.TopoLdd,
                    self.OldSurfaceRunoff,
                    q,
                    self.Alpha,
                    self.Beta,
                    self.Tslice,
                    self.timestepsecs,
                    self.DCL,
                )  # m3/s
                self.SurfaceRunoffMM = (
                    self.SurfaceRunoff * self.QMMConv
                )  # SurfaceRunoffMM (mm) from SurfaceRunoff (m3/s)

                self.InflowKinWaveCell = upstream(self.TopoLdd, self.OldSurfaceRunoff)
                deltasup = float(mapmaximum(abs(oldsup - self.SurfaceWaterSupply)))

                if deltasup < self.breakoff or self.nrit >= self.maxitsupply:
                    break

            self.InflowKinWaveCell = upstream(self.TopoLdd, self.SurfaceRunoff)
            self.updateRunOff()
        else:
            self.SurfaceRunoffMM = (
                self.SurfaceRunoff * self.QMMConv
            )  # SurfaceRunoffMM (mm) from SurfaceRunoff (m3/s)
            self.updateRunOff()

        # Now add the supply that is linked to irrigation areas to extra precip

        if self.nrirri > 0:
            # loop over irrigation areas and spread-out the supply over the area
            IRSupplymm = idtoid(
                self.IrrigationSurfaceIntakes,
                self.IrrigationAreas,
                self.SurfaceWaterSupply * (1 - self.DemandReturnFlowFraction),
            )
            sqmarea = areatotal(
                self.reallength * self.reallength, nominal(self.IrrigationAreas)
            )

            self.IRSupplymm = cover(
                IRSupplymm / (sqmarea / 1000.0 / self.timestepsecs), 0.0
            )

        if self.nrpaddyirri > 0:
            # loop over irrigation areas and spread-out the supply over the area
            IRSupplymm = idtoid(
                self.IrrigationSurfaceIntakes,
                ifthen(self.IrriDemandm3 > 0, self.IrrigationPaddyAreas),
                self.SurfaceWaterSupply,
            )
            sqmarea = areatotal(
                self.reallength * self.reallength,
                nominal(ifthen(self.IrriDemandm3 > 0, self.IrrigationPaddyAreas)),
            )

            self.IRSupplymm = cover(
                ((IRSupplymm * self.timestepsecs * 1000) / sqmarea), 0.0
            )


        # only run the reservoir module if needed
        if self.nrresSimple > 0:
            self.ReservoirVolume, self.OutflowSR = federicoreservoir(
            #self.ReservoirVolume, self.OutflowSR, self.ResPercFull, self.ResPrecipSR, self.ResEvapSR, self.DemandRelease = simplereservoir(
                self.ReservoirLocs_map,
                self.ReservoirLocs_arr,
                self.ReservoirVolume,
                self.OutflowSR,
                self.OldSurfaceRunoff,
                self.SurfaceRunoff,
                self.Reservoir_df,
                #self.ResSimpleArea,
                #self.ResMaxVolume,
                #self.ResTargetFullFrac,
                #self.ResMaxRelease,
                #self.ResDemand,
                #self.ResTargetMinFrac,
                #self.ReserVoirSimpleLocs,
                #self.ReserVoirPrecip,
                #self.ReserVoirPotEvap,
                #self.ReservoirSimpleAreas,
                Dir = self.Dir,
                coords = self.coords_system,
                timestepsecs=self.timestepsecs,
            )
#            report(self.OutflowSR, os.path.join(self.Dir, self.runId, "OutflowSR{}.map".format(self.currentTimeStep())))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "OutflowSR{}.map".format(self.currentTimeStep())),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
            
            self.coverOutflowSR = ifthenelse(self.OutflowSR>=0, self.OutflowSR, 22.0)
#            report(self.coverOutflowSR, os.path.join(self.Dir, self.runId, "coverOutflowSR{}.map".format(self.currentTimeStep())))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "coverOutflowSR{}.map".format(self.currentTimeStep())),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
            
#            self.OutflowDwn = upstream(
#                self.TopoLddOrg, cover(self.OutflowSR, scalar(0.0))
#            )
            self.OutflowDwn = upstream(
                self.TopoLddOrg, ifthenelse(self.OutflowSR>=0, self.OutflowSR, 0.0)
            )
            
#            report(self.OutflowDwn, os.path.join(self.Dir, self.runId, "OutflowDwn{}.map".format(self.currentTimeStep())))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "OutflowDwn{}.map".format(self.currentTimeStep())),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
#            report(self.Inflow, os.path.join(self.Dir, self.runId, "preInflow{}.map".format(self.currentTimeStep())))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "preInflow{}.map".format(self.currentTimeStep())),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
            
            self.Inflow = self.OutflowDwn + cover(self.Inflow, self.ZeroMap)
#            report(self.Inflow, os.path.join(self.Dir, self.runId, "Inflow{}.map".format(self.currentTimeStep())))
#            ds = gdal.Open(os.path.join(self.Dir, self.runId, "Inflow{}.map".format(self.currentTimeStep())),GA_Update)
#            ds.SetProjection(self.coords_system)
#            ds = None
        elif self.nrresComplex > 0:
            self.ReservoirWaterLevel, self.OutflowCR, self.ResPrecipCR, self.ResEvapCR, self.ReservoirVolumeCR = complexreservoir(
                self.ReservoirWaterLevel,
                self.ReserVoirComplexLocs,
                self.LinkedReservoirLocs,
                self.ResArea,
                self.ResThreshold,
                self.ResStorFunc,
                self.ResOutflowFunc,
                self.sh,
                self.hq,
                self.Res_b,
                self.Res_e,
                self.SurfaceRunoff,
                self.ReserVoirPrecip,
                self.ReserVoirPotEvap,
                self.ReservoirComplexAreas,
                self.wf_supplyJulianDOY(),
                timestepsecs=self.timestepsecs,
            )
            self.OutflowDwn = upstream(
                self.TopoLddOrg, cover(self.OutflowCR, scalar(0.0))
            )
            self.Inflow = self.OutflowDwn + cover(self.Inflow, self.ZeroMap)
        else:            
            self.Inflow = cover(self.Inflow, self.ZeroMap)

        self.OldInflow = self.Inflow
        self.MassBalKinWave = (
            (-self.KinWaveVolume + self.OldKinWaveVolume) / self.timestepsecs
            + self.InflowKinWaveCell
            + self.Inwater
            - self.SurfaceRunoff
        )

        Runoff = self.SurfaceRunoff

        # Updating
        # --------
        # Assume a tss file with as many columns as outputlocs. Start updating for each non-missing value and start with the
        # first column (nr 1). Assumes that outputloc and columns match!

        if self.updating:
            self.QM = timeinputscalar(self.updateFile, self.UpdateMap) * self.QMMConv

            # Now update the state. Just add to the Ustore
            # self.UStoreDepth =  result
            # No determine multiplication ratio for each gauge influence area.
            # For missing gauges 1.0 is assumed (no change).
            # UpDiff = areamaximum(QM,  self.UpdateMap) - areamaximum(self.SurfaceRunoffMM, self.UpdateMap)
            UpRatio = areamaximum(self.QM, self.UpdateMap) / areamaximum(
                self.SurfaceRunoffMM, self.UpdateMap
            )

            UpRatio = cover(areaaverage(UpRatio, self.TopoId), 1.0)
            # Now split between Soil and Kyn  wave
            self.UpRatioKyn = min(
                self.MaxUpdMult,
                max(self.MinUpdMult, (UpRatio - 1.0) * self.UpFrac + 1.0),
            )
            UpRatioSoil = min(
                self.MaxUpdMult,
                max(self.MinUpdMult, (UpRatio - 1.0) * (1.0 - self.UpFrac) + 1.0),
            )

            # update/nudge self.UStoreDepth for the whole upstream area,
            # not sure how much this helps or worsens things
            # TODO: FIx this for multiple layers
            UpdSoil = True
            if UpdSoil:
                toadd = (self.UStoreDepth * UpRatioSoil) - self.UStoreDepth
                self.UStoreDepth = self.UStoreDepth + toadd

            # Update the kinematic wave reservoir up to a maximum upstream distance
            MM = (1.0 - self.UpRatioKyn) / self.UpdMaxDist
            self.UpRatioKyn = MM * self.DistToUpdPt + self.UpRatioKyn
            self.SurfaceRunoff = self.SurfaceRunoff * self.UpRatioKyn
            self.SurfaceRunoffMM = (
                self.SurfaceRunoff * self.QMMConv
            )  # SurfaceRunoffMM (mm) from SurfaceRunoff (m3/s)
            self.updateRunOff()
            Runoff = self.SurfaceRunoff

        # Determine Soil moisture profile
        # self.vwc, self.vwcRoot: volumetric water content [m3/m3] per soil layer and root zone (including thetaR and saturated store)
        # self.vwc_perc, self.vwc_percRoot: volumetric water content [%] per soil layer and root zone (including thetaR and saturated store)
        # self.RootStore_sat: root water storage [mm] in saturated store (excluding thetaR)
        # self.RootStore_unsat: root water storage [mm] in unsaturated store (excluding thetaR)
        # self.RootStore: total root water storage [mm] (excluding thetaR)

        self.RootStore_sat = max(0.0, self.ActRootingDepth - self.zi) * (
            self.thetaS - self.thetaR
        )

        self.RootStore_unsat = self.ZeroMap
        self.SumThickness = self.ZeroMap
        self.vwc = []
        self.vwc_perc = []

        for n in np.arange(len(self.UStoreLayerThickness)):

            fracRoot = ifthenelse(
                self.ZiLayer > float(n),
                min(
                    1.0,
                    max(
                        0.0,
                        (min(self.ActRootingDepth, self.zi) - self.SumThickness)
                        / self.UStoreLayerThickness[n],
                    ),
                ),
                min(
                    1.0,
                    max(
                        0.0,
                        (self.ActRootingDepth - self.SumThickness)
                        / (self.zi + 1 - self.SumThickness),
                    ),
                ),
            )

            self.SumThickness = self.UStoreLayerThickness[n] + self.SumThickness

            self.vwc.append(
                ifthenelse(
                    self.ZiLayer > float(n),
                    self.UStoreLayerDepth[n] / self.UStoreLayerThickness[n]
                    + self.thetaR,
                    (
                        (
                            (
                                self.UStoreLayerDepth[n]
                                + (self.thetaS - self.thetaR)
                                * min(
                                    self.UStoreLayerThickness[n],
                                    (self.SumThickness - self.zi),
                                )
                            )
                            / self.UStoreLayerThickness[n]
                        )
                        + self.thetaR
                    ),
                )
            )

            self.vwc_perc.append((self.vwc[n] / self.thetaS) * 100.0)

            self.RootStore_unsat = self.RootStore_unsat + cover(
                fracRoot * self.UStoreLayerDepth[n], 0.0
            )

        self.RootStore = self.RootStore_sat + self.RootStore_unsat
        self.vwcRoot = self.RootStore / self.ActRootingDepth + self.thetaR
        self.vwc_percRoot = (self.vwcRoot / self.thetaS) * 100.0

        # 2:
        ##########################################################################
        # water balance ###########################################
        ##########################################################################

        self.QCatchmentMM = self.SurfaceRunoff * self.QMMConvUp
        self.RunoffCoeff = (
            self.QCatchmentMM
            / catchmenttotal(self.PrecipitationPlusMelt, self.TopoLdd)
            / catchmenttotal(cover(1.0), self.TopoLdd)
        )
        # self.AA = catchmenttotal(self.PrecipitationPlusMelt, self.TopoLdd)
        # self.BB = catchmenttotal(cover(1.0), self.TopoLdd)
        # Single cell based water budget. snow not included yet.

        self.CellStorage = (
            sum_list_cover(self.UStoreLayerDepth, self.ZeroMap) + self.SatWaterDepth
        )

        self.sumUstore = sum_list_cover(self.UStoreLayerDepth, self.ZeroMap)

        self.DeltaStorage = self.CellStorage - self.OrgStorage
        OutFlow = self.SatWaterFlux
        if self.waterdem:
            CellInFlow = upstream(self.waterLdd, scalar(self.SatWaterFlux))
        else:
            CellInFlow = upstream(self.TopoLdd, scalar(self.SatWaterFlux))

        self.CumOutFlow = self.CumOutFlow + OutFlow
        self.CumActInfilt = self.CumActInfilt + self.ActInfilt
        self.CumCellInFlow = self.CumCellInFlow + CellInFlow
        self.CumPrec = self.CumPrec + self.Precipitation
        self.CumEvap = self.CumEvap + self.ActEvap
        self.CumPotenTrans = self.CumPotenTrans + self.PotTrans
        self.CumPotenEvap = self.CumPotenEvap + self.PotenEvap

        self.CumInt = self.CumInt + self.Interception

        self.SnowCover = ifthenelse(self.Snow > 0.0, self.ZeroMap + 1.0, self.ZeroMap)
        self.CumLeakage = self.CumLeakage + self.ActLeakage
        self.CumInwaterMM = self.CumInwaterMM + self.InwaterMM
        self.CumExfiltWater = self.CumExfiltWater + self.ExfiltWater

        self.SoilWatbal = (
            self.ActInfilt
            + self.reinfiltwater
            + CellInFlow
            - self.Transpiration
            - self.soilevap
            - self.ExfiltWater
            - self.SubCellGWRunoff
            - self.DeltaStorage
            - self.SatWaterFlux
        )
        self.InterceptionWatBal = (
            self.PrecipitationPlusMelt
            - self.Interception
            - self.StemFlow
            - self.ThroughFall
            - (self.OldCanopyStorage - self.CanopyStorage)
        )
        self.SurfaceWatbal = (
            self.PrecipitationPlusMelt
            + self.oldIRSupplymm
            - self.Interception
            - self.ExcessWater
            - self.RunoffOpenWater
            - self.SubCellRunoff
            - self.ActInfilt
            - (self.OldCanopyStorage - self.CanopyStorage)
        )

        self.watbal = self.SoilWatbal + self.SurfaceWatbal


def main(argv=None):
    """
    Perform command line execution of the model.
    """
    caseName = "default_sbm"
    global multpars
    runId = "run_default"
    configfile = "wflow_sbm.ini"
    config_reservoir_file = None
    _lastTimeStep = 0
    _firstTimeStep = 0
    LogFileName = "wflow.log"

    runinfoFile = "runinfo.xml"
    timestepsecs = 86400
    wflow_cloneMap = "step2/wflow_subcatch.map"
    _NoOverWrite = 1
    global updateCols
    loglevel = logging.DEBUG

    if argv is None:
        argv = sys.argv[1:]
        if len(argv) == 0:
            usage()
            return
    ########################################################################
    ## Process command-line options                                        #
    ########################################################################
    try:
        opts, args = getopt.getopt(argv, "XL:hC:Ii:v:S:T:WR:u:s:EP:p:Xx:U:fOc:l:r:")
    except getopt.error as msg:
        pcrut.usage(msg)

    for o, a in opts:
        if o == "-C":
            caseName = a
        if o == "-R":
            runId = a
        if o == "-c":
            configfile = a
        if o == "-L":
            LogFileName = a
        if o == "-s":
            timestepsecs = int(a)
        if o == "-h":
            usage()
        if o == "-f":
            _NoOverWrite = 0
        if o == "-l":
            exec("loglevel = logging." + a)
        if o == "-r":
            config_reservoir_file = a
        

    starttime = dt.datetime(1990, 1, 1)

    if _lastTimeStep < _firstTimeStep:
        print(
            "The starttimestep ("
            + str(_firstTimeStep)
            + ") is smaller than the last timestep ("
            + str(_lastTimeStep)
            + ")"
        )
        usage()

    myModel = WflowModel(wflow_cloneMap, caseName, runId, configfile, config_reservoir_file)
    dynModelFw = wf_DynamicFramework(
        myModel, _lastTimeStep, firstTimestep=_firstTimeStep, datetimestart=starttime
    )
    dynModelFw.createRunId(
        NoOverWrite=_NoOverWrite,
        level=loglevel,
        logfname=LogFileName,
        model="wflow_sbm",
        doSetupFramework=False,
    )

    for o, a in opts:
        if o == "-P":
            left = a.split("=")[0]
            right = a.split("=")[1]
            configset(
                myModel.config, "variable_change_once", left, right, overwrite=True
            )
        if o == "-p":
            left = a.split("=")[0]
            right = a.split("=")[1]
            configset(
                myModel.config, "variable_change_timestep", left, right, overwrite=True
            )
        if o == "-X":
            configset(myModel.config, "model", "OverWriteInit", "1", overwrite=True)
        if o == "-I":
            configset(myModel.config, "run", "reinit", "1", overwrite=True)
        if o == "-i":
            configset(myModel.config, "model", "intbl", a, overwrite=True)
        if o == "-s":
            configset(myModel.config, "model", "timestepsecs", a, overwrite=True)
        if o == "-x":
            configset(myModel.config, "model", "sCatch", a, overwrite=True)
        if o == "-c":
            configset(myModel.config, "model", "configfile", a, overwrite=True)
        if o == "-M":
            configset(myModel.config, "model", "MassWasting", "0", overwrite=True)
        if o == "-Q":
            configset(myModel.config, "model", "ExternalQbase", "1", overwrite=True)
        if o == "-U":
            configset(myModel.config, "model", "updateFile", a, overwrite=True)
            configset(myModel.config, "model", "updating", "1", overwrite=True)
        if o == "-u":
            zz = []
            exec("zz =" + a)
            updateCols = zz
        if o == "-E":
            configset(myModel.config, "model", "reInfilt", "1", overwrite=True)
        if o == "-R":
            runId = a
        if o == "-W":
            configset(myModel.config, "model", "waterdem", "1", overwrite=True)
        if o == "-T":
            configset(myModel.config, "run", "endtime", a, overwrite=True)
        if o == "-S":
            configset(myModel.config, "run", "starttime", a, overwrite=True)
        if o == "-r":
        #    configset(myModel.reservoir_config, "files", "selected_reservoirs", a, overwrite=True)
            myModel.reservoir_txtfile = configget(myModel.reservoir_config, "files", "selected_reservoirs", "reservoirs/all_reservoirs_df.txt" )
            myModel.reservoir_coords = configget(myModel.reservoir_config, "files", "reservoir_coords", "reservoirs/reservoir_coords.txt" )
            myModel.reservoir_charact = configget(myModel.reservoir_config, "files", "reservoir_charact", "reservoirs/all_reservoirs_df.txt" )
            print("\n" + myModel.reservoir_txtfile + "\n")
            #print("\n" + self.reservoir_coords + "\n")
            #print("\n" + self.reservoir_charact + "\n")
            wflow_streamorder = configget(myModel.config,
                                          "model",
                                          "wflow_streamorder",
                                          "staticmaps/wflow_streamorder.map",)
            myModel.streamorder = readmap(os.path.join(myModel.Dir, wflow_streamorder))
            
        

    dynModelFw.setupFramework()
    dynModelFw._runInitial()
    dynModelFw._runResume()
    # dynModelFw._runDynamic(0, 0)
    dynModelFw._runDynamic(_firstTimeStep, _lastTimeStep)
    dynModelFw._runSuspend()
    dynModelFw._wf_shutdown()


if __name__ == "__main__":
    main()
