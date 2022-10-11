'''
define and run crossover and mutation functions
classify subsets by dominance level
sort within dominance by crowding distance
create the next generation of subsets

'''

import os
# import arcpy
import math
import time
import random
import copy
import numpy as np
import pandas as pd
import geopandas as gpd
# import pysal as ps

import heur_geospatial as h_geo
import heur_initialize as h_init


#sorting functions
def quickSort(thisList,low,high):
    i,j = low,high
    mid = (high+low)/2
    pivot = thisList[mid][1]
    while (i <= j):
        while thisList[i][1] < pivot :
            i+=1
        while thisList[j][1] > pivot :
            j-=1
        if i < j :
            a = thisList[i]
            thisList[i] = thisList[j]
            thisList[j] = a
            i+=1
            j-=1
        if (i == j) :
            i+=1
            j-=1
    if low < j:
        quickSort(thisList,low,j)
    if i < high :
        quickSort(thisList,i, high)


def decr_quickSort(thisList,low,high):
    i,j = low,high
    mid = (high+low)/2
    pivot = thisList[mid][1]
    while (i <= j):
        while thisList[i][1] > pivot :
            i+=1
        while thisList[j][1] < pivot :
            j-=1
        if i < j :
            a = thisList[i]
            thisList[i] = thisList[j]
            thisList[j] = a
            i+=1
            j-=1
        if (i == j) :
            i+=1
            j-=1
    if low < j:
        quickSort(thisList,low,j)
    if i < high :
        quickSort(thisList,i, high)


def quickSortDams(thisList,low,high):
    i,j = low,high
    mid = (high+low)/2
    pivot = thisList[mid]
    while (i <= j):
        while thisList[i] < pivot :
            i+=1
        while thisList[j] > pivot :
            j-=1
        if i < j :
            a = thisList[i]
            thisList[i] = thisList[j]
            thisList[j] = a
            i+=1
            j-=1
        if (i == j) :
            i+=1
            j-=1
    if low < j:
        quickSortDams(thisList,low,j)
    if i < high :
        quickSortDams(thisList,i, high)


def mergeSort(thisList,low,high):
    if low == high:
        return [thisList[low]]
    if low == high-1:
        if thisList[low] > thisList[high]:
            return [thisList[high],thisList[low]]
        else:
            return [thisList[low], thisList[high]]
    else:
        mid = (low+high)/2
        mergeSort(thisList,low,mid)
        mergeSort(thisList,mid+1, high)


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



def get_curr_generation_subsets(gen_num, run_name):
    '''
    read csv of subsets of a generation
    each row is a damID 
    columns are subsets
    values are 1 if damID is in subset(column), 0 otherwise
    '''

    current_folder = os.getcwd()
    generation_csv_filename = os.path.join(current_folder, run_name, "gen{}_subsets.csv".format(gen_num))
    generation_subsets_df = pd.read_csv(generation_csv_filename, \
        # names=["damID"]+next_parents_list, 
        index_col="damID", 
        # usecols=["damID"]+next_parents_list
        )
    return generation_subsets_df


def get_specials_df(run_name):
    '''
    read .csv of special subsets and returns a DataFrame
    each row is a damID
    columns are subsets
    values are 1 if damID is in subset(column), 0 otherwise
    '''
    current_folder = os.getcwd()
    special_subsets_filename = os.path.join(current_folder, run_name, "special_subsets.csv")
    special_subsets_df = pd.read_csv(special_subsets_filename, \
        # names=["damID"]+next_parents_list, 
        index_col=["streamID", "damID"], 
        # usecols=["damID"]+next_parents_list
        )
    return special_subsets_df


def fix_unfeasible_after_crossover(subsets, crossover_damID, runFolder):
    '''
    checks that subsets are feasible:
    uses the flooding table to determine if damIDs before crossover flood/are flooded by damIDs after crossover
    to fix infeasibility from flooding, switch off either damIDs before or after crossover point
    returns fixed subsets, or original subsets if they were already feasible
    '''

    flooded_table = h_geo.get_flooded_table(runFolder)
    compressed_subsets = subsets[subsets.any(axis=1)]   # only keep damIDs in at least one of parents
   
    check = False
    subset_names = subsets.columns.tolist()
    for subset_name in subset_names:
        # damID_list = subsets.index.to_list()
        before_crossover_damID_list = compressed_subsets.loc[:crossover_damID, subset_name].index.to_list()
        after_crossover_damID_list = compressed_subsets.loc[crossover_damID:, subset_name].index.to_list()
        subset_flooded_table = flooded_table.loc[before_crossover_damID_list, after_crossover_damID_list]
        while subset_flooded_table.any().any():
            # if subset_flooded_table.any(axis=None):
            # fix the subset
            row_damIDs = subset_flooded_table.loc[subset_flooded_table.any(axis=1),:].index.tolist()
            col_damIDs = subset_flooded_table.loc[:, subset_flooded_table.any(axis=0)].columns.tolist()
            damID_to_remove = random.choice(random.choice([row_damIDs, col_damIDs]))
            subsets.loc[damID_to_remove, subset_name] = 0
            if damID_to_remove in before_crossover_damID_list:
                before_crossover_damID_list.remove(damID_to_remove)
            else:
                after_crossover_damID_list.remove(damID_to_remove)
            subset_flooded_table = flooded_table.loc[before_crossover_damID_list, after_crossover_damID_list]

    return subsets



def fix_unfeasible_after_crossover_swapOnStream(subsets, crossover_damIDs, runFolder):
    '''
    checks that subsets are feasible:
    crossover damIDs are damIDs on crossover streamID
    uses the flooding table to determine if active crossover damIDs flood/are flooded by other damIDs in the subset
    to fix infeasibility from flooding, switch off either the damID on the crossover streamID or the other
    returns fixed subsets, or original subsets if they were already feasible
    '''

    flooded_table = h_geo.get_flooded_table(runFolder)
    compressed_subsets = subsets[subsets.any(axis=1)]   # only keep damIDs in at least one of parents
   
    check = False
    subset_names = subsets.columns.tolist()
    for subset_name in subset_names:
        crossover_damID_list = crossover_damIDs
        non_crossover_damID_list = compressed_subsets.loc[~compressed_subsets.index.isin(crossover_damIDs), subset_name].index.tolist()
        subset_flooded_table = flooded_table.loc[crossover_damID_list, non_crossover_damID_list]
        while subset_flooded_table.any().any():
            # fix the subset
            row_damIDs = subset_flooded_table.loc[subset_flooded_table.any(axis=1),:].index.tolist()
            col_damIDs = subset_flooded_table.loc[:, subset_flooded_table.any(axis=0)].columns.tolist()
            damID_to_remove = random.choice(random.choice([row_damIDs, col_damIDs]))
            subsets.loc[damID_to_remove, subset_name] = 0
            if damID_to_remove in crossover_damID_list:
                crossover_damID_list.remove(damID_to_remove)
            else:
                non_crossover_damID_list.remove(damID_to_remove)
            subset_flooded_table = flooded_table.loc[crossover_damID_list, non_crossover_damID_list]

    return subsets


