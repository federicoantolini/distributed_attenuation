'''
runs the NSGA-II optimization
uses the other modules and streamlines the process
'''



import os
# import arcpy
import math
from os.path import join
import subprocess
import time
import random
import copy
import numpy as np
import pandas as pd
import geopandas as gpd
# import pysal as ps

import heur_geospatial as h_geo
import heur_initialize_regions as h_init
import heur_genetic4 as h_gen
# import heur_genetic_7030 as h_gen
# import heur_genetic_3070 as h_gen
# import heur_genetic_5050 as h_gen
# import heur_genetic_3obj as h_gen
import heur_parallelize as h_paral
import heur_lib_plot as h_lp
import remove_files as h_rem



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


def read_peaks(gen_df, runFolder):
    '''
    gen_df: DataFrame, each column is a subset
    reads the run_max.csv files produced by each wflow simulation, Q at checkpoint/outlet at every timestep
    returns a series, index=subset, value=Qpeak
    '''
    q_peak_dict = {}
    for subset_name in gen_df.columns.tolist():
        try:
            run_max_filename = os.path.join(runFolder,"{}".format(subset_name),"run_max_{}.csv".format(subset_name))
            q_df = pd.read_csv(run_max_filename, index_col="# Timestep")
        except:
            run_max_filename = os.path.join(runFolder,"{}".format(subset_name),"run_max.csv")
            q_df = pd.read_csv(run_max_filename, index_col="# Timestep")
        q_df.columns = [int(eval(name)) for name in q_df.columns]
        q_peak = q_df.loc[:, 1].max()
        q_peak_dict[subset_name] = q_peak
    return pd.Series(q_peak_dict, name=str("Q_peak"), dtype=np.float64)



def summarize_simulation_results(gen_df, resPolyg_df, Q0, runFolder, gen_num):
    '''
    gen_df: DataFrame, each column is a subset
    Q0: peak discharge Qpeak in baseline scenario (no reservoirs)
    returns a .csv summarizing Qpeak, Qpeak_reduction, cost for each subset in the generation gen_num
    '''
    q_peak_series = read_peaks(gen_df, runFolder)
    qpeak_cost_df = pd.DataFrame(q_peak_series)
    qpeak_cost_df.index.name = "subsetID"
    qpeak_cost_df["Qpeak_reduction"] = Q0 - qpeak_cost_df["Q_peak"]
    qpeak_cost_df["cost"] = h_geo.get_subsets_costs(gen_df, resPolyg_df)
    qpeak_cost_df["floodedArea"] = h_geo.get_subsets_floodedAreas(gen_df, resPolyg_df)
    qpeak_cost_df.to_csv(os.path.join(runFolder, "gen{}_qpeak_cost.csv".format(gen_num)))
    # print(qpeak_cost_df)


def merge_optimal_solutions(regional_runs, last_optimal_gen_num, num_subsets, current_folder):
    '''
    specific function to combine together the optimal solutions of regional runs into 
    - comb_values_df, a new table of objective values
    - comb_gen_df, a new table of optimal subsets
    '''
    comb_gen_df = None
    comb_values_df = None
    for i in range(len(regional_runs)):
        regional_run_name = regional_runs[i]
        regional_runFolder = os.path.join(current_folder, regional_run_name)
        
        last_gen_df = pd.read_csv(os.path.join(regional_runFolder, "gen{}_subsets.csv".format(last_optimal_gen_num)), index_col="damID")
        last_gen_df.rename(columns=lambda x:regional_run_name[0]+x, inplace=True)
        
        last_values_df = pd.read_csv(os.path.join(regional_runFolder, "gen{}_qpeak_cost_rank.csv".format(last_optimal_gen_num)), index_col="subsetID")
        last_values_df = last_values_df[last_values_df.loc[:, "rank"]==0]
        last_values_df.rename(index=lambda x:regional_run_name[0]+x, inplace=True)

        if type(comb_gen_df) == None:
            comb_gen_df = last_gen_df
        else:
            comb_gen_df = pd.concat([comb_gen_df, last_gen_df], axis=1)
        if type(comb_values_df) == None:
            comb_values_df = last_values_df
        else:
            comb_values_df = pd.concat([comb_values_df, last_values_df], axis=0)
    
    
    comb_values_df.sort_values(by=["rank","cost"], ascending=[True, True], inplace=True)
    comb_values_df["orig_subsetID"] = comb_values_df.index
    optimal_subsetID_list = comb_values_df["orig_subsetID"].tolist()
    comb_gen_df = comb_gen_df.loc[:, optimal_subsetID_list]
    return comb_gen_df, comb_values_df

        
