from enum import unique
import os
import time
import sys

import numpy as np
import pandas as pd

import heur_lib_analyze as hla

pd.set_option('mode.chained_assignment', None)


run_name_list = [
                # "all_22apr", 
                # "comb_umd_14may",
                "regionABCD_plus",

                ]

current_folder = os.getcwd()
for run_name in run_name_list:
    runFolder = os.path.join(current_folder, run_name)
    # filename_list = [fn for fn in os.listdir(runFolder) \
    #     if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
    # generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
    # generation_list.sort()
    generation_list = [i for i in range(61, 201)]

    hla.build_multi_gen_Pareto_df(generation_list, runFolder, run_name)
    summary_df = hla.calc_generation_summary(generation_list, runFolder)
    summary_df.to_csv(os.path.join(runFolder,"num_of_subsets_summary_{}-{}_gen_{}.csv".format(generation_list[0], generation_list[-1], run_name)))
    # unique_df = build_df_unique_in_gen(runFolder, run_name, generation_list, d=decimation)
    Pareto_unique_df = hla.build_df_unique_in_Pareto_gen(runFolder, run_name, generation_list)
    Pareto_unique_filepath = os.path.join(runFolder,"Pareto_unique_{}_{}-{}.csv".format(run_name, generation_list[0], generation_list[-1]))
    Pareto_unique_df = pd.read_csv(Pareto_unique_filepath, index_col='damID')
    # occurrences_df = build_df_occurrences_in_gen(runFolder, run_name, generation_list, d=decimation)
    Pareto_occurrences_df = hla.build_df_occurrences_in_Pareto_gen(runFolder, run_name, generation_list)
    # calc_diversity_within_generation(unique_df, runFolder, run_name, generation_list, d=decimation)
    hla.calc_diversity_within_Pareto_generation(Pareto_unique_df, runFolder, run_name, generation_list)
    # calculate_diversity_across_generations(unique_df, runFolder, run_name, d=decimation)
    hla.calculate_diversity_across_Pareto_generations(Pareto_unique_df, runFolder, run_name, generation_list)
    print("done with {}".format(run_name))

# current_folder = os.getcwd()
# gen_num = 200
# for run_name in run_name_list:
#     hla.analyze_Pareto_front(current_folder, run_name, gen_num)

