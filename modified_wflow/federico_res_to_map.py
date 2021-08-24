import os
import os.path
import sys

import osgeo.gdal as gdal
from osgeo.gdalconst import *
from pcraster import *
from pcraster.framework import *
import numpy as np
import pandas as pd
# import gzip, zipfile

def reservoirs_to_map(in_map, xcor, ycor, tolerance, values, path):
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
    
    #transform the river network (streamorder), 1 on streams, null otherwise
    river_map = ifthenelse(scalar(in_map)>1, scalar(1), numpy.nan)
    #report(river_map, os.path.join(path, "reservoirs/rivernet_map.map"))
    #ds = gdal.Open(os.path.join(path, "reservoirs/rivernet_map.map"),GA_Update)
    #ds.SetProjection(coords)
    #ds = None
    point = river_map * 0.0
    river_map_arr = pcr2numpy(river_map, numpy.nan)
    x = pcr2numpy(xcoordinate(defined(river_map)), numpy.nan)
    y = pcr2numpy(ycoordinate(defined(river_map)), numpy.nan)
    cell_length = float(celllength())

    # simple check to use both floats and numpy arrays
    try:
        c = xcor.ndim
    except:
        xcor = numpy.array([xcor])
        ycor = numpy.array([ycor])

    # Loop over points and "burn in" map
    for n in range(0, xcor.size):
        tol = tolerance
        if Verbose:
            print (n)
        diffx = x - xcor[n]
        diffy = y - ycor[n]
        #if the coords of a reservoir fall out of the wflow river network, nothing is burned in.
        #progressively increase tolerance until the point is burned in to the closest location on the wflow river network.
        prod = 0
        while prod < 1:
            reduce_tol_factor = orig_reduce_tol_factor
            col_ = numpy.absolute(diffx) <= (cell_length * tol)  # cellsize
            while numpy.nansum(col_) > 1:
                col_ = numpy.absolute(diffx) <= (cell_length * (tol*reduce_tol_factor))  # cellsize
                reduce_tol_factor *= 0.9 
            reduce_tol_factor = orig_reduce_tol_factor
            row_ = numpy.absolute(diffy) <= (cell_length * tol)  # cellsize
            while numpy.nansum(row_) > 1:
                row_ = numpy.absolute(diffx) <= (cell_length * (tol*reduce_tol_factor))  # cellsize
                reduce_tol_factor *= 0.9
            #numpy.savetxt(os.path.join(path, 'reservoirs/col_{}.txt'.format(n)), col_, delimiter=',', fmt='%1d')
            #numpy.savetxt(os.path.join(path, 'reservoirs/row_{}.txt'.format(n)), row_, delimiter=',', fmt='%1d')
            #print(col_[685:688,1049:1052])
            #print(row_[1049:1052])
            prod = numpy.nansum(col_*row_*river_map_arr)
            print(values[n], prod, tol)
            tol+=0.1
        point = point + numpy2pcr(Scalar, ((col_ * row_) * values[n]), numpy.nan)
    
    point = ifthenelse(point>0.0, nominal(point), nominal(numpy.nan))
    #point = nominal(point)
    print("finished converting reservoir points to PCRaster map")
    return point


current_folder = "A:/heuristics/prova_optim"
run_name = "0_5"
runFolder = os.path.join(current_folder, run_name)
streamorder_map = os.path.join(runFolder, "staticmaps", "step2", "wflow_streamorder_remapped.map")

reservoir_coords_filename = os.path.join(current_folder, "reservoirs", "reservoir_coords.txt")
reservoir_subset_filename = os.path.join(current_folder, "res_subsets", "0_5.txt")

reservoir_coords_df = pd.read_table(reservoir_coords_filename, index_col='damID')
reservoir_subset_df = pd.read_table(reservoir_subset_filename, squeeze=True)
reservoirLocs_df = reservoir_coords_df[reservoir_coords_df.index.isin(reservoir_subset_df)]
reservoirLocs_X = numpy.array(list(reservoirLocs_df['X']))
reservoirLocs_Y = numpy.array(list(reservoirLocs_df['Y']))

ds_studyarea = gdal.Open(os.path.join(current_folder, "staticmaps", "step2", "wflow_dem.map"), GA_ReadOnly)
coords_system = ds_studyarea.GetProjection()
ds_studyarea = None

ReservoirLocs_map = reservoirs_to_map(streamorder_map, 
reservoirLocs_X, reservoirLocs_Y, 
0.5, 
reservoir_subset_df, 
current_folder)

report(ReservoirLocs_map, os.path.join(current_folder, "reservoirs", "ReservoirLocs_{}.map".format(run_name)))
ds = gdal.Open(os.path.join(current_folder, "reservoirs", "ReservoirLocs_{}.map".format(run_name)),GA_Update)
ds.SetProjection(coords_system)
ds = None