# -*- coding: utf-8 -*-
"""
Created on Fri May 17 11:01:30 2019

@author: antolini
"""

import wflow.wflow_lib_federico as tr
from wflow.wf_DynamicFramework_federico import *

import os
import getopt
import glob
import sys
from mpi4py import MPI
#import numpy as np
import gdal
from gdalconst import *
driver = gdal.GetDriverByName('PCRaster')
driver.Register()

def createPrecipitation(studyarea, rain, output):
    ds_studyarea = gdal.Open(studyarea, GA_ReadOnly)
    coords_system = ds_studyarea.GetProjection()
    ds_studyarea = None
    
    sa = tr.readmap(studyarea)
    precipitation_area = tr.ifthen(tr.boolean(sa), tr.scalar(rain))
    
    tr.report(precipitation_area, output)
    tr.report(precipitation_area, output[:-4]+'_'+output[-3:]+'.map')
    ds = gdal.Open(output, GA_Update)
    ds.SetProjection(coords_system)
    ds = None

def createTemperature(studyarea, temp, output):
    ds_studyarea = gdal.Open(studyarea, GA_ReadOnly)
    coords_system = ds_studyarea.GetProjection()
    ds_studyarea = None
    
    sa = tr.readmap(studyarea)
    temperature_area = tr.ifthen(tr.boolean(sa), tr.scalar(temp))
    
    tr.report(temperature_area, output)
    ds = gdal.Open(output, GA_Update)
    ds.SetProjection(coords_system)
    ds = None

def createLayer(studyarea, value, output):
    ds_studyarea = gdal.Open(studyarea, GA_ReadOnly)
    coords_system = ds_studyarea.GetProjection()
    ds_studyarea = None
    
    sa = tr.readmap(studyarea)
    layer_area = tr.ifthen(tr.boolean(sa), tr.scalar(value))
    
    tr.report(layer_area, output)
    ds = gdal.Open(output, GA_Update)
    ds.SetProjection(coords_system)
    ds = None


def createStack(inputFolder, valueDict, studyarea, size, rank):
    #name = "P" for precipitation, "TEMP" for temperatures
        
    names = ["P", "TEMP", "PET", "IF"]
    inmapsFolder = inputFolder + "/inmaps/"
    
    # here starts the parallel: the following 3 lines ensure that ranks take each a cycle of the for loop
    # a rank can take multiple cycles, but cycles are equally distributed
    for i, step in enumerate(valueDict):  
        if i%size != rank:  # % gives the remainder of i divided by size... smart!!
            continue
        
        rain = valueDict[step][0]
        layername = generateNameT(names[0], step)
        createPrecipitation(studyarea, rain, inmapsFolder+layername)
        
        temp = valueDict[step][1]
        layername = generateNameT(names[1], step)
        createTemperature(studyarea, temp, inmapsFolder+layername)
        
        pet = valueDict[step][2]
        layername = generateNameT(names[2], step)
        createLayer(studyarea, pet, inmapsFolder+layername)
        
        inflow = valueDict[step][3]
        layername = generateNameT(names[3], step)
        createLayer(studyarea, inflow, inmapsFolder+layername)
        
        print("Step {} completed".format(step))