def fix_child_from_special(child, runFolder):
    '''
    recursively eliminates reservoirs that flood/get flooded by other reservoirs in the subset
    until no conflict exists and the subset is feasible
    '''
    flooded_table = h_geo.get_flooded_table(runFolder)
    compressed_child = child[child==1]   # only keep damIDs in at least one of parents
    subset_flooded_table = flooded_table.loc[compressed_child.index.tolist(), compressed_child.index.tolist()]
    while subset_flooded_table.any().any():
        row_damIDs = subset_flooded_table.loc[subset_flooded_table.any(axis=1),:].index.tolist()
        to_remove = random.choice(row_damIDs)
        child.loc[to_remove] = 0
        compressed_child = child.loc[child==1]
        subset_flooded_table = flooded_table.loc[compressed_child.index.tolist(), compressed_child.index.tolist()]
    return child


def check_feasible(subset, new_damID_list, runFolder):
    '''
    checks that subsets 2 is feasible:
    1) new_res is not flooded by the other reservoirs
    2) new_res does not flood the other reservoirs
    new_damID_list is the list of index/damID recently added to subset
    '''
    if len(new_damID_list) == 1:
        new_damID_list = new_damID_list[0]

    flooded_table = h_geo.get_flooded_table(runFolder)
    subset_damID_list = subset[subset==1].index.tolist()

    if flooded_table.loc[subset_damID_list, new_damID_list].any():
        return False

    return True


def df_non_dominated_sorting_algorithm(pooled_df):
    '''
    in pooled_df:
    - index is subsetID, ID of subset/solution
    - column "Qpeak_reduction"
    - column "cost"
    
    solution A dominates B if both obj values of A are better than B's
    function identifies all dominations relationships, classifies solutions into fronts, adds a "rank" column
    fronts are ranked from 0 (optimal) to worst
    fronts are lists of solutions, which are actually their index in qpeak_red and costs lists
    initial df with rank column is returned as result
    '''

    index_list = pooled_df.index.tolist()
    # S=[[] for i in range(qpeak_red.size)]  # list of lists; list w/ index i contains indices of sol dominated by solution w/ index i
    S = {}
    # fronts = {0:[]} # dict of frontiers/ranks, optimal has index 0, worst have max index
    pooled_df.loc[:,'n'] = 0  # num of solutions dominating solution w/ index i
    pooled_df.loc[:,'rank'] = -1 #solution rank based on frontier of belonging

    # determine the relationship of domination between any pair of solutions
    # domination does not exist for every pair: A can be better than B for value1, but not for value2... 
    # puts the dominated in S[p] and the number of dominating in n[p]
    # populate optimal front[0] w non-dominated (only populated frontier for now)
    for p in index_list:  # loop through solutions
        S[p]=[]  # initialize list in position p as empty list
    for i in range(len(index_list)-1):
        p = index_list[i]  # loop through solutions
        for j in range(i+1, len(index_list)):  # nested loop through solutions again
            q = index_list[j]
            # if p superior to q, q dominated
            if (pooled_df.loc[p,"Qpeak_reduction"] > pooled_df.loc[q,"Qpeak_reduction"] and pooled_df.loc[p,"cost"] <= pooled_df.loc[q,"cost"]) or \
                (pooled_df.loc[p,"Qpeak_reduction"] >= pooled_df.loc[q,"Qpeak_reduction"] and pooled_df.loc[p,"cost"] < pooled_df.loc[q,"cost"]):  
                if q not in S[p]:
                    S[p].append(q)  # S[p] is list of solutions dominated by p
                pooled_df.loc[q,'n'] += 1  # increase the n of q, number of solutions dominating q
            # elif q superior to p, p dominated
            elif (pooled_df.loc[q,"Qpeak_reduction"] > pooled_df.loc[p,"Qpeak_reduction"] and pooled_df.loc[q,"cost"] <= pooled_df.loc[p,"cost"]) or \
                (pooled_df.loc[q,"Qpeak_reduction"] >= pooled_df.loc[p,"Qpeak_reduction"] and pooled_df.loc[q,"cost"] < pooled_df.loc[p,"cost"]):
                if p not in S[q]:
                    S[q].append(p)  # S[q] is list of solutions dominated by q
                pooled_df.loc[p,'n'] += 1  # increase the n of p, number of solutions dominating p
    pooled_df.loc[pooled_df.loc[:,'n'] == 0,'rank'] = 0 # to all not dominated solutions, assign rank 0
    
    curr_rank = 0  # rank currently considered
    # print("\nstart ranking\n")
    ranked = pooled_df[pooled_df['rank']==0].index.tolist()
    while(len(ranked) < pooled_df.shape[0]):  # looping through frontiers/ranks, from optimal to worst
        current_frontier = pooled_df[pooled_df['rank']==curr_rank].index.tolist()  # list of solutions w/ rank curr_rank
        # print(current_frontier)
        for p in current_frontier: # looping through solutions of rank curr_rank (non-dominated solutions if rank=i=0)
            for q in S[p]: # looping through sol dominated by p 
                pooled_df.loc[q,'n'] -= 1  # take 1 off for each solution dominating q
                if(pooled_df.loc[q,'n']==0):  # e.g., if q dominated only by rank-0 sol, then rank of q is 0+1
                    pooled_df.loc[q,'rank'] = curr_rank+1
                    if q not in ranked:
                        ranked.append(q)
        curr_rank+=1          # move on to curr_rank+1
    print("done with df_non_dominated_sorting_algorithm")
    return pooled_df



