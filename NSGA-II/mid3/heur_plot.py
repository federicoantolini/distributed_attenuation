from email.mime import image
'''
call this module to RUN graphic functions and create plots
explicitly change parameters and variables, comment, uncomment lines in this module to call desired functions
'''

from enum import unique
import os

import numpy as np
import pandas as pd
import heur_lib_plot as hlp

# import geopandas as gpd
# import geoplot as gplt
# import geoplot.crs as gcrs
# import cartopy.crs as ccrs

# import matplotlib
# import matplotlib.pyplot as plt
# from matplotlib import cm
# from matplotlib import gridspec
# from matplotlib.ticker import FormatStrFormatter
# import imageio
from PIL import Image, ImageOps

# import heur_geospatial as h_geo

pd.set_option('mode.chained_assignment', None)



run_name_list = [
    # "mid_2080_01feb", 
    # "mid_5050_01feb",
    # "mid_8020_01feb",
    # "mid_2080SP_01feb",
    # "mid_5050SP_01feb",
    "mid_8020SP_01feb"
    ]
# run_name = "mid_8020SP_21jan"
runID = "mid3"
##run_name = "mid_8020_01feb"
##run_name_list = ["mid_8020_01feb"]
current_folder = os.getcwd()
for run_name in run_name_list:
    runFolder = os.path.join(current_folder, run_name)
    # filename_list = [fn for fn in os.listdir(runFolder) if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
    # generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
    # generation_list.sort()

    gen_filepath_list = []
    # for gen_num in generation_list:
    # for gen_num in range(100, 101):
    #     filename = os.path.join(runFolder, "gen{}_qpeak_cost_rank.csv".format(gen_num))
    #     df = pd.read_csv(filename, index_col='subsetID')
    #     gen_filepath = os.path.join(runFolder,"images", "_gen{}.png".format(gen_num))
    # #     # if os.path.exists(gen_filepath):
    # #     #     continue
    #     hlp.plot_single_generation(df, runID, run_name, gen_num, runFolder)
    #     gen_filepath_list.append(gen_filepath)
    # print("done with plot_single_generation")
    # output_gen_filename = "_gen_{}_slideshow.gif".format(run_name)
    # hlp.create_slideshow(runFolder, gen_filepath_list, output_gen_filename)

    gen_num = 200
    Pareto_df = pd.read_csv(os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, 0, gen_num)), index_col=["gen", "subsetID"])
    Pareto100_subsets = Pareto_df.loc[(gen_num, ),:].index.tolist()
    Pareto100_subset_filepath_list=[]
    # for i in range(len(Pareto100_subsets)):
    #     subsetID = Pareto100_subsets[i]
    #     subset_filename = "_Pareto_subset_gen{}_{}.png".format(gen_num, subsetID)
    #     subset_filepath = os.path.join(runFolder,"images", subset_filename) 
    # #     if os.path.exists(subset_filepath):
    # #         continue
    # #     # if subsetID == "_950042":
    # #     #     break
    #     hlp.plot_single_Pareto_subset(Pareto_df, runID, run_name, gen_num, subsetID, runFolder)
    #     print("done_with {}".format(subsetID))
    #     Pareto100_subset_filepath_list.append(subset_filepath)
    # print("done with plot_single_Pareto_subset")
    # output_Pareto100subsets_filename = "_Pareto_subset_gen{}_slideshow.gif".format(gen_num)
    # create_slideshow(runFolder, Pareto100_subset_filepath_list, output_Pareto100subsets_filename)
    
    # hlp.plot_multi_gen_Pareto(runID, run_name, runFolder, [0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200], decimation=True)
    
##    for run_name in run_name_list:
##         runFolder = os.path.join(current_folder, run_name)
##         filename_list = [fn for fn in os.listdir(runFolder) if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
##         generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
##         generation_list.sort()
     
##    plot_num_of_unique_res(run_name_list, current_folder)
##    plot_avg_res_per_subset(run_name_list, current_folder)
##    print("done with {}".format(run_name))

    # plot_generation_breakdown(runFolder, run_name, 200)
    gen_num = 200
    # temp_run_name = os.path.join(run_name, "no_decim")
    # hlp.create_maps(current_folder, runID, run_name, gen_num)
    
    Pareto100_map_filepath_list = []
    Pareto100_map_subset_filepath_list = []
    for i in range(len(Pareto100_subsets)):
        subsetID = Pareto100_subsets[i]
        map_subset_filename = "_Pareto_map_subset_gen{}_{}.png".format(gen_num, subsetID)
        map_subset_filepath = os.path.join(runFolder, "images", map_subset_filename)
    #     # if os.path.exists(map_subset_filepath):
    #     #     continue

        map_filename = "_Pareto_map_gen{}_{}.png".format(gen_num, subsetID)
        map_filepath = os.path.join(runFolder, "images", map_filename)
        map_im = Image.open(map_filepath)

        subset_filename = "_Pareto_subset_gen{}_{}.png".format(gen_num, subsetID)
        subset_filepath = os.path.join(runFolder, "images", subset_filename)
        subset_im = Image.open(subset_filepath)
 
        hlp.get_concat_h_resize(map_im, subset_im).save(map_subset_filepath)
        Pareto100_map_subset_filepath_list.append(map_subset_filepath)
        hlp.add_border(map_subset_filepath)
    
    # # gif_Pareto100maps_filename = "_Pareto_maps_gen{}_slideshow.gif".format(gen_num)
    # # gif_Pareto100maps_filepath = os.path.join(runFolder, "images", gif_Pareto100maps_filename)
    # # # create_slideshow(runFolder, Pareto100_map_filepath_list, gif_Pareto100maps_filepath)
    # # video_Pareto100maps_filename = "_Pareto_maps_gen{}_slideshow.mp4".format(gen_num)
    # # video_Pareto100maps_filepath = os.path.join(runFolder, "images", video_Pareto100maps_filename)
    # # create_video(gif_Pareto100maps_filepath, video_Pareto100maps_filepath)

    # # gif_Pareto100subset_filename = "_Pareto_subset_gen{}_slideshow.gif".format(gen_num)
    # # gif_Pareto100subset_filepath = os.path.join(runFolder, "images", gif_Pareto100subset_filename)
    # # video_Pareto100subset_filename = "_Pareto_subset_gen{}_slideshow.mp4".format(gen_num)
    # # video_Pareto100subset_filepath = os.path.join(runFolder, "images", video_Pareto100subset_filename)
    # # create_video(gif_Pareto100subset_filepath, video_Pareto100subset_filepath)
    
    gif_Pareto100map_subset_filename = "_Pareto_map_subset_gen{}_slideshow.gif".format(gen_num)
    gif_Pareto100map_subset_filepath = os.path.join(runFolder, "images", gif_Pareto100map_subset_filename)
    video_Pareto100map_subset_filename = "_Pareto_map_subset_gen{}_slideshow.mp4".format(gen_num)
    video_Pareto100map_subset_filepath = os.path.join(runFolder, "images", video_Pareto100map_subset_filename)
    # # if os.path.exists(video_Pareto100map_subset_filepath):
    # #     continue
    hlp.create_slideshow(runFolder, Pareto100_map_subset_filepath_list, gif_Pareto100map_subset_filepath)
    hlp.create_video(gif_Pareto100map_subset_filepath, video_Pareto100map_subset_filepath)


