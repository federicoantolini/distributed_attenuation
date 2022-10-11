'''
contains all functions using geospatial library
'''


import os
import math
import time
import random
import copy
import numpy as np
import pandas as pd
import geopandas as gpd
# import pysal as ps

from osgeo import gdal
from osgeo import ogr
try:
    from osgeo import osr
except:
    import osr

driver = ogr.GetDriverByName("ESRI Shapefile")
projSR = osr.SpatialReference()
projSR.ImportFromEPSG(26915)
geogSR = osr.SpatialReference()
geogSR.ImportFromEPSG(4326)
gdal.AllRegister()


def addPRJ(ds,sr,folder):
    '''
    adds the .prj file to a newly created shapefile
    ds, GDAL dataset from a shapefile
    sr, spatial reference: of the shapefile, to write out as a prj
    folder: of the shapefile    
    '''
    name = os.path.basename(ds.GetName()) 
    outfile = open(folder+name.replace('.shp','.prj'),'w')
    sr.MorphToESRI()
    outfile.write(sr.ExportToWkt())
    outfile.close()


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


def findFlooded(floodingFeat, reservoirPolyg_shp_filename):
    '''
    returns a list of all the damID flooded by floodingFeat
    '''

    floodedList = []
    flooding_damID = floodingFeat.GetField("damID")
    floodingGeom = floodingFeat.GetGeometryRef().Clone()

    targetResPolyg_ds = driver.Open(reservoirPolyg_shp_filename,0)
    targetResPolyg_lay = targetResPolyg_ds.GetLayer()
    targetFeat = targetResPolyg_lay.GetNextFeature()
    while targetFeat:
        if targetFeat.GetField("damID") == flooding_damID:
            targetFeat = targetResPolyg_lay.GetNextFeature()
            break  #cannot flood dams downstream or on other streams of same Strahler
        targetGeom = targetFeat.GetGeometryRef()
        if targetGeom.Intersect(floodingGeom):
            floodedList.append(targetFeat.GetField("damID"))
        targetFeat = targetResPolyg_lay.GetNextFeature()

    targetResPolyg_ds,targetFeat = None,None
    return floodedList



def build_floodedDict(reservoirPolyg_shp_filename):
    '''
    returns a dict mapping each damID to the damIDs it floods:
    - key is the damID
    - value is a list of all the damIDs flooded by damID in key
    '''

    floodedDict = {}
    reservoirPolyg_ds = driver.Open(reservoirPolyg_shp_filename,0)
    #damLine_ds = driver.open(os.path.join(current_folder, "reservoir_locations", damLine_shp_filename),0)
    reservoirPolyg_lay = reservoirPolyg_ds.GetLayer()
    selectFeat = reservoirPolyg_lay.GetNextFeature()
    while selectFeat:
        damID = selectFeat.GetField("damID")
        flooded_damID_list = findFlooded(selectFeat, reservoirPolyg_shp_filename)
        floodedDict[damID] = flooded_damID_list
        selectFeat = reservoirPolyg_lay.GetNextFeature()
    
    reservoirPolyg_ds, selectFeat = None, None
    return floodedDict



def build_flooded_table(reservoirPolyg_shp_filename):
    '''
    returns a table mapping all damIDs (index) to all damIDs (columns): 
    value 1 if row damID floods column damID or viceversa, 0 if no interaction
    '''
    reservoirPolyg_df = gpd.read_file(reservoirPolyg_shp_filename)
    reservoirPolyg_df = reservoirPolyg_df.set_index("damID", drop=False)

    flooded_table = pd.DataFrame(data=0,
    index=reservoirPolyg_df.index,
    columns=reservoirPolyg_df.index,
    dtype=np.int64)
    flooded_table.index.name = "damID"

    reservoirPolyg_ds = driver.Open(reservoirPolyg_shp_filename,0)
    #damLine_ds = driver.open(os.path.join(current_folder, "reservoir_locations", damLine_shp_filename),0)
    reservoirPolyg_lay = reservoirPolyg_ds.GetLayer()
    selectFeat = reservoirPolyg_lay.GetNextFeature()
    while selectFeat:
        damID = selectFeat.GetField("damID")
        flooded_damID_list = findFlooded(selectFeat, reservoirPolyg_shp_filename)
        flooded_table.loc[damID, flooded_damID_list] = 1
        flooded_table.loc[flooded_damID_list, damID] = 1
        selectFeat = reservoirPolyg_lay.GetNextFeature()
    reservoirPolyg_ds, selectFeat = None, None
    
    return flooded_table
    