def df_non_dominated_sorting_algorithm_3obj(pooled_df):
    '''
    ** NOT USED **
    
    in pooled_df:
    - index is subsetID, ID of subset/solution
    - column "Qpeak_reduction"
    - column "cost"
    - column "floodedArea"
    
    solution A dominates B if both obj values of A are better than B's
    function identifies all dominations relationships, classifies solutions into fronts, adds a "rank" column
    fronts are ranked from 0 (optimal) to worst
    fronts are lists of solutions, which are actually their index in qpeak_red and costs lists
    initial df with rank column is returned as result
    '''

    index_list = pooled_df.index.tolist()
    # S=[[] for i in range(qpeak_red.size)]  # list of lists; list w/ index i contains indices of sol dominated by solution w/ index i
    S = {}
    # fronts = {0:[]} # dict of frontiers/ranks, optimal has index 0, worst have max index
    pooled_df.loc[:,'n'] = 0  # num of solutions dominating solution w/ index i
    pooled_df.loc[:,'rank'] = -1 #solution rank based on frontier of belonging

    # determine the relationship of domination between any pair of solutions
    # domination does not exist for every pair: A can be better than B for value1, but not for value2...
    # puts the dominated in S[p] and the number of dominating in n[p]
    # populate optimal front[0] w non-dominated (only populated frontier for now)
    for p in index_list:  # loop through solutions
        S[p]=[]  # initialize list in position p as empty list
    for i in range(len(index_list)-1): # loop through solutions
        p = index_list[i]
        for j in range(i+1, len(index_list)):  # nested loop through solutions again
            q = index_list[j]
            # if p superior to q, q dominated
            if (pooled_df.loc[p,"Qpeak_reduction"] > pooled_df.loc[q,"Qpeak_reduction"] and pooled_df.loc[p,"cost"] <= pooled_df.loc[q,"cost"] and pooled_df.loc[p,"floodedArea"] <= pooled_df.loc[q,"floodedArea"]) or \
                (pooled_df.loc[p,"Qpeak_reduction"] >= pooled_df.loc[q,"Qpeak_reduction"] and pooled_df.loc[p,"cost"] < pooled_df.loc[q,"cost"] and pooled_df.loc[p,"floodedArea"] < pooled_df.loc[q,"floodedArea"]):  
                if q not in S[p]:
                    S[p].append(q)  # S[p] is list of solutions dominated by p
                pooled_df.loc[q,'n'] += 1  # increase the n of q, number of solutions dominating q
            # elif q superior to p, p dominated
            elif (pooled_df.loc[q,"Qpeak_reduction"] > pooled_df.loc[p,"Qpeak_reduction"] and pooled_df.loc[q,"cost"] <= pooled_df.loc[p,"cost"] and pooled_df.loc[q,"floodedArea"] <= pooled_df.loc[p,"floodedArea"]) or \
                (pooled_df.loc[q,"Qpeak_reduction"] >= pooled_df.loc[p,"Qpeak_reduction"] and pooled_df.loc[q,"cost"] < pooled_df.loc[p,"cost"] and pooled_df.loc[q,"floodedArea"] < pooled_df.loc[p,"floodedArea"]):
                if p not in S[q]:
                    S[q].append(p)  # S[q] is list of solutions dominated by q
                pooled_df.loc[p,'n'] += 1  # increase the n of p, number of solutions dominating p
    pooled_df.loc[pooled_df.loc[:,'n'] == 0,'rank'] = 0 # to all not dominated solutions, assign rank 0

    curr_rank = 0  # is rank currently considered
    ranked = pooled_df[pooled_df['rank']==0].index.tolist()
    while(len(ranked) < pooled_df.shape[0]):  # looping through frontiers/ranks, from optimal to worst
        current_frontier = pooled_df[pooled_df['rank']==curr_rank].index.tolist()  # list of solutions w/ rank curr_rank 
        for p in current_frontier: # looping through solutions of rank curr_rank (non-dominated solutions if curr_rank=0)
            for q in S[p]: # looping through sol dominated by p 
                pooled_df.loc[q,'n'] -= 1  # take 1 off for each solution dominating q
                if(pooled_df.loc[q,'n']==0):  # if q is dominated only by rank-0 sol, then rank of q is 0+1
                    pooled_df.loc[q,'rank'] = curr_rank+1
                    if q not in ranked:  
                        ranked.append(q)
        curr_rank += 1          # move on to rcurr_rank+1
    return pooled_df