def calcCost(subset, all_df):
    pass

def calcObjVal(subset, all_df, objective):
    '''
    calculates objective value for a subset of reservoirs|
    subset, dict of Series: subset of reservoirs, by Strahler
    all_df, df: data frame of all the reservoirs
    objective, str: the specific variable to calculate
    '''
    # if objective == "vol":
    #     return calcSumVol(subset, all_df)
    # if objective == "area":
    #     return calcSumArea(subset, all_df)


''' name of study area watershed '''
HUC10_watershed = "Volga"
HUC12_watershed = "Hewett"
lowercase_watershed = "hew"

''' 
A generation i is made of parents AND children, i.e. children are NOT the next generation of parents
The algorithm moves to next generation after NSGA-II and the creation of new parents
'''
# ID of the family of runs, i.e. name of the folder where this file is
runID = "RegionD"

# number of subsets in a parents_df or children_df (indicatively there are as many parents as children)
num_subsets = 112   # should be a multiple of core_num

# number of generations to go through with genetic algorithm
num_generations = 21

'''crossover / mutation operations when creating children, e.g. 0.7 means 70% crossover, 30% mutation'''
# crossover_prop = 0.2
# crossover_prop = 0.5
# crossover_prop = 0.8

'''survival rate after decimation operation'''
# decimation_survival_rate = 0.1

''' select reservoirs on "upstream"/"midstream"/"downstream"/"all" region of watershed '''
region = "regionD"

''' select reservoirs on reaches of Strahler order less than or equal to max_strahl '''
max_strahl = 5

''' name of current simulation/run '''
run_name = "regionD"

''' simulation run in minutes (1 timestep = 1 min) '''
timesteps = 100

'''queue name on Argon'''
queue = "UI-MPI"
# queue = "UI"
# queue = "all.q"

''' number of cores used on Argon for parallelization '''
core_num = 56


''' peak discharge Qpeak in baseline scenario (no reservoirs) '''
Q0 = 164.633544921875



'''import info on dams and reservoirs from shapefile into damLine_df dataframe'''
current_folder = os.getcwd()
runFolder = os.path.join(current_folder, run_name)
if not os.path.exists(runFolder):
    print("\nPlease create the run folder manually\n")
    exit()
# damLine_dbf_filename = "damLine2.0_by_Vmax_to_damLength_w_distToOutlet.dbf"
# damLine_shp_filename = "damLine2.0_by_Vmax_to_damLength_w_distToOutlet.shp"
reservoirPolyg_shp_filename = "resPolyg_{}.shp".format(region)
orig_resPolyg_df = gpd.read_file(os.path.join(runFolder, "reservoirs", reservoirPolyg_shp_filename))
orig_resPolyg_df = orig_resPolyg_df.set_index("damID", drop=False)
resPolyg_df = h_geo.clean_resPolyg_df(orig_resPolyg_df)
resPolyg_df.rename(columns={"CChaul_tot": "cost"}, inplace=True)
resPolyg_df.sort_index(axis=0, inplace=True)
# resPolyg_df = resPolyg_df[resPolyg_df['Strahler'] <= max_strahl]

# if region != "all":
#     resPolyg_df = resPolyg_df[resPolyg_df['region'] == region]


''' total budget available'''
# budget = 1000000

'''threshold for flooded area by a subset of reservoirs'''
# maxFloodedArea = 500000


# damIDList = damLine_df.damID.tolist()
# streamIDList = list(set(damLine_df.streamID.tolist()))
# reachIDList = list(set(damLine_df.reachID.tolist()))

