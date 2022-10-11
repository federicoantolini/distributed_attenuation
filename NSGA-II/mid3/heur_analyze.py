'''
I used this module, but it is better to split into heur_lib_analyze and heur_analyze
as in multi-scale folder

This module needs to be re-checked
'''



from enum import unique
import os
import time
import sys

import numpy as np
import pandas as pd

pd.set_option('mode.chained_assignment', None)



def build_multi_gen_Pareto_df(generation_list, runFolder, run_name, d=False):
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    filepath = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(generation_list[0]))
    if d==True:
        Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    df = pd.read_csv(filepath, usecols=['subsetID','Qpeak_reduction','cost','rank'])
    Pareto_df = df[df['rank'] == 0]
    Pareto_df.loc[:,'gen'] = generation_list[0]
        
    # Pareto_df.set_index(pd.Index([i for i in range(len(Pareto_df.index.tolist()))]), inplace=True)
    Pareto_df.set_index(['gen', 'subsetID'], inplace=True, drop=True)
    Pareto_df.loc[:, "subsetID"] = Pareto_df.index.get_level_values(1)
    Pareto_df.loc[:, "created_in_gen"] = Pareto_df.loc[:, "subsetID"].apply(lambda x:int(x[1:3]))
    Pareto_df.loc[:, "created_in_gen"] = Pareto_df.loc[:, "created_in_gen"].where(Pareto_df.loc[:, "subsetID"].apply(len)==7, Pareto_df.loc[:, "subsetID"].apply(lambda x: int(x[1:4])))

    if len(generation_list) == 1:
        return Pareto_df

    for gen_num in generation_list[1:]:
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        filename = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num))
        df = pd.read_csv(filename, usecols=['subsetID','Qpeak_reduction','cost','rank'])
        df = df[df['rank'] == 0]
        df.loc[:,'gen'] = gen_num
        df.set_index(['gen', 'subsetID'], inplace=True, drop=True)
        subsetID_list = df.index.get_level_values(1).to_list()
        # created_in_gen_list = [int(sID[1:3]) for sID in subsetID_list]
        df.loc[:, "subsetID"] = df.index.get_level_values(1)
        df.loc[:, "created_in_gen"] = df.loc[:, "subsetID"].apply(lambda x:int(x[1:3]))
        df.loc[:, "created_in_gen"] = df.loc[:, "created_in_gen"].where(df.loc[:, "subsetID"].apply(len)==7, df.loc[:, "subsetID"].apply(lambda x: int(x[1:4])))
        # df.loc[:,"created_in_gen"] = created_in_gen_list
        Pareto_df = pd.concat([Pareto_df, df], axis=0)
        # Pareto_df = Pareto_df.append(df)
    
    Pareto_df.to_csv(Pareto_filepath)



def calc_generation_summary(generation_list, runFolder, d=False):
    '''
    tot occurrences in a generation
    compress and shape[0] for the num of unique res in a gen 

    max res per subset
    min res per subset
    avg res per subset
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    
    num_of_occurr_dict = {}
    num_of_unique_res_dict = {}
    max_res_in_subset_dict = {}
    min_res_in_subset_dict = {}
    avg_res_in_subset_dict = {}

    index = pd.Index(data=generation_list, name='gen_num')
    
    for gen_num in generation_list:
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1] 
        filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        print(filepath)
        # if d==True:
        #     filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(filepath, index_col='damID', dtype='Int64')  # , usecols=['subsetID','Q_peak','Qpeak_reduction','cost', 'floodedArea','rank','distance']
        occurring_reservoirs_list = df[df.any(axis=1)].index.tolist()
        num_of_unique_res_dict[gen_num] = len(occurring_reservoirs_list)
        
        df.loc["num_of_reservoirs",:] = df.sum(axis=0)
        max_res_in_subset_dict[gen_num] = df.loc["num_of_reservoirs",:].max()
        min_res_in_subset_dict[gen_num] = df.loc["num_of_reservoirs",:].min()
        avg_res_in_subset_dict[gen_num] = df.loc["num_of_reservoirs",:].mean()

        df.loc[:,'num_of_occurr'] = df.sum(axis=1)
        num_of_occurr_dict[gen_num] = df.loc['num_of_reservoirs','num_of_occurr']
        
    
    summary_df = pd.DataFrame(data={'num_of_occurr':pd.Series(num_of_occurr_dict),
                                    'num_of_unique_res':pd.Series(num_of_unique_res_dict),
                                    'max_res_in_subset':pd.Series(max_res_in_subset_dict),
                                    'min_res_in_subset':pd.Series(min_res_in_subset_dict),
                                    'avg_res_in_subset':pd.Series(avg_res_in_subset_dict)
                                    },
                                    index=index)
    return summary_df



def build_df_unique_in_gen(runFolder, run_name, generation_list, d=False):
    '''
    calculate the number of unique reservoirs used by subsets in each generation
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    
    unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(0))
    if d==True:
        unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')
    index = pd.Index(data=df.index.tolist(), name='damID')
    unique_df = pd.DataFrame(data={"to_remove":0}, index=index)
    
    for i in range(len(generation_list)):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        ser = pd.Series(0, index=unique_df.index)
        ser.name = gen_num
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')  # , usecols=['subsetID','Q_peak','Qpeak_reduction','cost', 'floodedArea','rank','distance']
        occurring_reservoirs_list = df[df.any(axis=1)].index.tolist()
        ser[occurring_reservoirs_list] = 1
        unique_df = pd.concat([unique_df, ser], axis=1)
        df=None
        ser=None

    if "to_remove" in unique_df.columns.tolist():
        unique_df.drop(columns="to_remove", inplace=True)
    unique_df.to_csv(unique_filepath)
    return unique_df