def df_crowding_distance(pooled_df):
    '''
    in pooled_df:
    - index works as solution ID
    - column "Qpeak_reduction"
    - column "cost"
    
    qpeak_red and costs are Series of obj values of solutions w/ same index
    ranks is a Series of the rank of the frontier to which solutions belong to (0, 1, 2, etc)
    index is the same for all 3 Series, and works as solution ID
    '''
    pooled_df.loc[:,"distance"] = 0
    pooled_df["subsetID"] = pooled_df.index
    pooled_df["subsetID"] = pooled_df["subsetID"].apply(get_num_from_name)
    
    extreme_subsetID_list = [] #list of subsetIDs with max and min Qpeak_reduction and cost, within each rank
    # pivot the df, then add to above list the first and last subsetID in each rank column
    # during pivoting, values of new index (and of new columns) are automatically sorted in ascending order
    pivot_pooled_df = pooled_df.pivot(columns='rank', index='cost', values="subsetID")
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[0] for subsetID in pivot_pooled_df.columns])
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[-1] for subsetID in pivot_pooled_df.columns])
    pivot_pooled_df = pooled_df.pivot(columns='rank', index='Qpeak_reduction', values="subsetID")
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[0] for subsetID in pivot_pooled_df.columns])
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[-1] for subsetID in pivot_pooled_df.columns])
    extreme_subset_name_list = []
    extreme_subset_name_list = [get_name_from_num(subsetID % 10000, subsetID // 10000) for subsetID in extreme_subsetID_list]
    pooled_df.loc[extreme_subset_name_list, "distance"] = math.inf  # assign high dist, we want to keep diverse solutions

    # sort by rank, then by qpeak_red/cost, min to max
    sort_by_qpeak_red_df = pooled_df.copy(deep=True)
    sort_by_qpeak_red_df.sort_values(by=["rank","Qpeak_reduction"], ascending=[True,False], inplace=True)
    sort_by_cost_df = pooled_df.copy(deep=True)
    sort_by_cost_df.sort_values(by=["rank","cost"], ascending=True, inplace=True)

    range_qpeak_red = pooled_df["Qpeak_reduction"].max() - pooled_df["Qpeak_reduction"].min()
    range_costs = pooled_df["cost"].max() - pooled_df["cost"].min()

    max_rank = pooled_df["rank"].max()
    for rank in range(max_rank+1):
        change_dist_df = sort_by_qpeak_red_df[sort_by_qpeak_red_df["rank"]==rank]
        change_dist_df = change_dist_df[change_dist_df["distance"]==0]
        change_dist_index = change_dist_df.index
        sort_by_qpeak_red_df.loc[change_dist_index,"distance"] += \
            (sort_by_qpeak_red_df.shift(-1)["Qpeak_reduction"] - \
                sort_by_qpeak_red_df.shift(1)["Qpeak_reduction"]) / \
                    range_qpeak_red
        sort_by_qpeak_red_df["distance"].where(~np.isnan(sort_by_qpeak_red_df["distance"]),math.inf, inplace=True)
        sort_by_qpeak_red_df["distance"].where(sort_by_qpeak_red_df["distance"] > 0, -sort_by_qpeak_red_df["distance"], inplace=True)
        
        change_dist_df = sort_by_cost_df[sort_by_cost_df["rank"]==rank]
        change_dist_df = change_dist_df[change_dist_df["distance"]==0]
        change_dist_index = change_dist_df.index
        sort_by_cost_df.loc[change_dist_index,"distance"] += \
            (sort_by_cost_df.shift(-1)["cost"] - \
                sort_by_cost_df.shift(1)["cost"]) / \
                    range_costs
        sort_by_cost_df["distance"].where(~np.isnan(sort_by_cost_df["distance"]), math.inf, inplace=True)
        sort_by_cost_df["distance"].where(sort_by_cost_df["distance"] > 0, -sort_by_cost_df["distance"], inplace=True)
    
    pooled_df["distance"] = sort_by_qpeak_red_df["distance"] + sort_by_cost_df["distance"]
    # print(pooled_df)
    return pooled_df

    
   
def df_crowding_distance_3obj(pooled_df):
    '''
    ** NOT USED **
    
    in pooled_df:
    - index works as solution ID
    - column "Qpeak_reduction"
    - column "cost"
    - column "floodedArea"
    
    qpeak_red, costs and floodedAreas are Series of obj values of solutions w/ same index
    ranks is a Series of the rank of the frontier to which solutions belong to (0, 1, 2, etc)
    index is the same for all 3 Series, and works as solution ID
    '''
    pooled_df["distance"] = 0
    pooled_df["subsetID"] = pd. Series(pooled_df.index)

    extreme_subsetID_list = [] #list of subsetIDs with max and min Qpeak_reduction, cost and floodedArea, within each rank
    # pivot the df, then add to above list the first and last subsetID in each rank column
    # during pivoting, values of new index (and of new columns) are automatically sorted in ascending order
    pivot_pooled_df = pooled_df.pivot(columns='rank', index='cost', values="subsetID")
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[0] for subsetID in pivot_pooled_df.columns])
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[-1] for subsetID in pivot_pooled_df.columns])
    pivot_pooled_df = pooled_df.pivot(columns='rank', index='Qpeak_reduction', values="subsetID")
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[0] for subsetID in pivot_pooled_df.columns])
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[-1] for subsetID in pivot_pooled_df.columns])
    pivot_pooled_df = pooled_df.pivot(columns='rank', index='floodedArea', values="subsetID")
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[0] for subsetID in pivot_pooled_df.columns])
    extreme_subsetID_list += ([pivot_pooled_df.loc[:,subsetID][~np.isnan(pivot_pooled_df.loc[:,subsetID])].iloc[-1] for subsetID in pivot_pooled_df.columns])
    pooled_df.loc[extreme_subsetID_list, "distance"] = math.inf  # assign high dist, we want to keep diverse solutions

    # sort by rank, then by qpeak_red/cost, min to max
    sort_by_qpeak_red_df = pooled_df.copy(deep=True)
    sort_by_qpeak_red_df.sort_values(by=["rank","Qpeak_reduction"], ascending=[True,False], inplace=True)
    sort_by_cost_df = pooled_df.copy(deep=True)
    sort_by_cost_df.sort_values(by=["rank","cost"], ascending=True, inplace=True)
    sort_by_floodedArea_df = pooled_df.copy(deep=True)
    sort_by_floodedArea_df.sort_values(by=["rank","floodedArea"], ascending=True, inplace=True)

    range_qpeak_red = pooled_df["Qpeak_reduction"].max() - pooled_df["Qpeak_reduction"].min()
    range_costs = pooled_df["cost"].max() - pooled_df["cost"].min()
    range_floodedAreas = pooled_df["floodedArea"].max() - pooled_df["floodedArea"].min()

    max_rank = pooled_df["rank"].max()
    for rank in range(max_rank+1):
        change_dist_df = sort_by_qpeak_red_df[sort_by_qpeak_red_df["rank"]==rank]
        change_dist_df = change_dist_df[change_dist_df["distance"]==0]
        change_dist_index = change_dist_df.index
        sort_by_qpeak_red_df.loc[change_dist_index,"distance"] += \
            (sort_by_qpeak_red_df.shift(-1)["Qpeak_reduction"] - \
                sort_by_qpeak_red_df.shift(1)["Qpeak_reduction"]) / \
                    range_qpeak_red
        sort_by_qpeak_red_df["distance"].where(~np.isnan(sort_by_qpeak_red_df["distance"]),math.inf, inplace=True)
        sort_by_qpeak_red_df["distance"].where(sort_by_qpeak_red_df["distance"] > 0, -sort_by_qpeak_red_df["distance"], inplace=True)
        
        change_dist_df = sort_by_cost_df[sort_by_cost_df["rank"]==rank]
        change_dist_df = change_dist_df[change_dist_df["distance"]==0]
        change_dist_index = change_dist_df.index
        sort_by_cost_df.loc[change_dist_index,"distance"] += \
            (sort_by_cost_df.shift(-1)["cost"] - \
                sort_by_cost_df.shift(1)["cost"]) / \
                    range_costs
        sort_by_cost_df["distance"].where(~np.isnan(sort_by_cost_df["distance"]), math.inf, inplace=True)
        sort_by_cost_df["distance"].where(sort_by_cost_df["distance"] > 0, -sort_by_cost_df["distance"], inplace=True)

        change_dist_df = sort_by_floodedArea_df[sort_by_floodedArea_df["rank"]==rank]
        change_dist_df = change_dist_df[change_dist_df["distance"]==0]
        change_dist_index = change_dist_df.index
        sort_by_floodedArea_df.loc[change_dist_index,"distance"] += \
            (sort_by_floodedArea_df.shift(-1)["floodedArea"] - \
                sort_by_floodedArea_df.shift(1)["floodedArea"]) / \
                    range_costs
        sort_by_floodedArea_df["distance"].where(~np.isnan(sort_by_floodedArea_df["distance"]), math.inf, inplace=True)
        sort_by_floodedArea_df["distance"].where(sort_by_floodedArea_df["distance"] > 0, -sort_by_floodedArea_df["distance"], inplace=True)
    
    pooled_df["distance"] = sort_by_qpeak_red_df["distance"] + sort_by_cost_df["distance"] + sort_by_floodedArea_df["distance"]
    # print(pooled_df)
    return pooled_df



