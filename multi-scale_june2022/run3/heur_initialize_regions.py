'''
initialize generation 0 of subsets

'''

import os
#import arcpy
import math
import time
import random
import copy
import numpy as np
import pandas as pd
import geopandas as gpd
# import pysal as ps

import heur_geospatial as h_geo


def get_name_from_num(subset_num, gen_n):
    '''
    given the number of subset and the number of generation, it returns the subset string name combining the two
    '''
    subset_num = int(subset_num)
    gen_n = int(gen_n)
    name = '_' + '0'*(2-len(str(gen_n))) + (1-gen_n)*'00' + (1-gen_n)*(3-len(str(subset_num)))*'0' + str(10000*gen_n + subset_num)
    return name

def get_num_from_name(name):
    num = int(name.strip('_'))
    return num

# damIDList = []
# reachIDList = []
# dam_reach_Dict = {}
# reach_dam_Dict = {}

# reachDict = {}
# hortonDict = {}
# hortDamDict = {}
# volDict = {}
# areaDict = {}
# ratioVtoADict = {}
# costDict = {}
# floodedDict = {}
# ratioVtoCDict = {}
# ratioVtoACDict = {}

# outputFolder = "outputFolder/"
# huc10 = "Volga"
# huc12 = "Hewett"




def init_gen0(resPolyg_df, num_subsets, runFolder, max_strahl=5): # budget, maxFloodedArea, 
    '''
    resPolyg_df: rows=damID, cols=properties
    num_subsets: in generation 0
    budget, maxFloodedArea: constraints (not used)
    gen0_df: generation 0 of subsets, rows=damID, cols=#subset, values=0|1
    '''
    
    flooded_table = h_geo.get_flooded_table(runFolder)
    
    # gen0_index = resPolyg_df[resPolyg_df['Strahler'] <= max_strahl].index
    gen0_index = resPolyg_df.index
    damIDList = gen0_index.tolist()
    flooded_table = flooded_table.loc[damIDList, :]
    # streamID_ser = resPolyg_df[resPolyg_df['Strahler'] <= max_strahl]["streamID"]
    # streamIDList = streamID_ser.unique().tolist()
    # digits = len(str(num_subsets))
    colnames = []
    for i in range(num_subsets):
        subset_name = get_name_from_num(i, 0)
        colnames.append(subset_name)
    
    gen0_df = pd.DataFrame(data=0,
    index = gen0_index,
    columns = colnames,
    dtype = "int8")
    # print(gen0_df.head())

    k=0
    # cost_dict = {}
    # floodedArea_dict = {}
    for i in range(num_subsets):
        subset_name = colnames[i]
        # cost = 0
        # floodedArea = 0
        available = list(damIDList)
        selected_damIDs = []
        min_to_select = 2
        if i < math.ceil(num_subsets/4):
            max_to_select = 5
        else:
            max_to_select = math.ceil(len(available)*0.5)
        
        
        num_of_reservoirs = np.random.randint(low=min_to_select, high=max_to_select+1, size=None)  # random num of reservoirs in each subset, min 5, max 10% of all locations
        count_of_reservoirs = 0
        max_number_of_attempts = 10
        attempt = 1
        # while (cost < budget and floodedArea < maxFloodedArea and attempt <= number_of_attempts ):
        while (count_of_reservoirs < num_of_reservoirs and attempt <= max_number_of_attempts and len(available)>0):
            # dam_j = random.sample(range(0,len(available)),1)[0]
            dam_j = np.random.randint(low=0, high=len(available), size=None)
            damID = available[dam_j]
            # stream_j = random.sample(range(0,len(streamIDList)),1)[0]
            # streamID = streamIDList[stream_j]
            # stream_damIDList = resPolyg_df[resPolyg_df['streamID'] == streamID]["damID"].tolist()
            # dam_j = random.sample(range(0,len(stream_damIDList)),1)[0]
            # damID = stream_damIDList[dam_j]
            if damID not in available:
                continue

            # strahler = resPolyg_df.loc[damID, 'Strahler']
            # damID_cost = resPolyg_df.loc[damID, 'cost']
            # damID_area = resPolyg_df.loc[damID, 'AREAmax']
            feasible = True
            if count_of_reservoirs > 0:
                if flooded_table.loc[damID, selected_damIDs].any():
                # for flooded_damID in flooded_table.loc[:, damID].:
                #     if gen0_df.loc[flooded_damID, subset_name] == 1:
                    feasible = False # discard this damID, it is flooding a dam already in the subset
            
            # print(damID, feasible)
            if feasible == False:
                available.remove(damID)
                attempt += 1
                # continue  # to next while loop, new damID random selection
            else:
                gen0_df.loc[damID, subset_name] = 1
                available.remove(damID)
                selected_damIDs.append(damID)
                flooded_damIDs = flooded_table[flooded_table.loc[:,damID] == 1].index.tolist()
                if len(flooded_damIDs) > 0:
                    flooded_damIDs_to_remove = [f for f in flooded_damIDs if f in available]
                    for f in flooded_damIDs_to_remove:
                        available.remove(f)
                # cost += damID_cost
                # floodedArea += damID_area
                count_of_reservoirs += 1
        # cost_dict[subset_name] = cost
        # floodedArea_dict[subset_name] = floodedArea
    
        if flooded_table.loc[selected_damIDs, selected_damIDs].any().any():
            print("subset {} is unfeasible, heur_initialize does not work, FIX IT NOW!!!". format(subset_name))
            break
    return gen0_df
