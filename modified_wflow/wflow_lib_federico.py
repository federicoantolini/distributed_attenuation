# Copyright (c) J. Schellekens 2005-2011
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
wflow_lib - terrain analysis and hydrological library
-----------------------------------------------------

The goal of this module is to make a series functions to upscale maps (DEM)
and to  maintain as much of the information in a detailled dem when upscaling
to a coarser DEM. These include:

    - river length (per cell)
    - river network location
    - elevation distribution
    - other terrain analysis

the wflow_prepare scripts use this library extensively.

$Author: schelle $
$Id: wflow_lib.py 808 2013-10-04 19:42:43Z schelle $
$Rev: 808 $
"""


import os
import os.path
import sys

import osgeo.gdal as gdal
from osgeo.gdalconst import *
from pcraster import *
from pcraster.framework import *
import numpy as np
import pandas as pd
import gzip, zipfile


def pt_flow_in_river(ldd, river):
    """
    Returns all points (True) that flow into the mak river (boolean map with river set to True)

    :param ldd: Drainage network
    :param river: Map of river (True River, False non-river)
    :return ifmap: map with infrlo points into the river (True)
    :return ctach: catchment of each of the inflow points
    """

    dspts = downstream(ldd, cover(river, 0))
    dspts = ifthenelse(cover(river, 0) == 1, 0, dspts)

    catch = subcatchment(ldd, nominal(uniqueid(dspts)))

    return dspts, catch


def sum_list_cover(list_of_maps, covermap):
    """
    Sums a list of pcrastermap using cover to fill in missing values

    :param list_of_maps: list of maps to sum
    :param covermap: maps/ value to use fro cover

    :return: sum of list of maps (single map)
    """
    sum_ = cover(0.0)
    for map in list_of_maps:
        sum_ = sum_ + cover(map, covermap)

    return sum_


def idtoid(sourceidmap, targetidmap, valuemap):
    """
    tranfer the values from valuemap at the point id's in sourceidmap to the areas in targetidmap.

    :param pointmap:
    :param areamap:
    :param valuemap:
    :return:
    """

    _area = pcr2numpy(targetidmap, 0.0).copy().astype(float)
    _pt = pcr2numpy(sourceidmap, 0.0).copy()
    _val = pcr2numpy(valuemap, 0.0).copy()

    for val in np.unique(_pt):
        if val > 0:  #
            _area[_area == val] = np.mean(_val[_pt == val])

    retmap = numpy2pcr(Scalar, _area, 0.0)

    return retmap



#def interpolateOutflow (value, inflowVol, storage_array, discharge_array, timestepsecs=3600):
#    storage = previousStorage + inflowVol
#    storage_upper = storage_array[np.where(storage_array > storage)][0]
#    storage_lower = storage_array[np.where(storage_array < storage)][-1]
#    discharge_upper = discharge_array[np.where(storage_array == storage_upper)]
#    discharge_lower = discharge_array[np.where(storage_array == storage_lower)]
#    discharge = discharge_upper - (storage_upper-storage) * (discharge_upper-discharge_lower) / (storage_upper-storage_lower)
#    outflowVol = discharge * timestepsecs
#    return outflowVol

def interpolate(x, x_ceil, x_floor, y_ceil, y_floor):
    '''interpolates a y value based on a given x, between floor and ceiling values
    relationship between x and y is known discretely, at certain values'''
    y = y_ceil - (x_ceil - x) * (y_ceil - y_floor) / (x_ceil - x_floor)
    return y

def findSO(row, reservoirs_df, output, timestepsecs):
    '''takes in input a row, i.e. a reservoir location with its endTerm
    reads the corresponding storage-discahrge-endTerm function in single_res_df: all those 3 depend on the water stage in the reservoir! 
    decomposes the endTerm into storage and discharge (outflow), interpolating values where necessary
    returns storage or outflow, depending on output (s/o)'''
    damID = row.name
    endTerm = row[0]
    single_res_df = reservoirs_df.loc[damID,:]
    #single_res_df.iloc[(single_res_df['endTerms']-endTerm).abs().argsort()[:2]]
    if endTerm > single_res_df['endTerms'].iloc[-1]:
        if output == 's':
            s = single_res_df['storage'].iloc[-1]
            return s
        elif output == 'o':
            o = endTerm - (2*single_res_df['storage'].iloc[-1]/timestepsecs)
            return o
    d_floor = single_res_df[single_res_df['endTerms'] <= endTerm].idxmax().values[0]
    d_ceil = single_res_df[single_res_df['endTerms'] > endTerm].idxmin().values[0]
    df_sort = single_res_df.loc[[d_floor,d_ceil]]
    print("df_sort of {}: {}\n".format(damID, df_sort))
    if df_sort['endTerms'].iloc[0] > df_sort['endTerms'].iloc[1]:
        df_sort = df_sort.iloc[::-1]
        print("reprint df_sort of {}: {}\n".format(damID, df_sort))
    e_floor, e_ceil = df_sort['endTerms'].values
    if output == 's':
        s_floor, s_ceil = df_sort['storage'].values
        s = interpolate(endTerm, e_ceil, e_floor, s_ceil, s_floor)
        return s
    elif output == 'o':
        o_floor, o_ceil = df_sort['outflow_rect'].values
        o = interpolate(endTerm, e_ceil, e_floor, o_ceil, o_floor)
        return o

def federicoreservoir(
        ReservoirLocs_map,
        ReservoirLocs_arr,
        previousStorage_map,
        previousOutflow_map,
        #previousDepth,
        previous_inflow,
        inflow,
        reservoirs_df,
        Dir,
        coords,
        timestepsecs = 3600,
        threshold = 1
        ):

    """
    :param ReserVoirLocs_map: 
    :param storage: initial storage m^3
    :param inflow: inflow m^3 s^-1
    :param maxstorage: maximum storage (above which water is spilled) m^3
    
    """
    previous_inflow_map = ifthen(ReservoirLocs_map>0, previous_inflow)
#    report(previous_inflow_map, os.path.join(Dir, "reservoirs/previous_inflow.map"))
#    ds = gdal.Open(os.path.join(Dir, "reservoirs/previous_inflow.map"),GA_Update)
#    ds.SetProjection(coords)
#    ds = None
    inflow_map = ifthen(ReservoirLocs_map>0, inflow)
#    report(inflow_map, os.path.join(Dir, "reservoirs/inflow.map"))
#    ds = gdal.Open(os.path.join(Dir, "reservoirs/inflow.map"),GA_Update)
#    ds.SetProjection(coords)
#    ds = None
    #inflowVol_map = inflow_map * timestepsecs
    
    #endTerms_map = inflow_map + (2*previousStorage_map/timestepsecs - previousOutflow_map)
    #endTerms_all_arr = pcr2numpy(endTerms_map, np.nan)
    #endTerms_arr = endTerms_all_arr[~np.isnan(endTerms_all_arr)] # to get rid of nan, gives the values in the right order
    
    
    previous_inflow_all_arr = pcr2numpy(previous_inflow_map, np.nan)
    previous_inflow_arr = previous_inflow_all_arr[~np.isnan(previous_inflow_all_arr)]
    inflow_all_arr = pcr2numpy(inflow_map, np.nan)
    inflow_arr = inflow_all_arr[~np.isnan(inflow_all_arr)]
    S1_all_arr = pcr2numpy(previousStorage_map, np.nan)
    S1_arr = S1_all_arr[~np.isnan(S1_all_arr)]
    O1_all_arr = pcr2numpy(previousOutflow_map, np.nan)
    O1_arr = O1_all_arr[~np.isnan(O1_all_arr)]
    endTerms_arr = (previous_inflow_arr + inflow_arr) + (2*S1_arr/timestepsecs - O1_arr)
    print("i1", previous_inflow_arr)
    print("i2", inflow_arr)
    print("s", S1_arr)
    print("o", O1_arr)
    print("e", endTerms_arr)
    endTerms_arr = numpy.where(endTerms_arr < 0,
                               0,
                               endTerms_arr)

    
    endTerms_series = pd.Series(endTerms_arr, index=ReservoirLocs_arr)
    endTerms_df = pd.DataFrame(endTerms_series, columns=['endTerms'])
    print("\n\nThese are the endTerms: {}\n{}\n".format(endTerms_df, endTerms_df.shape))
    S2_series = endTerms_df.apply(findSO, args=[reservoirs_df, 's', timestepsecs], axis=1)
    O2_series = endTerms_df.apply(findSO, args=[reservoirs_df, 'o', timestepsecs], axis=1)
    print("s", S2_series)
    print("o", O2_series)
    S2_all_arr = numpy.copy(S1_all_arr)
    S2_all_arr[~numpy.isnan(S2_all_arr)] = S2_series.values
    O2_all_arr = numpy.copy(O1_all_arr)
    O2_all_arr[~numpy.isnan(O2_all_arr)] = O2_series.values

    currentStorage_map = numpy2pcr(Scalar, S2_all_arr, np.nan)
    currentOutflow_map = numpy2pcr(Scalar, O2_all_arr, np.nan)
    #currentStorage_map = ifthen(boolean(ReservoirLocs_map), storage_series.values)
    #currentOutflow_map = ifthen(boolean(ReservoirLocs_map), outflow_series.values)
#    storage_arr = np.where(np.isnan(endTerms_all_arr),
#                           np.nan,
#                           storage_series.values)
#    outflow_arr = np.where(np.isnan(endTerms_all_arr),
#                           np.nan,
#                           outflow_series.values)
#    storage_map = numpy2pcr(Scalar, storage_arr, np.nan)
#    outflow_map = numpy2pcr(Scalar, outflow_arr, np.nan)
    
    return currentStorage_map, currentOutflow_map
    
#    if endTerms > maxStorage/timestepsecs
#    
#    maxStorage = storage_array[-1]
#    if (previousStorage + inflowVol) > maxStorage:
#        storage = maxStorage
#        outflowVol = previousStorage + inflowVol - maxStorage
#    else:
#        storage = previousStorage + inflowVol
#        outflowVol = interpolateOutflow(previousStorage, inflowVol, storage_array, discharge_array)
#        while (inflowVol - outflowVol) - (storage - previousStorage) > abs(threshold):
#            storage = previousStorage + inflowVol - outflowVol
#            outflowVol = interpolateOutflow(previousStorage, inflowVol, storage_array, discharge_array)
#    percfull = storage / maxStorage
#    outflow = outflowVol / timestepsecs
#    return storage, outflow, percfull, 0, 0, 0        
        
    
    
    
def simplereservoir(
    storage,
    inflow,
    ResArea,
    maxstorage,
    target_perc_full,
    maximum_Q,
    demand,
    minimum_full_perc,
    ReserVoirLocs,
    precip,
    pet,
    ReservoirSimpleAreas,
    timestepsecs=86400,
):
    """

    :param storage: initial storage m^3
    :param inflow: inflow m^3/s
    :param maxstorage: maximum storage (above which water is spilled) m^3
    :param target_perc_full: target fraction full (of max storage) -
    :param maximum_Q: maximum Q to release m^3/s if below spillway
    :param demand: water demand (all combined) m^3/s
    :param minimum_full_perc: target minimum full fraction (of max storage) -
    :param ReserVoirLocs: map with reservoir locations
    :param timestepsecs: timestep of the model in seconds (default = 86400)
    :return: storage (m^3), outflow (m^3/s), PercentageFull (0-1), Release (m^3/sec)
    """

    inflow = ifthen(boolean(ReserVoirLocs), inflow)

    prec_av = cover(
        ifthen(boolean(ReserVoirLocs), areaaverage(precip, ReservoirSimpleAreas)),
        scalar(0.0),
    )
    pet_av = cover(
        ifthen(boolean(ReserVoirLocs), areaaverage(pet, ReservoirSimpleAreas)),
        scalar(0.0),
    )

    oldstorage = storage
    storage = (
        storage
        + (inflow * timestepsecs)
        + (prec_av / 1000.0) * ResArea
        - (pet_av / 1000.0) * ResArea
    )

    percfull = ((storage + oldstorage) * 0.5) / maxstorage
    # first determine minimum (environmental) flow using a simple sigmoid curve to scale for target level
    fac = sCurve(percfull, a=minimum_full_perc, c=30.0)
    demandRelease = min(fac * demand * timestepsecs, storage)
    storage = storage - demandRelease

    # Re-determine percfull
    percfull = ((storage + oldstorage) * 0.5) / maxstorage

    wantrel = max(0.0, storage - (maxstorage * target_perc_full))
    # Assume extra maximum Q if spilling
    overflowQ = (percfull - 1.0) * (storage - maxstorage)
    torelease = min(wantrel, overflowQ + maximum_Q * timestepsecs)
    storage = storage - torelease
    outflow = (torelease + demandRelease) / timestepsecs
    percfull = storage / maxstorage

    return storage, outflow, percfull, prec_av, pet_av, demandRelease / timestepsecs


def lookupResRegMatr(ReserVoirLocs, values, hq, JDOY):

    np_res_ids = pcr2numpy(ReserVoirLocs, 0)
    npvalues = pcr2numpy(values, 0)
    out = np.copy(npvalues) * 0.0

    if len(hq) > 0:
        for key in hq:
            value = npvalues[np.where(np_res_ids == key)]

            val = np.interp(value, hq[key][:, 0], hq[key][:, JDOY])

            out[np.where(np_res_ids == key)] = val

    return numpy2pcr(Scalar, out, 0)


def lookupResFunc(ReserVoirLocs, values, sh, dirLookup):

    np_res_ids = pcr2numpy(ReserVoirLocs, 0)
    npvalues = pcr2numpy(values, 0)
    out = np.copy(npvalues) * 0.0

    if len(sh) > 0:
        for key in sh:
            value = npvalues[np.where(np_res_ids == key)]

            if dirLookup == "0-1":
                val = np.interp(value, sh[key][:, 0], sh[key][:, 1])
            if dirLookup == "1-0":
                val = np.interp(value, sh[key][:, 1], sh[key][:, 0])

            out[np.where(np_res_ids == key)] = val

    return numpy2pcr(Scalar, out, 0)


def complexreservoir(
    waterlevel,
    ReserVoirLocs,
    LinkedReserVoirLocs,
    ResArea,
    ResThreshold,
    ResStorFunc,
    ResOutflowFunc,
    sh,
    hq,
    res_b,
    res_e,
    inflow,
    precip,
    pet,
    ReservoirComplexAreas,
    JDOY,
    timestepsecs=86400,
):

    mv = -999.0

    inflow = ifthen(boolean(ReserVoirLocs), inflow)

    prec_av = ifthen(boolean(ReserVoirLocs), areaaverage(precip, ReservoirComplexAreas))
    pet_av = ifthen(boolean(ReserVoirLocs), areaaverage(pet, ReservoirComplexAreas))

    np_reslocs = pcr2numpy(ReserVoirLocs, 0.0)
    np_linkedreslocs = pcr2numpy(LinkedReserVoirLocs, 0.0)

    _outflow = []
    nr_loop = np.max([int(timestepsecs / 21600), 1])
    for n in range(0, nr_loop):
        np_waterlevel = pcr2numpy(waterlevel, np.nan)
        np_waterlevel_lower = np_waterlevel.copy()

        for val in np.unique(np_linkedreslocs):
            if val > 0:
                np_waterlevel_lower[np_linkedreslocs == val] = np_waterlevel[
                    np.where(np_reslocs == val)
                ]

        diff_wl = np_waterlevel - np_waterlevel_lower
        diff_wl[np.isnan(diff_wl)] = mv
        np_waterlevel_lower[np.isnan(np_waterlevel_lower)] = mv

        pcr_diff_wl = numpy2pcr(Scalar, diff_wl, mv)
        pcr_wl_lower = numpy2pcr(Scalar, np_waterlevel_lower, mv)

        storage_start = ifthenelse(
            ResStorFunc == 1,
            ResArea * waterlevel,
            lookupResFunc(ReserVoirLocs, waterlevel, sh, "0-1"),
        )

        outflow = ifthenelse(
            ResOutflowFunc == 1,
            lookupResRegMatr(ReserVoirLocs, waterlevel, hq, JDOY),
            ifthenelse(
                pcr_diff_wl >= 0,
                max(res_b * (waterlevel - ResThreshold) ** res_e, 0),
                min(-1 * res_b * (pcr_wl_lower - ResThreshold) ** res_e, 0),
            ),
        )

        np_outflow = pcr2numpy(outflow, np.nan)
        np_outflow_linked = np_reslocs * 0.0

        with np.errstate(invalid='ignore'):
            if np_outflow[np_outflow < 0] is not None:
                np_outflow_linked[
                    np.in1d(np_reslocs, np_linkedreslocs[np_outflow < 0]).reshape(
                        np_linkedreslocs.shape
                    )
                ] = np_outflow[np_outflow < 0]

        outflow_linked = numpy2pcr(Scalar, np_outflow_linked, 0.0)

        fl_nr_loop = float(nr_loop)
        storage = (
            storage_start
            + (inflow * timestepsecs / fl_nr_loop)
            + (prec_av / fl_nr_loop / 1000.0) * ResArea
            - (pet_av / fl_nr_loop / 1000.0) * ResArea
            - (cover(outflow, 0.0) * timestepsecs / fl_nr_loop)
            + (cover(outflow_linked, 0.0) * timestepsecs / fl_nr_loop)
        )

        waterlevel = ifthenelse(
            ResStorFunc == 1,
            waterlevel + (storage - storage_start) / ResArea,
            lookupResFunc(ReserVoirLocs, storage, sh, "1-0"),
        )

        np_outflow_nz = np_outflow * 0.0
        with np.errstate(invalid='ignore'):
            np_outflow_nz[np_outflow > 0] = np_outflow[np_outflow > 0]
        _outflow.append(np_outflow_nz)

    outflow_av_temp = np.average(_outflow, 0)
    outflow_av_temp[np.isnan(outflow_av_temp)] = mv
    outflow_av = numpy2pcr(Scalar, outflow_av_temp, mv)

    return waterlevel, outflow_av, prec_av, pet_av, storage


Verbose = 0


def lddcreate_save(
    lddname,
    dem,
    force,
    corevolume=1e35,
    catchmentprecipitation=1e35,
    corearea=1e35,
    outflowdepth=1e35,
):
    """
    Creates an ldd if a file does not exists or if the force flag is used

    input:
        - lddname (name of the ldd to create)
        - dem (actual dem)
        - force (boolean to force recreation of the ldd)
        - outflowdepth (set to 10.0E35 normally but smaller if needed)

    Output:
        - the LDD

    """
    if os.path.exists(lddname) and not force:
        if Verbose:
            print(("Returning existing ldd", lddname))
            return readmap(lddname)
    else:
        if Verbose:
            print(("Creating ldd", lddname))
            LDD = lddcreate(dem, 10.0e35, outflowdepth, 10.0e35, 10.0e35)
            report(LDD, lddname)
            return LDD


def configget(config, section, var, default):
    """

    Gets a string from a config file (.ini) and returns a default value if
    the key is not found. If the key is not found it also sets the value
    with the default in the config-file

    Input:
        - config - python ConfigParser object
        - section - section in the file
        - var - variable (key) to get
        - default - default string

    Returns:
        - string - either the value from the config file or the default value


    """
    Def = False
    try:
        ret = config.get(section, var)
    except:
        Def = True
        ret = default
        configset(config, section, var, default, overwrite=False)

    default = Def
    return ret


def configset(config, section, var, value, overwrite=False):
    """
    Sets a string in the in memory representation of the config object
    Deos NOT overwrite existing values if overwrite is set to False (default)

    Input:
        - config - python ConfigParser object
        - section - section in the file
        - var - variable (key) to set
        - value - the value to set
        - overwrite (optional, default is False)

    Returns:
        - nothing

    """

    if not config.has_section(section):
        config.add_section(section)
        config.set(section, var, value)
    else:
        if not config.has_option(section, var):
            config.set(section, var, value)
        else:
            if overwrite:
                config.set(section, var, value)


def configsection(config, section):
    """
    gets the list of keys in a section

    Input:
        - config
        - section

    Output:
        - list of keys in the section
    """
    try:
        ret = config.options(section)
    except:
        ret = []

    return ret


def getrows():
    """
    returns the number of rows in the current map

    Input:
        - -

    Output:
        - nr of rows in the current clonemap as a scalar
    """
    a = pcr2numpy(celllength(), numpy.nan).shape[0]

    return a


def getcols():
    """
    returns the number of columns in the current map

    Input:
        - -

    Output:
        - nr of columns in the current clonemap as a scalar
    """
    a = pcr2numpy(celllength(), numpy.nan).shape[1]

    return a


def getgridparams():
    """ return grid parameters in a python friendly way

    Output:
        [ Xul, Yul, xsize, ysize, rows, cols]

        - xul - x upper left centre
        - yul - y upper left centre
        - xsize - size of a cell in x direction
        - ysize - size of a cell in y direction
        - cols - number of columns
        - rows - number of rows
        - xlr -  x lower right centre
        - ylr -  y lower right centre
    """
    # This is the default, but add for safety...
    setglobaloption("coorcentre")
    # x and Y are the same for now
    xy = pcr2numpy(celllength(), numpy.nan)[0, 0]
    xu = pcr2numpy(xcoordinate(1), numpy.nan)[0, 0]
    yu = pcr2numpy(ycoordinate(1), numpy.nan)[0, 0]
    ylr = pcr2numpy(ycoordinate(1), numpy.nan)[getrows() - 1, getcols() - 1]
    xlr = pcr2numpy(xcoordinate(1), numpy.nan)[getrows() - 1, getcols() - 1]

    return [xu, yu, xy, xy, getrows(), getcols(), xlr, ylr]


def snaptomap(points, mmap):
    """
    Snap the points in _points_ to nearest non missing
    values in _mmap_. Can be used to move gauge locations
    to the nearest rivers.

    Input:
        - points - map with points to move
        - mmap - map with points to move to

    Return:
        - map with shifted points
    """
    points = cover(points, 0)
    # Create unique id map of mmap cells
    unq = nominal(cover(uniqueid(defined(mmap)), scalar(0.0)))
    # Now fill holes in mmap map with lues indicating the closes mmap cell.
    dist_cellid = scalar(spreadzone(unq, 0, 1))
    # Get map with values at location in points with closes mmap cell
    dist_cellid = ifthenelse(points > 0, dist_cellid, 0)
    # Spread this out
    dist_fill = spreadzone(nominal(dist_cellid), 0, 1)
    # Find the new (moved) locations
    npt = uniqueid(boolean(ifthen(dist_fill == unq, unq)))
    # Now recreate the original value in the points maps
    ptcover = spreadzone(cover(points, 0), 0, 1)
    # Now get the org point value in the pt map
    nptorg = ifthen(npt > 0, ptcover)

    return nptorg


def riverlength(ldd, order):
    """
    Determines the length of a river using the ldd.
    only determined for order and higher.

    Input:
        - ldd, order (streamorder)

    Returns:
        - totallength,lengthpercell, streamorder
    """
    strorder = streamorder(ldd)
    strorder = ifthen(strorder >= ordinal(order), strorder)
    dist = max(celllength(), ifthen(boolean(strorder), downstreamdist(ldd)))

    return catchmenttotal(cover(dist, 0), ldd), dist, strorder


def upscale_riverlength(ldd, order, factor):
    """
    Upscales the riverlength using 'factor'
    The resulting maps can be resampled (e.g. using resample.exe) by factor and should
    include the accurate length as determined with the original higher
    resolution maps.  This function is **depricated**,
    use are_riverlength instead as this version
    is very slow for large maps

    Input:
        - ldd
        - minimum streamorder to include

    Output:
        - distance per factor cells
    """

    strorder = streamorder(ldd)
    strorder = ifthen(strorder >= order, strorder)
    dist = cover(max(celllength(), ifthen(boolean(strorder), downstreamdist(ldd))), 0)
    totdist = max(
        ifthen(
            boolean(strorder),
            windowtotal(ifthen(boolean(strorder), dist), celllength() * factor),
        ),
        dist,
    )

    return totdist


def area_riverlength_factor(ldd, Area, Clength):
    """
    ceates correction factors for riverlength for
    the largest streamorder in each area

    Input:
        - ldd
        - Area
        - Clength (1d length of a cell (sqrt(Area))

    Output:
        - distance per area

    """
    strorder = streamorder(ldd)
    strordermax = areamaximum(strorder, Area)
    dist = downstreamdist(ldd)
    # count nr of strorder cells in each area
    nr = areatotal(ifthen(strorder == strordermax, dist), Area)
    # N = sqrt(areatotal(scalar(boolean(Area)),Area))
    N = Clength
    factor = nr / N

    return factor


def area_river_burnin(ldd, dem, order, Area):
    """
  Calculates the lowest values in as DEM for each erea in an area map for
  river of order *order*

  Input:
      - ldd
      - dem
      - order
      - Area map

  Output:
      - dem
  """
    strorder = streamorder(ldd)
    strordermax = areamaximum(strorder, Area)
    maxordcell = ifthen(strordermax > order, strordermax)
    riverdem = areaminimum(dem, Area)

    return ifthen(boolean(maxordcell), riverdem)


def area_percentile(inmap, area, n, order, percentile):
    """
  calculates percentile of inmap per area
  n is the number of points in each area,
  order, the sorter order of inmap per area (output of
  areaorder(inmap,area))
  n is the output of areatotal(spatial(scalar(1.0)),area)

  Input:
      - inmap
      - area map
      - n
      - order (riverorder)
      - percentile

  Output:
      - percentile map

  """
    i = rounddown((n * percentile) / 100.0 + 0.5)  # index in order map
    perc = ifthen(i == order, inmap)

    return areaaverage(perc, area)


def find_outlet(ldd):
    """
    Tries to find the outlet of the largest catchment in the Ldd

    Input:
        - Ldd

    Output:
        - outlet map (single point in the map)
    """
    largest = mapmaximum(catchmenttotal(spatial(scalar(1.0)), ldd))
    outlet = ifthen(catchmenttotal(1.0, ldd) == largest, spatial(scalar(1.0)))

    return outlet


def subcatch(ldd, outlet):
    """
    Determines a subcatchment map using LDD and outlet(s). In the resulting
    subcatchment map the i's of the catchment are determiend by the id's of
    the outlets.

    Input:
        - ldd
        - Outlet - maps with points for each outlet.

    Output:
        - map of subcatchments
    """
    subcatch = subcatchment(ldd, ordinal(outlet))

    return subcatch


def areastat(Var, Area):
    """
    Calculate several statistics of *Var* for each unique id in *Area*

    Input:
        - Var
        - Area

    Output:
        - Standard_Deviation,Average,Max,Min

    """
    Avg = areaaverage(Var, Area)
    Sq = (Var - Avg) ** 2
    N = areatotal(spatial(cellarea()), Area) / cellarea()
    Sd = (areatotal(Sq, Area) / N) ** 0.5
    Max = areamaximum(Var, Area)
    Min = areaminimum(Var, Area)

    return Sd, Avg, Max, Min


def checkerboard(mapin, fcc):
    """
    checkerboard create a checkerboard map with unique id's in a
    fcc*fcc cells area. The resulting map can be used
    to derive statistics for (later) upscaling of maps (using the fcc factor)

    .. warning: use with unitcell to get most reliable results!

    Input:
        - map (used to determine coordinates)
        - fcc (size of the areas in cells)

    Output:
        - checkerboard type map
    """
    msker = defined(mapin)
    ymin = mapminimum(ycoordinate(msker))
    yc = (ycoordinate((msker)) - ymin) / celllength()
    yc = rounddown(yc / fcc)
    # yc = yc/fcc
    xmin = mapminimum(xcoordinate((msker)))
    xc = (xcoordinate((msker)) - xmin) / celllength()
    xc = rounddown(xc / fcc)
    # xc = xc/fcc

    yc = yc * (mapmaximum(xc) + 1.0)

    xy = ordinal(xc + yc)

    return xy


def subcatch_stream(
    ldd,
    threshold,
    min_strahler=-999,
    max_strahler=999,
    assign_edge=False,
    assign_existing=False,
    up_area=None,
):
    """
    (From Deltares Hydrotools)

    Derive catchments based upon strahler threshold
    Input:
        ldd -- pcraster object direction, local drain directions
        threshold -- integer, strahler threshold, subcatchments ge threshold
            are derived
        min_strahler -- integer, minimum strahler threshold of river catchments
            to return
        max_strahler -- integer, maximum strahler threshold of river catchments
            to return
        assign_unique=False -- if set to True, unassigned connected areas at
            the edges of the domain are assigned a unique id as well. If set
            to False, edges are not assigned
        assign_existing=False == if set to True, unassigned edges are assigned
            to existing basins with an upstream weighting. If set to False,
            edges are assigned to unique IDs, or not assigned
    output:
        stream_ge -- pcraster object, streams of strahler order ge threshold
        subcatch -- pcraster object, subcatchments of strahler order ge threshold

    """
    # derive stream order

    stream = streamorder(ldd)
    stream_ge = ifthen(stream >= threshold, stream)
    stream_up_sum = ordinal(upstream(ldd, cover(scalar(stream_ge), 0)))
    # detect any transfer of strahler order, to a higher strahler order.
    transition_strahler = ifthenelse(
        downstream(ldd, stream_ge) != stream_ge,
        boolean(1),
        ifthenelse(
            nominal(ldd) == 5,
            boolean(1),
            ifthenelse(
                downstream(ldd, scalar(stream_up_sum)) > scalar(stream_ge),
                boolean(1),
                boolean(0),
            ),
        ),
    )
    # make unique ids (write to file)
    transition_unique = ordinal(uniqueid(transition_strahler))

    # derive upstream catchment areas (write to file)
    subcatch = nominal(subcatchment(ldd, transition_unique))

    if assign_edge:
        # fill unclassified areas (in pcraster equal to zero) with a unique id, above the maximum id assigned so far
        unique_edge = clump(ifthen(subcatch == 0, ordinal(0)))
        subcatch = ifthenelse(
            subcatch == 0,
            nominal(mapmaximum(scalar(subcatch)) + scalar(unique_edge)),
            nominal(subcatch),
        )
    elif assign_existing:
        # unaccounted areas are added to largest nearest draining basin
        if up_area is None:
            up_area = ifthen(boolean(cover(stream_ge, 0)), accuflux(ldd, 1))
        riverid = ifthen(boolean(cover(stream_ge, 0)), subcatch)

        friction = 1.0 / scalar(
            spreadzone(cover(ordinal(up_area), 0), 0, 0)
        )  # *(scalar(ldd)*0+1)
        delta = ifthen(
            scalar(ldd) >= 0,
            ifthen(cover(subcatch, 0) == 0, spreadzone(cover(riverid, 0), 0, friction)),
        )
        subcatch = ifthenelse(boolean(cover(subcatch, 0)), subcatch, delta)

    # finally, only keep basins with minimum and maximum river order flowing through them
    strahler_subcatch = areamaximum(stream, subcatch)
    subcatch = ifthen(
        ordinal(strahler_subcatch) >= min_strahler,
        ifthen(ordinal(strahler_subcatch) <= max_strahler, subcatch),
    )

    return stream_ge, ordinal(subcatch)


def subcatch_order_a(ldd, oorder):
    """
    Determines subcatchments using the catchment order

    This version uses the last cell BELOW order to derive the
    catchments. In general you want the _b version

    Input:
        - ldd
        - order - order to use

    Output:
        - map with catchment for the given streamorder
    """
    outl = find_outlet(ldd)
    large = subcatchment(ldd, boolean(outl))
    stt = streamorder(ldd)
    sttd = downstream(ldd, stt)
    pts = ifthen((scalar(sttd) - scalar(stt)) > 0.0, sttd)
    dif = upstream(
        ldd,
        cover(ifthen(large, uniqueid(boolean(ifthen(stt == ordinal(oorder), pts)))), 0),
    )
    dif = cover(scalar(outl), dif)  # Add catchment outlet
    dif = ordinal(uniqueid(boolean(dif)))
    sc = subcatchment(ldd, dif)

    return sc, dif, stt


def subcatch_order_b(
    ldd, oorder, sizelimit=0, fill=False, fillcomplete=False, stoporder=0
):
    """
    Determines subcatchments using the catchment order

    This version tries to keep the number op upstream/downstream catchment the
    small by first dederivingatchment connected to the major river(the order) given, and fill
    up from there.

    Input:
        - ldd
        - oorder - order to use
        - sizelimit - smallest catchments to include, default is all (sizelimit=0) in number of cells
        - if fill is set to True the higer order catchment are filled also
        - if fillcomplete is set to True the whole ldd is filled with catchments.


    :returns sc, dif, nldd; Subcatchment, Points, subcatchldd
    """
    # outl = find_outlet(ldd)
    # large = subcatchment(ldd,boolean(outl))

    if stoporder == 0:
        stoporder = oorder

    stt = streamorder(ldd)
    sttd = downstream(ldd, stt)
    pts = ifthen((scalar(sttd) - scalar(stt)) > 0.0, sttd)
    maxorder = getCellValue(mapmaximum(stt), 1, 1)
    dif = uniqueid(boolean(ifthen(stt == ordinal(oorder), pts)))

    if fill:
        for order in range(oorder, maxorder):
            m_pts = ifthen((scalar(sttd) - scalar(order)) > 0.0, sttd)
            m_dif = uniqueid(boolean(ifthen(stt == ordinal(order), m_pts)))
            dif = uniqueid(boolean(cover(m_dif, dif)))

        for myorder in range(oorder - 1, stoporder, -1):
            sc = subcatchment(ldd, nominal(dif))
            m_pts = ifthen((scalar(sttd) - scalar(stt)) > 0.0, sttd)
            m_dif = uniqueid(boolean(ifthen(stt == ordinal(myorder - 1), m_pts)))
            dif = uniqueid(boolean(cover(ifthen(scalar(sc) == 0, m_dif), dif)))

        if fillcomplete:
            sc = subcatchment(ldd, nominal(dif))
            cs, m_dif, stt = subcatch_order_a(ldd, stoporder)
            dif = uniqueid(
                boolean(cover(ifthen(scalar(sc) == 0, ordinal(m_dif)), ordinal(dif)))
            )

    scsize = catchmenttotal(1, ldd)
    dif = ordinal(uniqueid(boolean(ifthen(scsize >= sizelimit, dif))))
    sc = subcatchment(ldd, dif)

    # Make pit ldd
    nldd = lddrepair(ifthenelse(cover(dif, 0) > 0, 5, ldd))

    return sc, dif, nldd


def getRowColPoint(in_map, xcor, ycor):
    """
    returns the row and col in a map at the point given.
    Works but is rather slow.

    Input:
        - in_map - map to determine coordinates from
        - xcor - x coordinate
        - ycor - y coordinate

    Output:
        - row, column
    """
    x = pcr2numpy(xcoordinate(boolean(scalar(in_map) + 1.0)), numpy.nan)
    y = pcr2numpy(ycoordinate(boolean(scalar(in_map) + 1.0)), numpy.nan)
    XX = pcr2numpy(celllength(), 0.0)
    tolerance = 0.5  # takes a single point

    diffx = x - xcor
    diffy = y - ycor
    col_ = numpy.absolute(diffx) <= (XX[0, 0] * tolerance)  # cellsize
    row_ = numpy.absolute(diffy) <= (XX[0, 0] * tolerance)  # cellsize
    point = col_ * row_

    return point.argmax(0).max(), point.argmax(1).max()


def getValAtPoint(in_map, xcor, ycor):
    """
    returns the value in a map at the point given.
    works but is rather slow.

    Input:
        - in_map - map to determine coordinates from
        - xcor - x coordinate
        - ycor - y coordinate

    Output:
        - value
    """
    x = pcr2numpy(xcoordinate(defined(in_map)), numpy.nan)
    y = pcr2numpy(ycoordinate(defined(in_map)), numpy.nan)
    XX = pcr2numpy(celllength(), 0.0)
    themap = pcr2numpy(in_map, numpy.nan)
    tolerance = 0.5  # takes a single point

    diffx = x - xcor
    diffy = y - ycor
    col_ = numpy.absolute(diffx) <= (XX[0, 0] * tolerance)  # cellsize
    row_ = numpy.absolute(diffy) <= (XX[0, 0] * tolerance)  # cellsize
    point = col_ * row_
    pt = point.argmax()

    return themap.ravel()[pt]


def points_to_map(in_map, xcor, ycor, tolerance):
    """
    Returns a map with non zero values at the points defined
    in X, Y pairs. It's goal is to replace the pcraster col2map program.

    tolerance should be 0.5 to select single points
    Performance is not very good and scales linear with the number of points


    Input:
        - in_map - map to determine coordinates from
        - xcor - x coordinate (array or single value)
        - ycor - y coordinate (array or single value)
        - tolerance - tolerance in cell units. 0.5 selects a single cell\
        10 would select a 10x10 block of cells

    Output:
        - Map with values burned in. 1 for first point, 2 for second and so on
    """
    point = in_map * 0.0

    x = pcr2numpy(xcoordinate(defined(in_map)), numpy.nan)
    y = pcr2numpy(ycoordinate(defined(in_map)), numpy.nan)
    cell_length = float(celllength())

    # simple check to use both floats and numpy arrays
    try:
        c = xcor.ndim
    except:
        xcor = numpy.array([xcor])
        ycor = numpy.array([ycor])

    # Loop over points and "burn in" map
    for n in range(0, xcor.size):
        if Verbose:
            print (n)
        diffx = x - xcor[n]
        diffy = y - ycor[n]
        col_ = numpy.absolute(diffx) <= (cell_length * tolerance)  # cellsize
        row_ = numpy.absolute(diffy) <= (cell_length * tolerance)  # cellsize
        point = point + numpy2pcr(Scalar, ((col_ * row_) * (n + 1)), numpy.nan)

    return ordinal(point)


def reservoirs_to_map(in_map, xcor, ycor, tolerance, values, path, coords):
    """
    Returns a map with non zero values at the points defined
    in X, Y pairs. It's goal is to replace the pcraster col2map program.

    tolerance should be 0.5 to select single points
    Performance is not very good and scales linear with the number of points


    Input:
        - in_map - map of river network used to link reservoir coordinates to inline locations
        - xcor - x coordinate (array or single value) of reservoirs
        - ycor - y coordinate (array or single value) of reservoirs
        - tolerance - tolerance in cell units. 0.5 selects a single cell\
        10 would select a 10x10 block of cells

    Output:
        - Map with values burned in. Values are damIDs (reservoirIDs).
    """
    print("starting to convert reservoir points to PCRaster map")
    orig_reduce_tol_factor = 0.9  # factor to reduce tolerance if more than one cell is selected to burn in the point
    # simple check to use both floats and numpy arrays
    try:
        c = xcor.ndim
    except:
        xcor = numpy.array([xcor])
        ycor = numpy.array([ycor])

    point = scalar(in_map) * 0.0
    for n in range(len(values)):
        damID = values[n]
        strahler = int(str(damID)[0])
        #transform the river network (streamorder), 1 on streams, null otherwise
        if strahler == 6:
            river_map = ifthenelse(scalar(in_map)==9, scalar(1), numpy.nan)
        elif strahler == 5:
            river_map = ifthenelse(scalar(in_map)<9, scalar(in_map), numpy.nan)
            river_map = ifthenelse(scalar(river_map)>6, scalar(1), numpy.nan)
        elif strahler == 4:
            river_map = ifthenelse(scalar(in_map)<8, scalar(in_map), numpy.nan)
            river_map = ifthenelse(scalar(river_map)>5, scalar(1), numpy.nan)
        elif damID in [301219, 301220, 301221, 301222]:
            river_map = ifthenelse(scalar(in_map)==4, scalar(1), numpy.nan)
        elif strahler == 3:
            river_map = ifthenelse(scalar(in_map)<7, scalar(in_map), numpy.nan)
            river_map = ifthenelse(scalar(river_map)>4, scalar(1), numpy.nan)
        elif strahler == 2:
            river_map = ifthenelse(scalar(in_map)<7 , scalar(in_map), numpy.nan)
            river_map = ifthenelse(scalar(river_map)>2, scalar(1), numpy.nan)
        else:
            print("first digit of damID {} is not in the range of defined Strahler orders".format(damID))
            return
    
        # river_map = ifthenelse(scalar(in_map)>3, scalar(1), numpy.nan)
        # #report(river_map, os.path.join(path, "reservoirs/rivernet_map.map"))
        # #ds = gdal.Open(os.path.join(path, "reservoirs/rivernet_map.map"),GA_Update)
        # #ds.SetProjection(coords)
        # #ds = None
        
        # in_map_arr = pcr2numpy(in_map, numpy.nan)
        river_map_arr = pcr2numpy(river_map, numpy.nan)
        # print(in_map_arr.min(), in_map_arr.max())
        # print(in_map_arr[600:610, 600:610])
        # print(river_map_arr.min(), river_map_arr.max())
        # print(river_map_arr[759:762, 550:553])
        # x = pcr2numpy(xcoordinate(defined(river_map)), numpy.nan)
        # y = pcr2numpy(ycoordinate(defined(river_map)), numpy.nan)
        x = pcr2numpy(ifthenelse(scalar(river_map)==1, xcoordinate(boolean(river_map)), numpy.nan), numpy.nan)
        y = pcr2numpy(ifthenelse(scalar(river_map)==1, ycoordinate(boolean(river_map)), numpy.nan), numpy.nan)
        cell_length = float(celllength())        

        # Loop over points and "burn in" map
        tol = tolerance
        # if Verbose:
        #     print (n)
        diffx = x - xcor[n]
        diffy = y - ycor[n]
        # print(diffx[759:769, 545:555])
        # print(diffy[759:769, 545:555])
            
        #if the coords of a reservoir fall out of the wflow river network, nothing is burned in.
        #progressively increase tolerance until the point is burned in to the closest location on the wflow river network.
        prod = 0
        while prod < 1:
            # reduce_tol_factor = orig_reduce_tol_factor
            col_ = numpy.absolute(diffx) <= (cell_length * tol)  # cellsize
            row_ = numpy.absolute(diffy) <= (cell_length * tol)  # cellsize
            # print(row_[759:762, 550:553])
            # print(col_[760, 551], row_[760, 551], river_map_arr[760, 551])
            # print(type(col_[760, 551]), type(row_[760, 551]), type(river_map_arr[760, 551]))
            # print((col_*row_*river_map_arr)[760, 551])
            #numpy.savetxt(os.path.join(path, 'reservoirs/col_{}.txt'.format(n)), col_, delimiter=',', fmt='%1d')
            #numpy.savetxt(os.path.join(path, 'reservoirs/row_{}.txt'.format(n)), row_, delimiter=',', fmt='%1d')
            #print(col_[685:688,1049:1052])
            #print(row_[1049:1052])
            prod = numpy.nansum(col_*row_*river_map_arr)
            # to solve the problem of having 2 consecutive cells selected instead of 1, due to resol of xcoordinate fun
            if prod>1:
                print(values[n], prod, tol)
                print("change")
                # print(col_[619:621,758:761])
                index_of_selected_cells = np.nonzero((col_*row_)==1)
                col_index_of_cells_to_remove = index_of_selected_cells[0][:-1]
                row_index_of_cells_to_remove = index_of_selected_cells[1][:-1]
                print(col_index_of_cells_to_remove, row_index_of_cells_to_remove)
                col_[col_index_of_cells_to_remove, row_index_of_cells_to_remove] = 0
                row_[col_index_of_cells_to_remove, row_index_of_cells_to_remove] = 0
                # print(col_[619:621,758:761])
                prod = numpy.nansum(col_*row_*river_map_arr)
            print(values[n], prod, tol)
            tol+=0.1
        point = point + numpy2pcr(Scalar, ((col_ * row_) * values[n]), numpy.nan)
        
    point = ifthenelse(point>0.0, nominal(point), nominal(numpy.nan))
    #point = nominal(point)
    print("finished converting reservoir points to PCRaster map")
    return point


def detdrainlength(ldd, xl, yl):
    """
    Determines the drainaige length (DCL) for a non square grid

    Input:
        - ldd - drainage network
        - xl - length of cells in x direction
        - yl - length of cells in y direction

    Output:
        - DCL
    """
    # take into account non-square cells
    # if ldd is 8 or 2 use Ylength
    # if ldd is 4 or 6 use Xlength
    draindir = scalar(ldd)
    slantlength = sqrt(xl ** 2 + yl ** 2)
    drainlength = ifthenelse(
        draindir == 2,
        yl,
        ifthenelse(
            draindir == 8,
            yl,
            ifthenelse(draindir == 4, xl, ifthenelse(draindir == 6, xl, slantlength)),
        ),
    )

    return drainlength


def detdrainwidth(ldd, xl, yl):
    """
    Determines width of drainage over DEM for a non square grid

    Input:
        - ldd - drainage network
        - xl - length of cells in x direction
        - yl - length of cells in y direction

    Output:
        - DCL
    """
    # take into account non-square cells
    # if ldd is 8 or 2 use Xlength
    # if ldd is 4 or 6 use Ylength
    draindir = scalar(ldd)
    slantwidth = (xl + yl) * 0.5
    drainwidth = ifthenelse(
        draindir == 2,
        xl,
        ifthenelse(
            draindir == 8,
            xl,
            ifthenelse(draindir == 4, yl, ifthenelse(draindir == 6, yl, slantwidth)),
        ),
    )
    return drainwidth


def classify(
    inmap, lower=[0, 10, 20, 30], upper=[10, 20, 30, 40], classes=[2, 2, 3, 4]
):
    """
    classify a scaler maps accroding to the boundaries given in classes.

    """

    result = ordinal(cover(-1))
    for l, u, c in zip(lower, upper, classes):
        result = cover(ifthen(inmap >= l, ifthen(inmap < u, ordinal(c))), result)

    return ifthen(result >= 0, result)


def derive_HAND(dem, ldd, accuThreshold, rivers=None, basin=None):
    """
    Function derives Height-Above-Nearest-Drain.
    See http://www.sciencedirect.com/science/article/pii/S003442570800120X
    Input:
        dem -- pcraster object float32, elevation data
        ldd -- pcraster object direction, local drain directions
        accuThreshold -- upstream amount of cells as threshold for river
            delineation
        rivers=None -- you can provide a rivers layer here. Pixels that are
                        identified as river should have a value > 0, other
                        pixels a value of zero.
        basin=None -- set a boolean pcraster map where areas with True are estimated using the nearest drain in ldd distance
                        and areas with False by means of the nearest friction distance. Friction distance estimated using the
                        upstream area as weight (i.e. drains with a bigger upstream area have a lower friction)
                        the spreadzone operator is used in this case.
    Output:
        hand -- pcraster bject float32, height, normalised to nearest stream
        dist -- distance to nearest stream measured in cell lengths
            according to D8 directions
    """
    if rivers is None:
        stream = ifthenelse(accuflux(ldd, 1) >= accuThreshold, boolean(1), boolean(0))
    else:
        stream = boolean(cover(rivers, 0))

    height_river = ifthenelse(stream, ordinal(dem * 100), 0)
    if basin is None:
        up_elevation = scalar(subcatchment(ldd, height_river))
    else:
        drainage_surf = ifthen(rivers, accuflux(ldd, 1))
        weight = 1.0 / scalar(spreadzone(cover(ordinal(drainage_surf), 0), 0, 0))
        up_elevation = ifthenelse(
            basin,
            scalar(subcatchment(ldd, height_river)),
            scalar(spreadzone(height_river, 0, weight)),
        )
        # replace areas outside of basin by a spread zone calculation.
    hand = max(scalar(ordinal(dem * 100)) - up_elevation, 0) / 100
    dist = ldddist(ldd, stream, 1)

    return hand, dist


def sCurve(X, a=0.0, b=1.0, c=1.0):
    """
    sCurve function:

    Input:
        - X input map
        - C determines the steepness or "stepwiseness" of the curve.
          The higher C the sharper the function. A negative C reverses the function.
        - b determines the amplitude of the curve
        - a determines the centre level (default = 0)

    Output:
        - result
    """
    try:
        s = 1.0 / (b + exp(-c * (X - a)))
    except:
        s = 1.0 / (b + np.exp(-c * (X - a)))
    return s


def sCurveSlope(X, a=0.0, b=1.0, c=1.0):
    """
    First derivative of the sCurve defined by a,b,c at point X

    Input:
        - X - value to calculate for
        - a
        - b
        - c

    Output:
        - first derivative (slope) of the curve at point X
    """
    sc = sCurve(X, a=a, b=b, c=c)
    slope = sc * (1 - sc)
    return slope


def Gzip(fileName, storePath=False, chunkSize=1024 * 1024):
    """
        Usage: Gzip(fileName, storePath=False, chunksize=1024*1024)
        Gzip the given file to the given storePath and then remove the file.
        A chunk size may be selected. Default is 1 megabyte
        Input:
            fileName:   file to be GZipped
            storePath:  destination folder. Default is False, meaning the file will be zipped to its own folder
            chunkSize:  size of chunks to write. If set too large, GZip will fail with memory problems
        """
    import gzip

    if not storePath:
        pathName = os.path.split(fileName)[0]
        fileName = os.path.split(fileName)[1]
        curdir = os.path.curdir
        os.chdir(pathName)
    # open files for reading / writing
    r_file = open(fileName, "rb")
    w_file = gzip.GzipFile(fileName + ".gz", "wb", 9)
    dataChunk = r_file.read(chunkSize)
    while dataChunk:
        w_file.write(dataChunk)
        dataChunk = r_file.read(chunkSize)
    w_file.flush()
    w_file.close()
    r_file.close()
    os.unlink(fileName)  # We don't need the file now
    if not storePath:
        os.chdir(curdir)


# These come from GLOFRIS_Utils


def Gzip(fileName, storePath=False, chunkSize=1024 * 1024):
    """
        Usage: Gzip(fileName, storePath=False, chunksize=1024*1024)
        Gzip the given file to the given storePath and then remove the file.
        A chunk size may be selected. Default is 1 megabyte
        Input:
            fileName:   file to be GZipped
            storePath:  destination folder. Default is False, meaning the file will be zipped to its own folder
            chunkSize:  size of chunks to write. If set too large, GZip will fail with memory problems
        """
    if not storePath:
        pathName = os.path.split(fileName)[0]
        fileName = os.path.split(fileName)[1]
        curdir = os.path.curdir
        os.chdir(pathName)
    # open files for reading / writing
    r_file = open(fileName, "rb")
    w_file = gzip.GzipFile(fileName + ".gz", "wb", 9)
    dataChunk = r_file.read(chunkSize)
    while dataChunk:
        w_file.write(dataChunk)
        dataChunk = r_file.read(chunkSize)
    w_file.flush()
    w_file.close()
    r_file.close()
    os.unlink(fileName)  # We don't need the file now
    if not storePath:
        os.chdir(curdir)


def zipFiles(fileList, fileTarget):
    """
    Usage: zipFiles(fileList, fileTarget)
    zip the given list of files to the given target file
    Input:
        fileList:   list of files to be zipped
        fileTarget: target zip-file
    """
    zout = zipfile.ZipFile(fileTarget, "w", compression=zipfile.ZIP_DEFLATED)
    for fname in fileList:
        zout.write(fname, arcname=os.path.split(fname)[1])
    zout.close()


def readMap(fileName, fileFormat):
    """
    Read geographical file into memory

    :param fileName:
    :param fileFormat:
    :return x, y, data, FillVal:
    """
    # Open file for binary-reading
    mapFormat = gdal.GetDriverByName(fileFormat)
    mapFormat.Register()
    ds = gdal.Open(fileName)
    if ds is None:
        print("Could not open " + fileName + ". Something went wrong!! Shutting down")
        sys.exit(1)
        # Retrieve geoTransform info
    geotrans = ds.GetGeoTransform()
    originX = geotrans[0]
    originY = geotrans[3]
    resX = geotrans[1]
    resY = geotrans[5]
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    x = numpy.linspace(originX + resX / 2, originX + resX / 2 + resX * (cols - 1), cols)
    y = numpy.linspace(originY + resY / 2, originY + resY / 2 + resY * (rows - 1), rows)
    # Retrieve raster
    RasterBand = ds.GetRasterBand(1)  # there's only 1 band, starting from 1
    data = RasterBand.ReadAsArray(0, 0, cols, rows)
    FillVal = RasterBand.GetNoDataValue()
    RasterBand = None
    ds = None
    return x, y, data, FillVal


def cutMapById(data, subcatchmap, id, x, y, FillVal):
    """

    :param data: 2d numpy array to cut
    :param subcatchmap: 2d numpy array with subcatch
    :param id: id (value in the array) to cut by
    :param x: array with x values
    :param y:  array with y values
    :return: x,y, data
    """

    if len(data.flatten()) == len(subcatchmap.flatten()):
        scid = subcatchmap == id
        data[np.logical_not(scid)] = FillVal
        xid, = np.where(scid.max(axis=0))
        xmin = xid.min()
        xmax = xid.max()
        if xmin >= 1:
            xmin = xmin - 1
        if xmax < len(x) - 1:
            xmax = xmax + 1

        yid, = np.where(scid.max(axis=1))
        ymin = yid.min()
        ymax = yid.max()
        if ymin >= 1:
            ymin = ymin - 1
        if ymax < len(y) - 1:
            ymax = ymax + 1

        return (
            x[xmin:xmax].copy(),
            y[ymin:ymax].copy(),
            data[ymin:ymax, xmin:xmax].copy(),
        )
    else:
        return None, None, None


def writeMap(fileName, fileFormat, x, y, data, FillVal):
    """ Write geographical data into file"""

    verbose = False
    gdal.AllRegister()
    driver1 = gdal.GetDriverByName("GTiff")
    driver2 = gdal.GetDriverByName(fileFormat)

    # Processing
    if verbose:
        print("Writing to temporary file " + fileName + ".tif")
    # Create Output filename from (FEWS) product name and data and open for writing

    if data.dtype == np.int32:
        TempDataset = driver1.Create(
            fileName + ".tif", data.shape[1], data.shape[0], 1, gdal.GDT_Int32
        )
    else:
        TempDataset = driver1.Create(
            fileName + ".tif", data.shape[1], data.shape[0], 1, gdal.GDT_Float32
        )
    # Give georeferences
    xul = x[0] - (x[1] - x[0]) / 2
    yul = y[0] + (y[0] - y[1]) / 2
    TempDataset.SetGeoTransform([xul, x[1] - x[0], 0, yul, 0, y[1] - y[0]])
    # get rasterband entry
    TempBand = TempDataset.GetRasterBand(1)
    # fill rasterband with array
    TempBand.WriteArray(data, 0, 0)
    TempBand.FlushCache()
    TempBand.SetNoDataValue(FillVal)
    # Create data to write to correct format (supported by 'CreateCopy')
    if verbose:
        print("Writing to " + fileName + ".map")
    outDataset = driver2.CreateCopy(fileName, TempDataset, 0)
    TempDataset = None
    outDataset = None
    if verbose:
        print("Removing temporary file " + fileName + ".tif")
    os.remove(fileName + ".tif")

    if verbose:
        print("Writing to " + fileName + " is done!")