def create_next_parent_values(values_df, gen_num, run_name):
    '''
    parents and children as DataFrame with same nrows, ncols
    indices are in continuity, i.e. index of first child = index of last parent+1
    pool together by concatenation
    rank by domination and sort by crowding distance
    better half of pooled ranked&sorted solutions is the parents DataFrame of the next generation
    # remember to assign an index to children in continuity with parents, so don't need to create j_index and 
    # can concatenate w/o keys
    '''

    # parents and children are already pooled together
    p_c_pooled_df = values_df.copy(deep=True)   
    # assign ranks to solutions based on domination relationships
    p_c_pooled_df = df_non_dominated_sorting_algorithm(p_c_pooled_df)
    # calculate and assign crowding distance within each frontier/rank 
    p_c_pooled_df = df_crowding_distance(p_c_pooled_df)

    # sort by rank (min to max) and by crowding dist (max to min) and return the better half
    p_c_pooled_df.sort_values(by=["rank","distance"], ascending=[True, False], inplace=True) 
    print("\nsorted by rank and then by distance")
    print(p_c_pooled_df)
    qpeak_reduction_min_threshold = 0.1 * p_c_pooled_df["Qpeak_reduction"].max()
    next_parents = p_c_pooled_df[p_c_pooled_df["Qpeak_reduction"] > qpeak_reduction_min_threshold]

    # before passing the best half to next gen, export current gen values, rank and dist to a .csv
    values_df['rank'] = p_c_pooled_df['rank']
    values_df['distance'] = p_c_pooled_df['distance']
    values_df.sort_values(by=["rank","cost"], ascending=[True, True], inplace=True)
    # values_df.set_index(["rank","distance"], append=True, inplace=True)
    values_df.to_csv(os.path.join(run_name, "gen{}_qpeak_cost_rank.csv".format(gen_num)))
    
    # now pass the best half to next gen
    num_of_solutions = p_c_pooled_df.shape[0]
    return next_parents.iloc[:int(num_of_solutions/2), :]
    # return p_c_pooled_df.iloc[:int(num_of_solutions/2), :]



def create_decimated_next_parent_values(values_df, gen_num, run_name, decimation_survival_rate):
    '''
    rank by domination and sort by crowding distance
    select solutions by decimation
    those are the parents DataFrame of the next generation
    '''
    
    surviving_index = int(1/decimation_survival_rate)
    # parents and children are already pooled together
    p_c_pooled_df = values_df.copy(deep=True)
    # assign ranks to solutions based on domination relationships
    p_c_pooled_df = df_non_dominated_sorting_algorithm(p_c_pooled_df)
    # calculate and assign crowding distance within each frontier/rank 
    p_c_pooled_df = df_crowding_distance(p_c_pooled_df)

    # sort by rank (min to max) and by crowding dist (max to min) and return the better half
    p_c_pooled_df.sort_values(by=["rank","distance"], ascending=[True, False], inplace=True) 
    print("\nsorted by rank and then by distance")
    print(p_c_pooled_df)
    next_parents = p_c_pooled_df.iloc[:10, :]
    remaining_parents_df = p_c_pooled_df.iloc[10:, :]
    remaining_parents_df.sort_values(by=["rank","cost"], ascending=[True, True], inplace=True) 
    remaining_parents_list = remaining_parents_df.index.tolist()
    surviving_parents_list = []
    for i in range(len(remaining_parents_list)):
        if i % surviving_index == 0:
            surviving_parents_list.append(remaining_parents_list[i])
    survived_parents = p_c_pooled_df.loc[surviving_parents_list,:]
    next_parents = pd.concat([next_parents, survived_parents], axis=0)

    # before passing the surviving parents to next gen, export current gen values, rank and dist to a .csv
    values_df['rank'] = p_c_pooled_df['rank']
    values_df['distance'] = p_c_pooled_df['distance']
    values_df.sort_values(by=["rank","cost"], ascending=[True, True], inplace=True)
    # values_df.set_index(["rank","distance"], append=True, inplace=True)
    values_df.to_csv(os.path.join(run_name, "gen{}_qpeak_cost_rank.csv".format(gen_num)))
    
    return next_parents



def print_rank_dist(values_df, gen_num, run_name):
    '''
    function to assign rank and distance to the final generation of solution
    rank by domination and sort by crowding distance
    '''
    # assign ranks to solutions based on domination relationships
    values_df = df_non_dominated_sorting_algorithm(values_df)
    # calculate and assign crowding distance within each frontier/rank 
    values_df = df_crowding_distance(values_df)

    # sort by rank (min to max) and by crowding dist (max to min) and return the better half
    values_df.sort_values(by=["rank","cost"], ascending=[True, True], inplace=True)
    print("\nsorted by rank and then by cost")
    print(values_df)  
    # values_df.set_index(["rank","distance"], append=True, inplace=True)
    values_df.to_csv(os.path.join(run_name, "gen{}_qpeak_cost_rank.csv".format(gen_num)))
    return


def crossover(parents, resPolyg_df, runFolder):
    '''
    single-point crossover

    parents is a DataFrame of two solutions/subsets to crossover to generate a child
    function returns the child, a feasible subset of type Series 
    
    find crossover damID
    child_1 = parent_1 (before crossover)  AND  parent_2 (after crossover)
    child_2 = parent_2 (before crossover)  AND  parent_1 (after crossover)
    '''

    compressed_parents = parents[parents.any(axis=1)]   # only keep damIDs in at least one of parents
    compressed_nrows = compressed_parents.shape[0]      # num of damIDs involved
    children = parents.copy(deep=True)
    parents_names = parents.columns.tolist()
    # print("parents_names {}".format(parents_names))

    crossover_index = np.random.randint(1,compressed_nrows) 
    crossover_damID = compressed_parents.iloc[crossover_index:, :].index.tolist()[0] # crossover on 1st row of sliced compr parents
    # print("crossover_damID {} {}".format(crossover_damID, type(crossover_damID)))
    children.loc[crossover_damID:, parents_names[0]] = parents.loc[crossover_damID:, parents_names[1]]
    children.loc[crossover_damID:, parents_names[1]] = parents.loc[crossover_damID:, parents_names[0]]
    for i in range(0,2):
        if children.iloc[:,i].any() == False:
            crossover(parents, resPolyg_df, runFolder)

    # check the feasibility of crossover operation
    children = fix_unfeasible_after_crossover(children, crossover_damID, runFolder)
    return children



