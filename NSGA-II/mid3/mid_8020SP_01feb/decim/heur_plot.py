import os
import pandas as pd
import heur_lib_plot as hpl

current_folder = os.getcwd()
# print(current_folder.split(os.sep))
runID = current_folder.split(os.sep)[-3]
run_name = current_folder.split(os.sep)[-2]
# for run_name in run_name_list:
#     runFolder = os.path.join(current_folder, run_name)

filename_list = [fn for fn in os.listdir(current_folder) if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
generation_list = [ fn.split('_')[0][3:] for fn in filename_list]
generation_list.sort()
# print(generation_list)

for gen_num in generation_list:
    filepath = os.path.join(current_folder, "gen{}_qpeak_cost_rank.csv".format(gen_num))
    df = pd.read_csv(filepath, index_col='subsetID')
    gen_filepath = os.path.join(current_folder, "images", "_gen{}.png".format(gen_num))
    # if os.path.exists(gen_filepath):
    #     continue
    hpl.plot_single_generation(df, runID, run_name, gen_num, current_folder, decimation=True)