def main(argv=None):
    comm = MPI.COMM_WORLD  #parallelization starts here, each node will run everything from here on
    rank = comm.Get_rank() #rank is the number of node, ranks go from 0 to size-1
    size = comm.Get_size() # number of nodes, will use all the nodes specified in the job
    
    caseName = "C:/Users/antolini/Documents/prove2.0_turkey/Volga/Hewett/"
    precipitation = 86.1 #mm, 100-year 1-hour rainfall
    temperature = 16 #degrees Celsius
    potential_evapotranspiration = 0 #mm  http://mesonet.agron.iastate.edu/agclimate/smts.php?station=CIRI4&opt=5&year1=2018&month1=4&day1=1&hour1=0&year2=2018&month2=7&day2=31&hour2=0
    inflow = 0 #m3/s
    timesteps = 24
    _OverWrite = True
    
    
    if argv is None:
        argv = sys.argv[1:]
        if len(argv) == 0:
            usage()
            return
    
    
    try:
        opts, args = getopt.getopt(argv, "C:P:T:e:I:t:o")
    except getopt.error as msg:
        pcrut.usage(msg)

    for o, a in opts:
        if o == "-C":
            caseName = a
        if o == "-P":
            precipitation = a
        if o == "-T":
            temperature = a
        if o == "-e":
            potential_evapotranspiration = a
        if o == "-I":
            inflow = a
        if o == "-t":
            timesteps = int(a)
        if o == "-o":
            _OverWrite = False


    #inputFolder = "C:/Users/antolini/Documents/prove2.0_turkey/Volga/Hewett/hewett_10"
    inputFolder = caseName
    values = {}
    
    # all the instructions before are repeated run by each rank/process/node
    # it is important that all the processes define their own variables, such as empty dict values, empty lists, etc.
    
    if rank == 0:  #the following is only run by process/rank 0
        try:
            precipitation = int(precipitation)   
            for timestep in range(1, timesteps+1):
                values[timestep] = [0]
                if timestep == 2:
                    values[timestep] = [precipitation]
        except:
            precipitationFile = os.path.join(inputFolder, precipitation)
            infile = open(precipitationFile, 'r')
            infile.readline()
            lines = infile.readlines()
            i = 0
            while i < timesteps:
                line = lines[i]
                linestrip = line.strip().split(',')
                timestep, precipitation = linestrip[0], linestrip[-1]
                timestep, precipitation = int(timestep), float(precipitation)
                values[timestep] = [precipitation]
                print(timestep, values[timestep])
                i+=1
            infile.close()
            
        
        
        try:
            temperature = int(temperature)
            for timestep in range(1, timesteps+1):
                print(timestep, temperature)
                print(timestep, values[timestep])
                values[timestep].append(temperature)
                
        except:
            temperatureFile = os.path.join(inputFolder, temperature)
            infile = open(temperatureFile, 'r')
            infile.readline()
            lines = infile.readlines()
            i = 0
            while i < timesteps:
                line = lines[i]
                timestep, temperature = line.strip().split(',')
                timestep, temperature = int(timestep), int(temperature)
                values[timestep].append(temperature)
                i+=1
            infile.close()
        
        
        try:
            potential_evapotranspiration = int(potential_evapotranspiration)   
            for timestep in range(1, timesteps+1):
                values[timestep].append(potential_evapotranspiration)
        except:
            potential_evapotranspirationFile = os.path.join(inputFolder, potential_evapotranspiration)
            infile = open(potential_evapotranspirationFile, 'r')
            infile.readline()
            lines = infile.readlines()
            i = 0
            while i < timesteps:
                line = lines[i]
                timestep, potential_evapotranspiration = line.strip().split(',')
                timestep, potential_evapotranspiration = int(timestep), float(potential_evapotranspiration)
                values[timestep].append(potential_evapotranspiration)
                i+=1
            infile.close()
        
        
        try:
            inflow = float(inflow)   
            for timestep in range(1, timesteps+1):
                values[timestep].append(inflow)
        except:
            inflowFile = os.path.join(inputFolder, inflow)
            infile = open(inflowFile, 'r')
            infile.readline()
            lines = infile.readlines()
            i = 0
            while i < timesteps:
                line = lines[i]
                timestep, inflow = line.strip().split(',')
                timestep, inflow = int(timestep), float(inflow)
                values[timestep].append(inflow)
                i+=1
            infile.close()
        
        
        
        if _OverWrite:
            if (inputFolder + "/inmaps") in glob.glob(inputFolder + "/*"):
                files = glob.glob(inputFolder + "/inmaps/*")
                for f in files:
                    os.remove(f)
            else:
                os.mkdir(inputFolder + "/inmaps/")
    
    values = comm.bcast(values, root=0)  # the result of what rank 0 did is broadcasted to all the other processes, including itself
    comm.Barrier()  #simple instruction, so that processes will stop here until every process has called the barrier
    createStack(inputFolder, values, inputFolder+"/staticmaps/step2/wflow_subcatch.map", 
                size, rank)

        
if __name__ == "__main__":
    main()