def build_df_unique_in_Pareto_gen(runFolder, run_name, generation_list, d=False):
    '''
    calculate the number of unique reservoirs used by Pareto optimal subsets in each generation
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    # if os.path.exists(unique_filename):
    #     unique_df = pd.read_csv(unique_filename, index_col='damID')
    #     columns_list = [int(i) for i in unique_df.columns.tolist()]
    # else:
    subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(0))
    df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')
    index = pd.Index(data=df.index.tolist(), name='damID')
    Pareto_unique_df = pd.DataFrame(data={"to_remove":0}, index=index)
    
    Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_df = pd.read_csv(Pareto_filepath, index_col=["gen","subsetID"])

    for i in range(len(generation_list)):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        ser = pd.Series(0, index=index)
        ser.name = gen_num
        Pareto_subset_list = Pareto_df.loc[(gen_num,),:].index.tolist()
        # if gen_num in columns_list:
        #     continue
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')  # , usecols=['subsetID','Q_peak','Qpeak_reduction','cost', 'floodedArea','rank','distance']
        df = df.loc[:, Pareto_subset_list]
        occurring_reservoirs_list = df[df.any(axis=1)].index.tolist()
        ser[occurring_reservoirs_list] = 1
        Pareto_unique_df = pd.concat([Pareto_unique_df, ser], axis=1)
        df=None
        ser=None

    if "to_remove" in Pareto_unique_df.columns.tolist():
        Pareto_unique_df.drop(columns="to_remove", inplace=True)
    Pareto_unique_df.to_csv(Pareto_unique_filepath)
    return Pareto_unique_df



def build_df_occurrences_in_gen(runFolder, run_name, generation_list, d=False):
    '''
    calculate the number of occurrences of reservoirs in each generation --> occurrences_df
    
    useful to understand what are the most frequent reservoirs across subsets and across generations
    if their frequency changes across generations (up or down)
    '''
    
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    occurrences_filepath = os.path.join(runFolder,"occurrences_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        occurrences_filepath = os.path.join(runFolder,"occurrences_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    unique_df = pd.read_csv(unique_filepath, index_col='damID')
    columns_list = unique_df.columns.tolist()
    print(columns_list[:10])
    unique_df.rename(columns=lambda x: int(x), inplace=True)
    columns_list = unique_df.columns.tolist()
    print(columns_list[:10])
    
    occurrences_df = unique_df.copy(deep=True)
    
    for i in range(len(generation_list)):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')  # , usecols=['subsetID','Q_peak','Qpeak_reduction','cost', 'floodedArea','rank','distance']
        occurring_reservoirs_list = unique_df[unique_df.loc[:, gen_num]==1].index.tolist()
        occurrences_df.loc[occurring_reservoirs_list, gen_num] = df.loc[occurring_reservoirs_list, :].sum(axis=1)
        df=None
        
    occurrences_df.to_csv(occurrences_filepath)   
    return occurrences_df
    
    
    
def build_df_occurrences_in_Pareto_gen(runFolder, run_name, generation_list, d=False):
    '''
    calculate the number of occurrences of reservoirs in each generation --> occurrences_df
    
    useful to understand what are the most frequent reservoirs across subsets and across generations
    if their frequency changes across generations (up or down)
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_occurrences_filepath = os.path.join(runFolder,"Pareto_occurrences_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_occurrences_filepath = os.path.join(runFolder,"Pareto_occurrences_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))

    Pareto_df = pd.read_csv(Pareto_filepath, index_col=["gen","subsetID"])
    Pareto_unique_df = pd.read_csv(Pareto_unique_filepath, index_col='damID')
    Pareto_unique_df.rename(columns=lambda x: int(x), inplace=True)
    columns_list = Pareto_unique_df.columns.tolist()
    Pareto_occurrences_df = Pareto_unique_df.copy(deep=True)
    
    for gen_num in generation_list:
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')  # , usecols=['subsetID','Q_peak','Qpeak_reduction','cost', 'floodedArea','rank','distance']
        Pareto_subset_list = Pareto_df.loc[(gen_num,),:].index.tolist()
        Pareto_occurring_reservoirs_list = Pareto_unique_df[Pareto_unique_df.loc[:, gen_num]==1].index.tolist()
        Pareto_occurrences_df.loc[Pareto_occurring_reservoirs_list, gen_num] = df.loc[Pareto_occurring_reservoirs_list, Pareto_subset_list].sum(axis=1)
        df=None
        
    Pareto_occurrences_df.to_csv(Pareto_occurrences_filepath)   
    return Pareto_occurrences_df
    

    
