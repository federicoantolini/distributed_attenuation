from enum import unique
import os
import time
import sys

import numpy as np
import pandas as pd

pd.set_option('mode.chained_assignment', None)






run_name_list = [
                "mid_2080_01feb", 
                "mid_5050_01feb",
                "mid_8020_01feb",
                "mid_2080SP_01feb",
                "mid_5050SP_01feb",
                "mid_8020SP_01feb"
                ]

current_folder = os.getcwd()
gen_num = 100

run_name = run_name_list[0]
runFolder = os.path.join(current_folder, run_name)
occurrences_filename = "Pareto_occurrences_{}.csv".format(run_name)
occurrences_filepath = os.path.join(runFolder, occurrences_filename)
occurrences_df = pd.read_csv(occurrences_filepath, index_col="damID", dtype='Int64')
runs_occurrences_df = pd.DataFrame({run_name+"_gen"+str(gen_num) : occurrences_df.loc[:, str(gen_num)]}, index=occurrences_df.index)
nrows = runs_occurrences_df.shape[0]
runs_occurrences_df.loc[:, run_name+"_%"] = runs_occurrences_df.loc[:, run_name+"_gen"+str(gen_num)] * 100 / nrows

for i in range(1, len(run_name_list)):
    run_name = run_name_list[i]
    runFolder = os.path.join(current_folder, run_name)
    occurrences_filename = "Pareto_occurrences_{}.csv".format(run_name)
    occurrences_filepath = os.path.join(runFolder, occurrences_filename)
    occurrences_df = pd.read_csv(occurrences_filepath, index_col="damID", dtype='Int64')
    runs_occurrences_df.loc[:, run_name+"_gen100"] = occurrences_df.loc[:, str(gen_num)]
    runs_occurrences_df.loc[:, run_name+"_%"] = runs_occurrences_df.loc[:, run_name+"_gen"+str(gen_num)] * 100 / nrows
    occurrences_df = None

runs_occurrences_filepath = os.path.join(current_folder, "Pareto_occurrences_allruns.csv")
runs_occurrences_df.to_csv(runs_occurrences_filepath, float_format='%.2f')