def crossover_swapOnStream(parents, resPolyg_df, runFolder):
    '''
    basically a 2-point crossover

    parents is a DataFrame of two solutions/subsets to crossover to generate a child
    function returns the child, a feasible subset of type Series 
    There is NOT a crossover point
    There is one crossover stream, and on the crossover stream:
    child_1 has the reservoirs of parent_2 on the crossover stream, and the reservoir of parent_1 everywhere else
    child_2 has the reservoirs of parent_1 on the crossover stream, and the reservoir of parent_2 everywhere else
    '''
    children = parents.copy(deep=True)
    parents_names = parents.columns.tolist()
    compressed_parents = parents[parents.any(axis=1)]   # only keep damIDs in at least one of parents
    compressed_nrows = compressed_parents.shape[0]      # num of damIDs involved   

    list_of_involved_reservoirs = compressed_parents.index.tolist()
    list_of_involved_streams = resPolyg_df.loc[list_of_involved_reservoirs,"streamID"].tolist()
    list_of_involved_streams = list(set(list_of_involved_streams))      # to eliminate duplicates
    
    swap_correct = False
    while swap_correct == False:
        crossover_streamID = np.random.choice(list_of_involved_streams)
        damIDs_on_crossover_streamID = resPolyg_df[resPolyg_df["streamID"]==crossover_streamID].index.tolist()
        if (parents.loc[damIDs_on_crossover_streamID,parents_names[0]] == parents.loc[damIDs_on_crossover_streamID,parents_names[1]]).all() == False:
            swap_correct = True
    children.loc[damIDs_on_crossover_streamID, parents_names[0]] = parents.loc[damIDs_on_crossover_streamID, parents_names[1]]
    children.loc[damIDs_on_crossover_streamID, parents_names[1]] = parents.loc[damIDs_on_crossover_streamID, parents_names[0]]
    # check the feasibility of crossover operation
    children = fix_unfeasible_after_crossover_swapOnStream(children, damIDs_on_crossover_streamID, runFolder)
    return children



def create_gen_with_specials(values_df, gen_df, num_subsets, gen_num, run_name, runFolder):
    '''
    periodically, after every n generations, this operator is applied instead of regular crossover
    current solutions on Pareto frontier (parents) are crossovered with some special subsets (special parents)
    Special subsets have at least 1 reservoir on each stream (a few small streams could have none)
    This operator selects a stream at random
    Parent's reservoirs on selected stream are replaced by special parent's reservoirs on the same stream. The result is the child
    
    As NSGA-II makes a selection of reservoirs across generations, this operator instead puts back in the game
    reservoirs previously lost, adds more reservoirs to increase diversity of solutions, avoids premature convergence.
    For example, if a parent has no reservoirs on the selected stream, it receives that/those from the special parent.

    One application of the operator produces one child, i.e., special parent with parent's reservoir is not considered
    More of a 1-way inheritance than a crossover
    The operator applies at least once to all and only parents with rank 0
    The operator applies to parents in order of descending Qpeak_reduction
    Once the rank 0 parent with the lowest Qpeak_reduction is reached, the operator cycles back to top, 
    i.e., the rank 0 with highest Qpeak_reduction, and applies to parents until num_of_children = num_of_parents
    In other words, this operator diversifies and seeks to improve the best, Paeto-optimal solutions only.
    '''
    specials_df = get_specials_df(run_name)
    specials_damIDIndex_df = specials_df.copy(deep=True).reset_index(level=0, drop=True, inplace=False)

    qpeak_reduction_min_threshold = 0.1 * values_df["Qpeak_reduction"].max()
    filtered_df = values_df[values_df["Qpeak_reduction"] > qpeak_reduction_min_threshold]
    filtered_df.sort_values(by=["rank","Qpeak_reduction"], ascending=[True,False], inplace=True)
    num_of_parents = int(values_df.shape[0]/2)
    num_of_children = 2*num_subsets - num_of_parents
    next_parents_list = filtered_df.iloc[:num_of_parents, :].index.tolist()
    next_gen_def = gen_df.loc[:,next_parents_list]

    parents_for_xo_list = filtered_df.loc[filtered_df["rank"] == 0,:].index.tolist()
    num_of_cycles = num_of_children//len(parents_for_xo_list)
    parents_for_xo_name_list = parents_for_xo_list * num_of_cycles + parents_for_xo_list[:(num_of_children%len(parents_for_xo_list))]
    parents_for_xo_df = gen_df.loc[:,parents_for_xo_list]
    i=0
    for parent_name in parents_for_xo_name_list:
        parent_ser = parents_for_xo_df.loc[:,parent_name]
        child_ser = parent_ser.copy(deep=True)
        streamIDlist = list(set(specials_df.index.get_level_values(0).to_list()))
        num_of_streams = len(streamIDlist)
        num_of_xo_streams = random.randint(1, math.ceil(num_of_streams*0.02))
        special_subset_ser = specials_damIDIndex_df.sample(n=1, weights=[1,1,1,1,1,2,2,2], axis=1).iloc[:,0]
        xo_streamIDs = list(np.random.choice(streamIDlist, size=num_of_xo_streams, replace=False))
        xo_damIDs = specials_df.loc[(xo_streamIDs,),:].index.get_level_values(1).to_list()
        child_ser.loc[xo_damIDs] = special_subset_ser.loc[xo_damIDs]
        child_ser = fix_child_from_special(child_ser, runFolder)
        child_name = get_name_from_num(i, gen_num+1)
        child_ser.rename(child_name, inplace=True)
        next_gen_def = pd.concat([next_gen_def, child_ser], axis=1)
        i+=1
    
    return next_gen_def    



def create_gen_with_decimated_and_specials(next_parents_values_df, next_parents_subsets_df, num_subsets, gen_num, run_name, runFolder):
    '''
    This operator is applied to the surviving solutions of DECIMATION, which are next_parents_subsets_df
    The number or decimation survivors is less than half typically: main difference of this function VS create_gen_with_specials
    
    These parents are crossovered with some special subsets (special parents)
    Special subsets have at least 1 reservoir on each stream (few very small streams could have none)
    This operator selects a stream at random
    Parent's reservoirs on selected stream are replaced by special parent's reservoirs on the same stream. The result is the child
    
    As NSGA-II makes a selection of reservoirs across generation, this operator should instead put back in the game
    reservoirs previously lost, add more reservoirs to increase diversity of solutions, avoid premature convergence
    For example, if a parent has no reservoirs on the selected stream, it receives that/those from the special parent

    One application of the operator produces one child (i.e. special parent with parent's reservoir is not considered)
    More of a 1-way inheritance than a crossover
    The operator applies at least once to all and only parents with rank 0
    The operator applies to parents in order of descending Qpeak_reduction
    Once the rank 0 parent with the lowest Qpeak_reduction is reached, the operator cycles back to top, 
    i.e. rank 0, highest Qpeak_reduction, and applies to parents until num_of_children = num_of_parents
    '''
    specials_df = get_specials_df(run_name)
    specials_damIDIndex_df = specials_df.copy(deep=True).reset_index(level=0, drop=True, inplace=False)

    # next_parents_subsets_df are the solutions after decimation
    next_parents_list = next_parents_subsets_df.columns.tolist()
    num_of_parents = len(next_parents_list)
    num_of_children = 2*num_subsets - num_of_parents
    print(num_of_parents, num_of_children)
    # next_gen_def = gen_df.loc[:,nextparents_list]
    next_gen_def = next_parents_subsets_df

    # parents_for_xo_list = filtered_df.loc[filtered_df["rank"] == 0,:].index.tolist()
    num_of_cycles = num_of_children//len(next_parents_list)
    parents_for_xo_name_list = next_parents_list * num_of_cycles + next_parents_list[:(num_of_children%len(next_parents_list))]
    parents_for_xo_df = next_parents_subsets_df #gen_df.loc[:,next_parents_list]
    i=0
    for parent_name in parents_for_xo_name_list:
        parent_ser = parents_for_xo_df.loc[:,parent_name]
        child_ser = parent_ser.copy(deep=True)
        streamIDlist = list(set(specials_df.index.get_level_values(0).to_list()))
        num_of_streams = len(streamIDlist)
        num_of_xo_streams = random.randint(1, math.ceil(num_of_streams*0.02))
        special_subset_ser = specials_damIDIndex_df.sample(n=1, weights=[1,1,1,1,1,2,2,2], axis=1).iloc[:,0]
        xo_streamIDs = list(np.random.choice(streamIDlist, size=num_of_xo_streams, replace=False))
        xo_damIDs = specials_df.loc[(xo_streamIDs,),:].index.get_level_values(1).to_list()
        child_ser.loc[xo_damIDs] = special_subset_ser.loc[xo_damIDs]
        child_ser = fix_child_from_special(child_ser, runFolder)
        child_name = get_name_from_num(i, gen_num+1)
        child_ser.rename(child_name, inplace=True)
        next_gen_def = pd.concat([next_gen_def, child_ser], axis=1)
        i+=1
    
    return next_gen_def    