'''creates the table of who floods and gets flooded by who; if the table exists, import it'''
# if "flooding_to_flooded.txt" in os.listdir((os.path.join(current_folder, "reservoir_locations"))):
#     flooded_df = pd.read_table(os.path.join(current_folder, "reservoir_locations", "flooding_to_flooded.txt"),
#     index_col="damID",)
#     flooded_ser = flooded_df['flooded_list'].apply(lambda x: eval(x))   # read values as list ['200126', '200127], not as string like "['200126', '200127]"
#     flooded_dict = flooded_ser.to_dict()

# else:    
#     flooded_dict = h_geo.build_floodedDict(os.path.join(current_folder, "reservoir_locations", reservoirPolyg_shp_filename))
#     flooded_ser = pd.Series(flooded_dict, name="damID")
#     flooded_ser.to_csv(os.path.join(current_folder, "reservoir_locations", "flooding_to_flooded.txt"),\
#         sep='\t',
#         header=["flooded_list"],
#         index_label = "damID"
#         )

if "flooding_table.csv" in os.listdir((os.path.join(runFolder, "reservoirs"))):
    flooded_table = h_geo.get_flooded_table(runFolder)
else:
    flooded_table = h_geo.build_flooded_table(os.path.join(runFolder, "reservoirs", reservoirPolyg_shp_filename))
    flooded_table.to_csv(os.path.join(runFolder, "reservoirs", "flooding_table.csv"),
        index_label = "damID"
        )




'''let the fun begin'''
gen_num = 0
'''
parents0_df = h_init.init_gen0(resPolyg_df, 2*num_subsets, runFolder, max_strahl)
parents0_df.to_csv(os.path.join(runFolder, "parents{}_subsets.csv".format(gen_num)))
# print(parents0_df)
# gen0_df = gen0_df.set_index("damID", drop=False)

# Here I create the children of generation zero

children0_df = h_gen.create_children2(parents0_df, num_subsets, resPolyg_df, gen_num, runFolder, crossover_prop)
curr_colnames = children0_df.columns.tolist()
new_colnames = [get_name_from_num(i, gen_num) for i in range(num_subsets, 2*num_subsets)]
new_colnames_dict = dict(zip(curr_colnames, new_colnames))
children0_df.rename(columns=new_colnames_dict, inplace=True)
gen0_df = pd.concat([parents0_df, children0_df], axis=1)
gen0_df.to_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)))

parents0_df.to_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)))
'''

gen0_df = pd.read_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)), index_col="damID")
# immig_df = pd.read_csv(os.path.join(runFolder, "immig{}_subsets.csv".format(gen_num)), index_col="damID")
# gen0_df = immig_df

h_paral.job_setup_and_launch(gen0_df, gen_num, runFolder, lowercase_watershed, timesteps, queue, core_num, 2*num_subsets)
h_rem.remove_useless_files(run_name, gen_num)
summarize_simulation_results(gen0_df, resPolyg_df, Q0, runFolder, gen_num)
# h_geo.subsets_to_SHP(gen0_df, resPolyg_df, runFolder)
print("\n\nGeneration {} concluded!\n\n".format(gen_num))

# values_df = h_gen.get_simulation_results(gen_num, run_name)
# h_gen.print_rank_dist(values_df, gen_num, run_name)