def get_flooded_table(runFolder):
    '''
    reads .csv and returns the DataFrame
    '''
    flooded_table = pd.read_csv(os.path.join(runFolder, "reservoirs", "flooding_table.csv"),
        index_col='damID',
        dtype={'damID':int} 
        )
    flooded_table.columns = [int(name) for name in flooded_table.columns]
    return flooded_table



def get_flooded_df():
    '''
    ** DO NOT USE **
    reads .csv and returns the DataFrame.
    It uses the WRONG format of the table. Use get_flooded_table instead
    '''
    
    current_folder = os.getcwd()
    flooded_df = pd.read_csv(os.path.join(current_folder, "reservoir_locations", "flooding_to_flooded.txt"),\
        sep='\t',
        index_col='damID',
        dtype={'damID':int, 'flooded_list':'str'} )
    flooded_df['flooded_list'] = flooded_df['flooded_list'].apply(lambda x: x.strip('[]').split(','))
    # print(flooded_df.tail())
    return flooded_df



def check_feasible_single_dam(subset, new_res):
    '''
    checks that subsets 2 is feasible:
    1) new_res is not flooded by the other reservoirs
    2) new_res does not flood the other reservoirs
    new_res is the index/damID of the newly added reservoir to subset
    '''

    flooded_df = get_flooded_df()
    subset_damID_list = subset.index.to_list()

    for damID in subset_damID_list:
        if new_res in flooded_df.loc[damID,"flooded_list"]:
            return False
        if damID in flooded_df.loc[new_res,"flooded_list"]:
            return False
    return True



def subsets_to_SHP(subsets_df, resPolyg_df, runFolder):
    '''
    for each subset in subset_df, creates a shapefile of reservoirs 
    '''
    num_subsets = subsets_df.shape[1]
    for i in range(num_subsets):
        subset_name = subsets_df.iloc[:, i].name.strip()
        subset_num = get_num_from_name(subset_name) % 10000
        gen_num = get_num_from_name(subset_name) // 10000
        filename = get_name_from_num(subset_num, gen_num)
        mask = subsets_df.iloc[:, i] == 1
        subset_resPolyg_df = resPolyg_df.loc[mask, :]
        subset_resPolyg_df = subset_resPolyg_df.set_index("_FID", drop=True)
        subset_resPolyg_df.to_file(os.path.join(runFolder, "reservoirs_shp", "{}.shp".format(filename)))


def get_subsets_costs(subsets_df, resPolyg_df):
    '''
    each row in subsets_df is a damID; columns are the subsets
    values are 1 if damID is in subset(column), 0 otherwise
    function calculates the costs of each subset
    it returns a cost Series, where each row is a subset, i.e. index = column labels of subsets_df 
    '''
    total_cost_dict = {}
    subset_list = subsets_df.columns.tolist()
    for subset_name in subset_list:
        subset_series = subsets_df[subset_name]
        mask = subset_series == 1
        subset_cost = resPolyg_df.loc[mask, "cost"].sum()
        total_cost_dict[subset_name] = subset_cost
    total_cost_ser = pd.Series(total_cost_dict, name="cost")
    return total_cost_ser



def get_subsets_floodedAreas(subsets_df, resPolyg_df):
    '''
    each row in subsets_df is a damID 
    columns are the subsets
    values are 1 if damID is in subset(column), 0 otherwise
    function calculates the sum of flooded areas behind dams in each subset
    it returns a floodedArea Series, where each row is a subset, i.e. index = subsets_df column names
    '''
    total_cost_dict = {}
    subset_list = subsets_df.columns.tolist()
    for subset_name in subset_list:
        subset_series = subsets_df[subset_name]
        mask = subset_series == 1
        subset_floodedArea = resPolyg_df.loc[mask, "AREAmax"].sum()
        total_cost_dict[subset_name] = subset_floodedArea
    return pd.Series(total_cost_dict, name="AREAmax")