def calc_diversity_within_generation(unique_df, runFolder, run_name, generation_list, d=False):
    '''
    within each generation, the diversity-within rate is the number of unique reservoirs divided by the total number of reservoirs
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    diversity_within_filepath = os.path.join(runFolder, "diversity_within_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        diversity_within_filepath = os.path.join(runFolder, "diversity_within_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    index = pd.Index([int(i) for i in unique_df.columns.tolist()], name="gen_num")
    # print(index.tolist())
    diversity_within_df = pd.DataFrame(data={"diversity_within":0}, index=index, dtype="Float64")
    for gen_num in generation_list:
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')
        diversity_within_rate = unique_df.iloc[:,gen_num].sum()/df.sum().sum()
        diversity_within_df.at[gen_num, "diversity_within"] = diversity_within_rate
        df=None
    
    diversity_within_df.to_csv(diversity_within_filepath)



def calc_diversity_within_Pareto_generation(Pareto_unique_df, runFolder, run_name, generation_list, d=False):
    '''
    within each generation, the diversity-within rate is the number of unique reservoirs divided by the total number of reservoirs
    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_diversity_within_filepath = os.path.join(runFolder, "Pareto_diversity_within_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    if d==True:
        Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        Pareto_diversity_within_filepath = os.path.join(runFolder, "Pareto_diversity_within_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
    index = pd.Index([int(i) for i in Pareto_unique_df.columns.tolist()], name="gen_num")
    # print(index.tolist())
    Pareto_diversity_within_df = pd.DataFrame(data={"diversity_within":0}, index=index, dtype="Float64")
    for i in range(len(generation_list)):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        # if d==True:
        #     subset_filepath = os.path.join(runFolder, "gen{}_subsets.csv".format(gen_num))
        df = pd.read_csv(subset_filepath, index_col='damID', dtype='Int64')
        Pareto_diversity_within_rate = Pareto_unique_df.iloc[:,i].sum()/df.sum().sum()
        Pareto_diversity_within_df.at[gen_num, "diversity_within"] = Pareto_diversity_within_rate
        df=None
    
    Pareto_diversity_within_df.to_csv(Pareto_diversity_within_filepath)



def calculate_diversity_across_generations(unique_df, runFolder, run_name, every_other=1, d=False):
    '''
    how many unique reservoirs are inherited from previous generation?
    how many unique reservoirs are introduced in the current generation?
    if the number of new reservoirs is very small, then subsets in consecutive generations are not very different...

    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    diversity_within_filepath = os.path.join(runFolder, "diversity_within_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    diversity_across_filepath = os.path.join(runFolder, "diversity_across_{}_{}_{}-{}.csv".format(every_other, run_name, generation_list[0], generation_list[-1]))
    if d==True:
        unique_filepath = os.path.join(runFolder,"unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        diversity_within_filepath = os.path.join(runFolder, "diversity_within_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        diversity_across_filepath = os.path.join(runFolder, "diversity_across_{}_{}_{}-{}_d.csv".format(every_other, run_name, generation_list[0], generation_list[-1]))
    
    unique_df = pd.read_csv(unique_filepath, index_col="damID")
    diversity_df = pd.read_csv(diversity_within_filepath, index_col="gen_num")
    generation_list = diversity_df.index.tolist()
    
    diversity_df["total"] = 0
    diversity_df.at[0,"total"] = unique_df.iloc[:, 0].sum()
    diversity_df["num_of_new_from_prev_{}".format(every_other)]=0
    diversity_df["num_of_lost_from_prev_{}".format(every_other)]=0

    for i in range(len(generation_list[every_other:])):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        # subset_filename = os.path.join(runFolder, "gen{}_subsets.csv".format(0))
        # df = pd.read_csv(subset_filename, index_col='damID', dtype='Int64')
       
        diversity_df.at[gen_num, "total"] = unique_df.iloc[:, i].sum()
        
        s = pd.Series(0, index=unique_df.index)
        s = s.where(unique_df.iloc[:, i]<=unique_df.iloc[:, i-every_other], 1)
        diversity_df.at[gen_num, "num_of_new_from_prev_{}".format(every_other)] = s.sum() 
       
        s = pd.Series(1, index=unique_df.index)
        s = s.where(unique_df.iloc[:, i]==0, 0)
        s = s.where(unique_df.iloc[:, i-every_other]==1, 0 )
        diversity_df.at[gen_num, "num_of_lost_from_prev_{}".format(every_other)] = s.sum()
        
        s = pd.Series(1, index=unique_df.index)
        s = s.where(unique_df.iloc[:, i]==1, 0) 
        s = s.where(unique_df.iloc[:, i-every_other]==1, 0 )
        diversity_df.at[gen_num, "num_of_inherited_from_prev_{}".format(every_other)] = s.sum()
        
        diversity_df.at[gen_num, "perc_new_from_prev_{}".format(every_other)] = 100*diversity_df.at[gen_num, "num_of_new_from_prev_{}".format(every_other)]/diversity_df.at[gen_num, "total"]
        diversity_df.at[gen_num, "perc_lost_from_prev_{}".format(every_other)] = 100*diversity_df.at[gen_num, "num_of_lost_from_prev_{}".format(every_other)]/diversity_df.at[gen_num, "total"]
        diversity_df.at[gen_num, "perc_inherited_from_prev_{}".format(every_other)] = 100*diversity_df.at[gen_num, "num_of_inherited_from_prev_{}".format(every_other)]/diversity_df.at[gen_num, "total"]
         
        
        # diversity_from_prev_rate = unique_df.loc[:,gen_num].sum()/df.sum()
    diversity_df.to_csv(diversity_across_filepath)



def calculate_diversity_across_Pareto_generations(Pareto_unique_df, runFolder, run_name, generation_list, every_other=1, d=False):
    '''
    how many unique reservoirs are inherited from previous generation?
    how many unique reservoirs are introduced in the current generation?
    if the number of new reservoirs is very small, then subsets in consecutive generations are not very different...

    '''
    alt_runFolders = [os.path.join(runFolder,"no_decim"), os.path.join(runFolder,"d2")]
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_diversity_within_filepath = os.path.join(runFolder, "Pareto_diversity_within_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_diversity_across_filepath = os.path.join(runFolder, "Pareto_diversity_across_{}_{}_{}-{}.csv".format(every_other, run_name, generation_list[0], generation_list[-1]))
    if d==True:
        Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        Pareto_diversity_within_filepath = os.path.join(runFolder, "Pareto_diversity_within_{}_{}-{}_d.csv".format(run_name, generation_list[0], generation_list[-1]))
        Pareto_diversity_across_filepath = os.path.join(runFolder, "Pareto_diversity_across_{}_{}_{}-{}_d.csv".format(every_other, run_name, generation_list[0], generation_list[-1]))
        
    Pareto_unique_df = pd.read_csv(Pareto_unique_filepath, index_col="damID")
    Pareto_diversity_df = pd.read_csv(Pareto_diversity_within_filepath, index_col="gen_num")
    # generation_list = Pareto_diversity_df.index.tolist()
    
    Pareto_diversity_df["total"] = 0
    Pareto_diversity_df.at[0,"total"] = Pareto_unique_df.iloc[:, 0].sum()
    Pareto_diversity_df["num_of_new_from_prev_{}".format(every_other)]=0
    Pareto_diversity_df["num_of_lost_from_prev_{}".format(every_other)]=0

    for i in range(len(generation_list[every_other:])):
        gen_num = generation_list[i]
        if gen_num>100 and d==False:
            runFolder = alt_runFolders[0]
        elif gen_num>100 and d==True:
            runFolder = alt_runFolders[1]
        # subset_filename = os.path.join(runFolder, "gen{}_subsets.csv".format(0))
        # df = pd.read_csv(subset_filename, index_col='damID', dtype='Int64')
       
        Pareto_diversity_df.at[gen_num, "total"] = Pareto_unique_df.iloc[:, i].sum()
        
        s = pd.Series(0, index=Pareto_unique_df.index)
        s = s.where(Pareto_unique_df.iloc[:, i]<=Pareto_unique_df.iloc[:, i-every_other], 1)
        Pareto_diversity_df.at[gen_num, "num_of_new_from_prev_{}".format(every_other)] = s.sum() 
       
        s = pd.Series(1, index=Pareto_unique_df.index)
        s = s.where(Pareto_unique_df.iloc[:, i]==0, 0)
        s = s.where(Pareto_unique_df.iloc[:, i-every_other]==1, 0 )
        Pareto_diversity_df.at[gen_num, "num_of_lost_from_prev_{}".format(every_other)] = s.sum()
        
        s = pd.Series(1, index=Pareto_unique_df.index)
        s = s.where(Pareto_unique_df.iloc[:, i]==1, 0) 
        s = s.where(Pareto_unique_df.iloc[:, i-every_other]==1, 0 )
        Pareto_diversity_df.at[gen_num, "num_of_inherited_from_prev_{}".format(every_other)] = s.sum()
        
        Pareto_diversity_df.at[gen_num, "perc_new_from_prev_{}".format(every_other)] = \
            100*Pareto_diversity_df.at[gen_num, "num_of_new_from_prev_{}".format(every_other)] / \
                Pareto_diversity_df.at[gen_num, "total"]
        Pareto_diversity_df.at[gen_num, "perc_lost_from_prev_{}".format(every_other)] = \
            100*Pareto_diversity_df.at[gen_num, "num_of_lost_from_prev_{}".format(every_other)] / \
                Pareto_diversity_df.at[gen_num, "total"]
        Pareto_diversity_df.at[gen_num, "perc_inherited_from_prev_{}".format(every_other)] = \
            100*Pareto_diversity_df.at[gen_num, "num_of_inherited_from_prev_{}".format(every_other)] / \
                Pareto_diversity_df.at[gen_num, "total"]
         
        
        # diversity_from_prev_rate = unique_df.loc[:,gen_num].sum()/df.sum()
    Pareto_diversity_df.to_csv(Pareto_diversity_across_filepath)



run_name_list = [
                # "mid_2080_01feb", 
                # "mid_5050_01feb",
                # "mid_8020_01feb",
                # "mid_2080SP_01feb",
                # "mid_5050SP_01feb",
                "mid_8020SP_01feb"
                ]
# decimation=False
decimation=True
# run_name = "mid_2080_01feb"
# run_name_list = ["mid_8020_01feb"]
current_folder = os.getcwd()
for run_name in run_name_list:
    runFolder = os.path.join(current_folder, run_name)
    # filename_list = [fn for fn in os.listdir(runFolder) \
    #     if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
    # generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
    # generation_list.sort()
    generation_list = [i for i in range(0, 201)]

    build_multi_gen_Pareto_df(generation_list, runFolder, run_name, d=decimation)
    summary_df = calc_generation_summary(generation_list, runFolder, d=decimation)
    summary_df.to_csv(os.path.join(runFolder,"num_of_subsets_summary_{}-{}_gen_{}.csv".format(generation_list[0], generation_list[-1], run_name)))
    # unique_df = build_df_unique_in_gen(runFolder, run_name, generation_list, d=decimation)
    Pareto_unique_df = build_df_unique_in_Pareto_gen(runFolder, run_name, generation_list, d=decimation)
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_unique_df = pd.read_csv(Pareto_unique_filepath, index_col='damID')
    # occurrences_df = build_df_occurrences_in_gen(runFolder, run_name, generation_list, d=decimation)
    Pareto_occurrences_df = build_df_occurrences_in_Pareto_gen(runFolder, run_name, generation_list, d=decimation)
    # calc_diversity_within_generation(unique_df, runFolder, run_name, generation_list, d=decimation)
    calc_diversity_within_Pareto_generation(Pareto_unique_df, runFolder, run_name, generation_list, d=decimation)
    # calculate_diversity_across_generations(unique_df, runFolder, run_name, d=decimation)
    calculate_diversity_across_Pareto_generations(Pareto_unique_df, runFolder, run_name, generation_list, d=decimation)
    print("done with {}".format(run_name))