def mutation(subset, runFolder, n=1):
    '''
    parent is a Series, a solution/subset to mutate to generate a child
    n is the number of mutations to apply to the parent
    function returns the child, a feasible subset of type Series 
    '''
    nrows = subset.shape[0]
    mutated_subset = subset.copy(deep=True)
    
    k=1
    while k<=n:
        mutation_cand_index = np.random.randint(0,nrows)
        mutation_damID = subset.iloc[mutation_cand_index:].index.tolist()[0]
        if mutated_subset.loc[mutation_damID] == 1:
            mutated_subset.loc[mutation_damID] = 0
            if mutated_subset.any()==False:
                mutated_subset.loc[mutation_damID] = 1
                continue
            k+=1
        else:
            mutated_subset.loc[mutation_damID] = 1
            # check that the new reservoir is not flooded by nor does flood one of the other reservoirs
            if check_feasible(mutated_subset, [mutation_damID], runFolder) == True:
                k+=1
            else:
                mutated_subset.loc[mutation_damID] = 0
    # print("mutation {}".format(child))
    return mutated_subset


def create_children2(parents, num_subsets, resPolyg_df, gen_num, runFolder, crossover_proportion=0.7):
    '''
    parents: DataFrame of subsets, one in each column, generated by initialization or by nsga2 (create_next_parent)
    function applies crossover and mutation function to generate children DataFrame
    children contains as many subsets as parents
    both parents and children run on wflow through functions create_job and run_job in module heur_parallelize
    '''

    num_of_parents = parents.shape[1]
    num_of_children = 2*num_subsets - num_of_parents
    num_of_crossover_operations = math.ceil(num_of_children * crossover_proportion / 2)
    num_of_mutation_operations = num_of_children - (num_of_crossover_operations * 2)
    # digits = len(str(2*num_of_parents))

    children = pd.DataFrame(0, index=parents.index, columns=["to_remove"])

    # apply crossover to random pairs of parents and create some children
    crossover_j = 1
    while crossover_j <= num_of_crossover_operations:
        parent1_index = np.random.randint(0,num_of_parents)
        parent2_index = np.random.randint(0,num_of_parents)
        while parent2_index == parent1_index:
            parent2_index = np.random.randint(0,num_of_parents)
        selected_parents = parents.iloc[:, [parent1_index, parent2_index]]
        crossover_children = crossover_swapOnStream(selected_parents, resPolyg_df, runFolder)
        gc_colnames = crossover_children.columns.tolist()
        new_colnames = {gc_colnames[0]:get_name_from_num(2*crossover_j-2, gen_num),
        gc_colnames[1]:get_name_from_num(2*crossover_j-1, gen_num)}
        crossover_children.rename(columns = new_colnames, inplace=True)
        children = pd.concat([children, crossover_children], axis=1)
        # children.append(crossover_children)
        crossover_j += 1
    
    # apply mutation to random parents and create the rest of the children
    mutation_j = 1
    while mutation_j <= num_of_mutation_operations:
        parent_index = np.random.randint(0, num_of_parents)
        selected_parent = parents.iloc[:, parent_index]
        mutation_child = mutation(selected_parent, runFolder, 1)
        mutation_child.name = get_name_from_num(num_of_crossover_operations*2-1 + mutation_j, gen_num)
        children = pd.concat([children, mutation_child], axis=1)
        # children.append(mutation_child)
        mutation_j += 1

    children.drop("to_remove", axis=1, inplace=True)
    return children


def add_children(parents, curr_children, num_subsets, gen_num, runFolder):
    '''
    curr_children (DataFrame) are less than parents
    function adds children so that there are as many children as parents
    to reduce risk of duplicates, new children are the result of 3 mutation operations
    new children are concatenated with existing children and parents
    new generation is returned; duplicate columns/subsets in the generation are still possible
    '''
    
    num_of_parents = parents.shape[1]
    num_of_children = 2*num_subsets - num_of_parents
    parents_list = parents.columns.tolist()
    new_children = curr_children.copy(deep=True)
    children_colnames = [get_name_from_num(i, gen_num) for i in range(num_of_children)]
    curr_children_colnames = curr_children.columns.tolist()
    add_children_colnames = [subset_name for subset_name in children_colnames if subset_name not in curr_children_colnames]
    print(add_children_colnames)
    for subset_name in add_children_colnames:
        parent_name = np.random.choice(parents_list)
        selected_parent = parents.loc[:, parent_name]
        mutation_child = mutation(selected_parent, runFolder, 3)
        new_children[subset_name] = mutation_child
    
    new_children.sort_index(axis=1, inplace=True)
    subsets_df = pd.concat([parents, new_children], axis=1)
    # subsets_df.rename(columns= lambda x: int(x), inplace=True)
    return subsets_df



def dropping_duplicates(subsets_df):
    '''
    function drops duplicate columns from subsets_df
    pandas.drop_duplicates only works on rows, so subsets_df must be transposed before and after
    '''
    transposed_subsets_df = subsets_df.T
    transposed_subsets_df.drop_duplicates(inplace=True)
    return transposed_subsets_df.T