'''
regional_runs = ["up_22apr", "mid_22apr", "down_22apr"]
comb_gen_df, comb_values_df = merge_optimal_solutions(regional_runs, 50, num_subsets, current_folder)
comb_gen_df.to_csv(os.path.join(runFolder, "umd_comb_gen50_subsets.csv"), index_label = "damID")
comb_values_df.to_csv(os.path.join(runFolder, "umd_comb_gen50_values.csv"), index_label = "subsetID")
subsetIDs = comb_values_df.index.tolist()
new_subsetIDs = [get_name_from_num(i, 50) for i in range(len(subsetIDs))]
new_subsetIDs_dict = dict(zip(subsetIDs, new_subsetIDs))
comb_gen_df.rename(columns=new_subsetIDs_dict, inplace=True)
comb_values_df.rename(index=new_subsetIDs_dict, inplace=True)
comb_gen_df.fillna(int(0), inplace=True)
comb_gen_df.to_csv(os.path.join(runFolder, "umd_comb_gen50_subsets_renamed.csv"), index_label = "damID")
comb_values_df.to_csv(os.path.join(runFolder, "umd_comb_gen50_values_renamed.csv"), index_label = "subsetID")
resorted_comb_values_df = h_gen.rankSort_curr_gen(comb_values_df, 50, run_name)
resorted_comb_values_df.to_csv(os.path.join(runFolder, "umd_comb_gen50_values_resorted.csv"), index_label = "subsetID")
ranked_subsetID_list = resorted_comb_values_df.index.tolist()
comb_gen_df = comb_gen_df.loc[:, ranked_subsetID_list]
comb_gen_df.to_csv(os.path.join(runFolder, "gen50_subsets.csv"), index_label = "damID")
'''



for gen_num in range(1, num_generations):
    curr_generation_df = h_gen.create_next_generation(gen_num-1, resPolyg_df, run_name, num_subsets, runFolder)
    summary_filepath = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num-1))
    summary_df = pd.read_csv(summary_filepath, index_col='subsetID')
    h_lp.plot_single_generation(summary_df, runID, run_name, gen_num-1, runFolder)

    curr_generation_df.to_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)))
    # curr_generation_df = pd.read_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)), index_col="damID")
    h_paral.job_setup_and_launch(curr_generation_df, gen_num, runFolder, lowercase_watershed, timesteps, queue, core_num, num_subsets)
    # curr_generation_df = pd.read_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)), index_col="damID")
    summarize_simulation_results(curr_generation_df, resPolyg_df, Q0, runFolder, gen_num)
    h_rem.remove_useless_files(run_name, gen_num)
    # h_geo.subsets_to_SHP(curr_generation_df, resPolyg_df, runFolder)

    if gen_num == num_generations-1:
        values_df = h_gen.get_simulation_results(gen_num, run_name)
        h_gen.print_rank_dist(values_df, gen_num, run_name)
        summary_filepath = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num))
        summary_df = pd.read_csv(summary_filepath, index_col='subsetID')
        h_lp.plot_single_generation(summary_df, runID, run_name, gen_num, runFolder)

    print("\n\nGeneration {} concluded!\n\n".format(gen_num))

''' 
uncomment + run the code below AND comment the code above (from "let the fun begin" keyline) 
if you want to start from a certain generation number or if you want to continue with more generations...
'''
'''
start_gen_num = 11            # USER: SPECIFY NUMBER HERE!
num_generations = 22        # USER: SPECIFY NUMBER HERE!

for gen_num in range(start_gen_num, num_generations):
    curr_generation_df = h_gen.create_next_generation(gen_num-1, resPolyg_df, run_name, num_subsets, runFolder)
    summary_filepath = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num-1))
    summary_df = pd.read_csv(summary_filepath, index_col='subsetID')
    h_lp.plot_single_generation(summary_df, runID, run_name, gen_num-1, runFolder)
    
    curr_generation_df.to_csv(os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num)))
    h_paral.job_setup_and_launch(curr_generation_df, gen_num, runFolder, lowercase_watershed, timesteps, queue, core_num, num_subsets)
    summarize_simulation_results(curr_generation_df, resPolyg_df, Q0, runFolder, gen_num)
    h_geo.subsets_to_SHP(curr_generation_df, resPolyg_df, runFolder)

    if gen_num == num_generations-1:
        values_df = h_gen.get_simulation_results(gen_num, run_name)
        h_gen.print_rank_dist(values_df, gen_num, run_name)
        summary_filepath = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num))
        summary_df = pd.read_csv(summary_filepath, index_col='subsetID')
        h_lp.plot_single_generation(summary_df, runID, run_name, gen_num, runFolder)

    print("\n\nGeneration {} concluded!\n\n".format(gen_num))'''