def drop_unused_fields(resPolyg_df):
    '''
    creates a copy of the file
    drops fields that are not used for optimization
    
    ** MODIFY THE FUNCTION TO MAKE IT WORK ** --> what should it return? 
    
    Inefficient, use clean_resPolyg_df instead
    '''
    resPolyg_smalldf = resPolyg_df.copy(deep=True)
    fields_to_drop = ['fr_StaStr', 'to_EndStr', 'fr_StaRea', 'to_EndRea', 'MIvalid', 'Z', 'MaxElev', 'Drainage', 'INFLOW_VOL',
                        'damOrient', 'PROC_CODE', 
                        'VOL_1', 'AREA_1', 'V_A_1','V_LEN_1','V_STO_1',
                        'VOL_2', 'AREA_2', 'V_A_2','V_LEN_2','V_STO_2',
                        'VOL_3', 'AREA_3', 'V_A_3','V_LEN_3','V_STO_3',
                        'VOL_4', 'AREA_4', 'V_A_4','V_LEN_4','V_STO_4',
                        'VOL_5', 'AREA_5', 'V_A_5','V_LEN_5','V_STO_5',
                        'reachWid','B_orif','H_orif','_FID', 'rect_orif_', 
                        'D_orif_inc','D_orif_met','single_cir','num_pipes','tot_circ_o','delta_area;','%_circ_to_',
                        'top_width','base_width','base_wid_1',
                        'damBodyVol','damBodyV_1','damSideVol','damSideV_1','side_to_bo','pipeVolume',
           
                        ]
    pass



def clean_resPolyg_df(resPolyg_df):
    '''
    returns a copy with just fields necessary for optimization
    '''

    resPolyg_smalldf = resPolyg_df[['_FID','HUC10','HUC12','damID','streamID','reachID','Strahler','to_outlet',
    'region','Drainage','damLength','VOLmax','AREAmax','Vmax_STO','maxH','B_orif','H_orif','damVolume','CChaul_tot','geometry']]
    return resPolyg_smalldf