def get_simulation_results(gen_name, run_name):
    '''
    reads results of simulation, in which parents and children are run with wflow, parallelized on Argon
    '''
    current_folder = os.getcwd()
    results_csv_filename = os.path.join(current_folder, run_name, "gen{}_qpeak_cost.csv".format(gen_name))
    results_df = pd.read_csv(results_csv_filename, index_col="subsetID")#, usecols=["Qpeak_reduction", "cost"])
    return results_df


def create_next_generation(gen_num, resPolyg_df, run_name, num_subsets, runFolder, crossover_proportion):
    '''
    heur_main calls this function immediately after wflow parallel run on Argon
    function reads and evaluates results of parents and children, which are together in the same .csv
    parents and children are rows, index in the first column; "Qpeak_reduction" and "cost" columns
    normally, first half are parents, second half are children, and they are in the same number
    num_parents is given to tell exactly where the parents end and the children start in the df
    
    function creates parents of next generation, created with NSGA II
    then from nextgen parents creates nextgen children, with crossover and mutation
    dfs concatenated together into nextgen df
    check for duplicate subsets columns, in case drop duplicate child(ren) and replace with new child(ren)
    returns nextgen df
    '''
    # gen_name = get_name_from_num(gen_n, 2)
    values_df = get_simulation_results(gen_num, run_name)
    # parents_values_df = values_df.iloc[:num_parents, :]
    # children_values_df = values_df.iloc[num_parents:, :]
    next_parents_values_df = create_next_parent_values(values_df, gen_num, run_name) # NonDom, DistSorted ranking
    next_parents_list = next_parents_values_df.index.tolist()

    curr_generation_subsets_df = get_curr_generation_subsets(gen_num, run_name)
    
    next_parents_subsets_df = curr_generation_subsets_df.loc[:, next_parents_list].copy(deep=True)
    num_parents = next_parents_subsets_df.shape[1]
    next_gen_num = gen_num+1
    # if next_gen_num % 4 == 0:
    #     next_generation_subsets_df = create_gen_with_specials(values_df, curr_generation_subsets_df, num_subsets, gen_num, run_name, runFolder)
    # else:
    next_children_subsets_df = create_children2(next_parents_subsets_df, num_subsets, resPolyg_df, next_gen_num, runFolder, crossover_proportion)
    next_generation_subsets_df = pd.concat([next_parents_subsets_df, next_children_subsets_df], axis=1)
    
    possible_duplicates = True
    while possible_duplicates == True:
        after_dropdupli_df = dropping_duplicates(next_generation_subsets_df)
        if after_dropdupli_df.shape == next_generation_subsets_df.shape:
            possible_duplicates = False
        else:
            next_generation_subsets_df = add_children(next_parents_subsets_df, after_dropdupli_df.iloc[:, num_parents:], num_subsets, next_gen_num, runFolder)
            possible_duplicates = True
    return next_generation_subsets_df



def create_decimated_generation(gen_num, resPolyg_df, run_name, num_subsets, runFolder, crossover_proportion, decimation_survival_rate):
    '''
    heur_main calls this function immediately after wflow parallel run on Argon
    function reads and evaluates results of parents and children, which are together in the same .csv
    parents and children are rows, index in the first column; "Qpeak_reduction" and "cost" columns
    normally, first half are parents, second half are children, and they are in the same number
    num_parents is given to tell exactly where the parents end and the children start in the df
    
    function creates parents of next generation using decimation operator
    solution are ranked by non-dominance and distance
    top 10 Pareto solutions with highest distance are retained and passed to next gen
    the remaining Pareto solutions are decimated, i.e., one every 1/decimation_survival_rate are passed to next gen
    the few nextgen parents remained create nextgen children, with crossover and mutation
    dfs concatenated together into nextgen df
    check for duplicate subsets columns, in case drop duplicate child(ren) and replace with new child(ren)
    returns nextgen df
    '''

    # gen_name = get_name_from_num(gen_n, 2)
    values_df = get_simulation_results(gen_num, run_name)
    # parents_values_df = values_df.iloc[:num_parents, :]
    # children_values_df = values_df.iloc[num_parents:, :]
    next_parents_values_df = create_decimated_next_parent_values(values_df, gen_num, run_name, decimation_survival_rate) # NonDom, DistSorted ranking
    next_parents_list = next_parents_values_df.index.tolist()

    curr_generation_subsets_df = get_curr_generation_subsets(gen_num, run_name)
    # curr_generation_subsets_df.rename(columns= lambda x: int(x), inplace=True)

    # next_parents_subsets_df are the solutions after decimation
    next_parents_subsets_df = curr_generation_subsets_df.loc[:, next_parents_list].copy(deep=True)
    num_parents = next_parents_subsets_df.shape[1]
    next_gen_num = gen_num+1
    next_generation_subsets_df = create_gen_with_decimated_and_specials(next_parents_values_df, next_parents_subsets_df, num_subsets, gen_num, run_name, runFolder)
    # next_children_subsets_df = create_children2(next_parents_subsets_df, num_subsets, resPolyg_df, next_gen_num, runFolder, crossover_proportion)
    # next_generation_subsets_df = pd.concat([next_parents_subsets_df, next_children_subsets_df], axis=1)

    possible_duplicates = True
    while possible_duplicates == True:
        after_dropdupli_df = dropping_duplicates(next_generation_subsets_df)
        if after_dropdupli_df.shape == next_generation_subsets_df.shape:
            possible_duplicates = False
        else:
            next_generation_subsets_df = add_children(next_parents_subsets_df, after_dropdupli_df.iloc[:, num_parents:], num_subsets, next_gen_num, runFolder)
            possible_duplicates = True
    return next_generation_subsets_df




























'''import info on dams and reservoirs from shapefile into damLine_df dataframe'''
# current_folder = os.getcwd()
# damLine_dbf_filename = "damLine2.0_by_Vmax_to_damLength.dbf"
# damLine_shp_filename = "damLine2.0_by_Vmax_to_damLength.shp"
# reservoirPolyg_shp_filename = "reservoirPolygon2.0_by_Vmax_to_damLength.shp"
# damLine_df = gpd.read_file(os.path.join(current_folder, "reservoir_locations", damLine_dbf_filename))

''' total budget available'''
# budget = 600000

'''threshold for flooded area by a subset of reservoirs'''
# maxFloodedArea = 500000

# number of subsets for a generation
# num_subsets = 1000

# damIDList = damLine_df.damID.tolist()
# streamIDList = list(set(damLine_df.streamID.tolist()))
# reachIDList = list(set(damLine_df.reachID.tolist()))
# flooded_dict = h_geo.build_floodedDict(current_folder, reservoirPolyg_shp_filename)

# gen0_df = h_init.init_gen0(damLine_df, num_subsets, budget, maxFloodedArea, flooded_dict)