def create_special_subsets(reservoirPolyg_shp_filename, current_folder, runFolder):
    '''
    creates special subsets, selection based on theoretically favorable reservoir properties, less random
    Final .csv must be checked manually:
    1. make sure there is no infeasibility (footprint overalap of selected reservoirs)
    2. change subsets (esp. 5,6,7) to ensure that most reservoirs appear at least once in one of the 8 reservoirs
    3. changing a few reservoirs in subsets 0-4 to help having most reservoirs selected at least once is fine
    '''
    resPolyg_df = gpd.read_file(os.path.join(current_folder, "reservoir_locations", reservoirPolyg_shp_filename))
    resPolyg_df = resPolyg_df.set_index(["streamID", "damID"], drop=False)
    resPolyg_df.rename(columns={"CChaul_tot": "cost"}, inplace=True)

    if "flooding_table.csv" in os.listdir((os.path.join(runFolder, "reservoirs"))):
        flooded_table = get_flooded_table(runFolder)
    else:
        flooded_table = build_flooded_table(os.path.join(runFolder, "reservoirs", reservoirPolyg_shp_filename))
        flooded_table.to_csv(os.path.join(runFolder, "reservoirs", "flooding_table.csv"),
            index_label = "damID"
            )
    if not os.path.exists(os.path.join(current_folder,"special_subsets.csv")):

        resPolyg_df = resPolyg_df.loc[resPolyg_df.loc[:,"region"]=='midstream', :]

        resPolyg_df["cost_to_VOL"] = resPolyg_df["cost"]/resPolyg_df["VOLmax"]
        resPolyg_df["orif_to_inflow"] = resPolyg_df["B_orif"]*resPolyg_df["B_orif"]/resPolyg_df["INFLOW_VOL"]

        resPolyg_index = resPolyg_df.index
        damIDList = resPolyg_index.get_level_values(1).to_list()
        streamIDlist = resPolyg_index.get_level_values(0).to_list()
        colnames = []
        for i in range(8):
            subset_name = "special_{}".format(i)
            colnames.append(subset_name)
        special_df = pd.DataFrame(data=0,
        index = resPolyg_index,
        columns = colnames,
        dtype = "int8")

        for streamID in streamIDlist:
            # special subset 0: most upstream reservoir in each stream
            special_df.loc[streamID,"special_0"].iloc[0] = 1

            # special subset 1: most downstream reservoir in each stream
            special_df.loc[streamID,"special_1"].iloc[-1] = 1

            # special subset 2: reservoir with smallest cost in each stream
            damID_MINcost = resPolyg_df.loc[streamID,:]["cost"].idxmin()
            special_df.loc[(streamID, damID_MINcost), "special_2"] = 1

            # special subset 3: reservoir with minimum cost per volume ratio in each stream
            damID_MINcost_to_VOL = resPolyg_df.loc[streamID,:]["cost_to_VOL"].idxmin()
            special_df.loc[(streamID, damID_MINcost_to_VOL), "special_3"] = 1
            
            # special subset 4: reservoir with minimum orifice section-to-inflow ratio in each stream
            damID_MINorif_to_inflow = resPolyg_df.loc[streamID,:]["orif_to_inflow"].idxmin()
            special_df.loc[(streamID, damID_MINorif_to_inflow), "special_4"] = 1

            # special subset 5, 6, 7: random selection of random number of reservoirs in each stream
            damIDs_on_stream = resPolyg_df.loc[(streamID,),"damID"].tolist()
            num_of_damIDs_on_stream = len(damIDs_on_stream)
            for i in range(5,8):          
                numOfRes_to_select = np.random.randint(0,num_of_damIDs_on_stream+1)
                selected_damIDs = np.random.choice(damIDs_on_stream, numOfRes_to_select, replace=False).tolist()
                if len(selected_damIDs) > 0:
                    special_df.loc[(streamID, selected_damIDs), "special_{}".format(i)] = 1
                    streamID_flooded_table = flooded_table.loc[selected_damIDs, selected_damIDs]  # flooded table reduced to selected reservoirs
                    # check feasibility of subset
                    while streamID_flooded_table.any(axis=None):
                        # fix the subset manually: I noticed problems in this loop, it is not fixing all the overlapping damIDs
                        flooded_damIDs = streamID_flooded_table.loc[streamID_flooded_table.any(axis=1),:].index.tolist()
                        # col_damIDs = streamID_flooded_table.loc[:, streamID_flooded_table.any(axis=0)].columns.tolist()
                        to_remove = random.choice(flooded_damIDs)
                        special_df.loc[(streamID,to_remove), "special_{}".format(i)] = 0
                        selected_damIDs.remove(to_remove)
                        streamID_flooded_table = flooded_table.loc[selected_damIDs, selected_damIDs]

        special_df.to_csv(os.path.join(current_folder,"special_subsets.csv"))
    else:
        print("special_df esiste gia!")
        special_df = pd.read_csv(os.path.join(current_folder,"special_subsets.csv"))
        special_df = special_df.set_index(["streamID", "damID"], drop=False)
    return special_df



def find_duplicates_in_special(special_df, run_name):
    '''
    checks feasibility of all reservoirs
    Fix infeasibilities MANUALLY!!
    modify 1s and 0s in special_df .csv, save the .csv, and launch this function again, until all conflicts are solved
    '''
    run_folder = os.path.join(os.getcwd(), run_name)
    # let's check feasibility of 8 special subsets... The following could be changed, just gives output to help fix manually
    flooded_table = get_flooded_table(run_folder)
    for i in range(8):
        subset = special_df.loc[:,"special_{}".format(i)]
        subset_damIDs = subset[subset == 1].index.get_level_values(1).tolist()
        subset_flooded_table = flooded_table.loc[subset_damIDs, subset_damIDs]
        if subset_flooded_table.any(axis=None):
            print("special_{} is not feasible".format(i))
            flooded_damIDs = subset_flooded_table.loc[subset_flooded_table.any(axis=1),:].index.tolist()
            print("conflicting damIDs are {}\n".format(flooded_damIDs))
        else:
            print("\nspecial_{} is FEASIBLE\n".format(i))

    # special_df.to_csv(os.path.join(current_folder,"special_subsets_fixed.csv"))

# current_folder = os.getcwd()
# reservoirPolyg_shp_filename = "reservoirPolygon2.0_by_Vmax_to_damLength_design_cost.shp"
# create_special_subsets(reservoirPolyg_shp_filename, current_folder)




    
