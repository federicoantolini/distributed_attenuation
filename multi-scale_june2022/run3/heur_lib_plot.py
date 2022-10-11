'''
contain all the graphic functions to visualize spatial optimization and distributed attenuation results
'''

from email.mime import image
from enum import unique
import os
import time
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import geoplot as gplt
import geoplot.crs as gcrs
import cartopy.crs as ccrs

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib import gridspec
from matplotlib.ticker import FormatStrFormatter
import imageio
from PIL import Image, ImageOps

import heur_geospatial as h_geo

pd.set_option('mode.chained_assignment', None)



def run_notes(runID, run_name):
    '''
    creates the text describing the spatial optimization process and its parameters
    ** CHANGE HERE based on the customized graph you want to make
    '''
    
    title_components = run_name.split('_')
    region_dict = {"up":"upstream", "mid":"midstream", "down":"downstream", 
    "all":"Whole catchment\noptimization",  "comb":"Whole catchment optimization\nOptimization per region until gen 50"}
    # region = region_dict[title_components[0]]
    region="whole catchment"
    # crossover_proportion_str = "{}%".format(title_components[1][:2])
    # mutation_proportion_str = "{}%".format(title_components[1][2:4])
    # special_subsets_use = "NO"
    # if "SP" in title_components[1]:
    #     special_subsets_use = "YES"
    
    #"runID: {}\n".format(runID) + \
    notes_str = ""#"Scale: {}".format(region)# + \
                # "{}\n".format(runID) + \
                # "Crossover: {}\n".format(crossover_proportion_str) + \
                # "Mutation: {}\n".format(mutation_proportion_str) + \
                # "Special subset: {}".format(special_subsets_use)
    
    return notes_str



def plot_single_generation(df, runID, run_name, gen_num, runFolder):
    '''
    plots subsets as point in a dual-objective cartesian plan
    full color for Pareto-optimal, transparent for the others
    '''
    rank_num_list = df['rank'].unique()

    notes_str = run_notes(runID, run_name)
    
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "{}, Generation {}".format(runID, gen_num)
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)

    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, labelpad=7)

    df.loc[:,'cost_million'] = df.loc[:, 'cost']/1000000
    
    for rank_num in rank_num_list:
        rank_df = df[df['rank']==rank_num]
        if rank_num == 0:
            alpha = 1
            label = "Pareto"
        else:
            alpha = 0.05
            label = None
        ax.plot(rank_df["Qpeak_reduction"], rank_df["cost_million"], linestyle='None', 
                marker='o', color='blue', markersize=5, alpha=alpha, 
                label=label
                )
    
    notes = ax.text(0.04, 0.94, notes_str, transform=ax.transAxes, fontsize=13,
                    verticalalignment='top')
    notes.set_bbox(dict(boxstyle='round', facecolor='whitesmoke', edgecolor="darkgrey"))
    # shadow = matplotlib.patches.Shadow(notes.get_bbox_patch(), 10/72., -10/72)
    # ax.add_patch(shadow)
    # notes.patch.get_frame().set_facecolor = "red"

    #set legend
    leg = ax.legend(loc=(0.03, 0.66), fontsize=13, shadow=False) #'upper left'
    leg.get_frame().set_facecolor('whitesmoke')

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)
    # fig.patch.set_linewidth(2.8)
    # fig.patch.set_edgecolor('black')
    fig_filepath = os.path.join(runFolder,"images", "_gen{}.png".format(gen_num))
    fig.savefig(fig_filepath, 
                facecolor='white', edgecolor='black', 
                # linewidth=1.5
                )
    plt.close()
    add_border(fig_filepath)



def plot_single_Pareto_subset(Pareto_df, runID, run_name, gen_num, subsetID, runFolder):
    '''
    plots only the Pareto-optimal subsets, as points
    transparent color for Pareto-optimal, full color only for subsetID point   
    '''
    notes_str = run_notes(runID, run_name)

    gen_Pareto_df = Pareto_df.loc[(gen_num, ),:]
    subset_ser = Pareto_df.loc[(gen_num, subsetID), :]
   
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "{}, Generation {}".format(runID, gen_num)
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)

    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, labelpad=7)

    gen_Pareto_df.loc[:,'cost_million'] = gen_Pareto_df.loc[:,'cost']/1000000
    subset_ser.loc['cost_million'] = subset_ser.loc['cost']/1000000
    
    ax.plot(gen_Pareto_df["Qpeak_reduction"], gen_Pareto_df["cost_million"],
            linestyle='None',
            marker='o', markersize=7, 
            color='blue',
            alpha=0.05, 
            )

    ax.plot(subset_ser["Qpeak_reduction"], subset_ser["cost_million"], 
            linestyle='None',
            marker='o', markersize=7, 
            color='blue',
            alpha=1.0, 
            label="Pareto"
            )
    
    notes = ax.text(0.04, 0.94, notes_str, transform=ax.transAxes, fontsize=13,
                    verticalalignment='top')
    notes.set_bbox(dict(boxstyle='round', facecolor='whitesmoke', edgecolor="darkgrey"))

    #set legend
    leg = ax.legend(loc=(0.03, 0.70), fontsize=13, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)
    # fig.patch.set_linewidth(2.8)
    # fig.patch.set_edgecolor('black')
    filename = "_Pareto_subset_gen{}_{}.png".format(gen_num, subsetID)
    fig_filepath = os.path.join(runFolder,"images", filename)
    fig.savefig(fig_filepath,
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(fig_filepath)



def plot_multi_gen_Pareto(runID, run_name, runFolder, gen_num_list, decimation=False):
    '''
    plots Pareto frontiers (lines) for each generation in gen_num_list
    ** CHANGE HERE to customize the graph, e.g., colors, other graphical params
    '''
    gen1 = gen_num_list[0]
    gen_last = gen_num_list[-1]

    Pareto_filepath = os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, gen1, gen_last))
    Pareto_df = pd.read_csv(Pareto_filepath)
    
    notes_str = run_notes(runID, run_name, decimation)

    prop_cycle = plt.rcParams['axes.prop_cycle']
    # colors = prop_cycle.by_key()['color']   # predefined colors are 10
    colors = ["blue", "lightcoral", "limegreen", "goldenrod", "deepskyblue", "red", "springgreen", "darkorange"]
    colors = ["yellowgreen", 'limegreen', "mediumaquamarine", "darkcyan", "steelblue", "darkblue"]
    blue_colors = ["lightblue", "lightskyblue", "skyblue", "deepskyblue", "dodgerblue", "cornflowerblue", "royalblue", "mediumblue", "midnightblue"]
    blue_colors = ["lightblue", "lightskyblue", "deepskyblue", "dodgerblue", "royalblue", "blue", "midnightblue"]
    red_colors = ['peachpuff', 'lightsalmon', 'coral', 'orangered', 'indianred', 'darkred']
    # colors = 'GnBu'
    cmap = plt.get_cmap('winter', len(gen_num_list))
    # cmaplist = [cmap(i) for i in range(cmap.N)]
    colors = cmap(np.linspace(1, 0.1, 6))
    alphas = np.linspace(start=0.1, stop=1.0, num=len(gen_num_list))

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "pareto"
    if gen_num_list=='all':
        image_filename += gen_num_list
    else:
        for gen_num in gen_num_list:
            image_filename += '_g{}'.format(gen_num)


    if gen_num_list=='all':
        gen_num_list = Pareto_df['gen'].unique()
    for i in range(len(gen_num_list)):
        gen_num = gen_num_list[i]
        gen_df = Pareto_df[Pareto_df['gen']==gen_num]
        gen_df.sort_values(by='cost', inplace=True)
        gen_df.loc[:,'cost_million'] = gen_df.loc[:, 'cost']/1000000
        # if rank_num == 0:
        #     alpha = 1
        #     label = "Pareto"
        # else:
        #     alpha = 0.05
        #     label = None
        
        # if gen_num<=100:
        ax.plot(gen_df["Qpeak_reduction"], gen_df["cost_million"], linestyle='-', 
                marker='None', 
                # color=colors[i], 
                color=blue_colors[i],
                # color="darkblue",
                # alpha=alphas[i],
                alpha=1.0,
                linewidth=1.5, markersize=5,
                label='gen {}'.format(gen_num)
                )
        # if gen_num>100:
        #     ax.plot(gen_df["Qpeak_reduction"], gen_df["cost_million"], linestyle='-', 
        #             marker='None', 
        #             # color=colors[i], 
        #             color=red_colors[i-5],
        #             # color="darkblue",
        #             # alpha=alphas[i],
        #             alpha=1.0,
        #             linewidth=1.5, markersize=5,
        #             label='gen {}'.format(gen_num)
        #             )
    
    notes = ax.text(0.04, 0.94, notes_str, transform=ax.transAxes, fontsize=12,
                    verticalalignment='top')
    notes.set_bbox(dict(boxstyle='round', facecolor='whitesmoke', edgecolor="darkgrey"))

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.17-len(gen_num_list)*.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(runFolder,"images", "{}.png".format(image_filename))
    fig.savefig(os.path.join(runFolder,"images", "{}.png".format(image_filename)), 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_num_of_unique_res(run_name_list, current_folder):
    '''
    plots number of unique reservoirs used within a generation
    '''
    # prop_cycle = plt.rcParams['axes.prop_cycle']
    # colors = prop_cycle.by_key()['color']
    colors = ["blue", "lightcoral", "limegreen", "goldenrod", "deepskyblue", "red", "springgreen", "darkorange"]

    fig, ax = plt.subplots(figsize=[9, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

    title = "Unique reservoirs per generation"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)

    ax.set_xlim(xmin=-1, xmax=102)
    ax.set_xticks([i for i in range(102) if i%10==0])
    ax.set_xticklabels([i for i in range(102) if i%10==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=500)
    ax.set_yticks([i for i in range(500) if i%50==0])
    ax.set_yticklabels([i for i in range(500) if i%50==0], fontsize=13)

    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel('Generation number', size=16, labelpad=7)
    ax.set_ylabel("Num of unique reservoirs", size=16, y=0.5, labelpad=7)
    
    for i in range(len(run_name_list[:3])):
        run_name = run_name_list[i]
        runFolder = os.path.join(current_folder, run_name)
        filename_list = [fn for fn in os.listdir(runFolder) if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
        generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
        generation_list.sort()
        summary_df = pd.read_csv(os.path.join(runFolder,"num_of_subsets_summary_{}-{}_gen_{}.csv".format(generation_list[0], generation_list[-1], run_name)))
        ax.plot(summary_df.index, summary_df["num_of_unique_res"], linestyle='-', 
                    marker=None, color=colors[i], linewidth=1.5, markersize=4, alpha=1.0, # 0.3
                    # label='_'+run_name,
                    label = run_name,
                    )

    leg = ax.legend(loc='lower left', fontsize=14, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.96, left=0.10)
    # fig.patch.set_linewidth(2.8)
    # fig.patch.set_edgecolor('black')
    image_filename = "unique_reservoirs_plot_1" # 2
    image_filepath = os.path.join(runFolder,"images", "{}.png".format(image_filename))
    fig.savefig(image_filepath,
                facecolor='white', edgecolor='black')
    add_border(image_filepath)



def plot_avg_res_per_subset(run_name_list, current_folder):
    '''
    plot number of unique reservoirs used within a generation
    '''
    # prop_cycle = plt.rcParams['axes.prop_cycle']
    # colors = prop_cycle.by_key()['color']
    colors = ["blue", "lightcoral", "limegreen", "goldenrod", "deepskyblue", "red", "springgreen", "darkorange"]

    fig, ax = plt.subplots(figsize=[9, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

    title = "Average number of reservoirs per subset"
    ttl = ax.title
    ttl.set_position([0.5,1.00])
    ax.set_title(title, fontsize=18, y=1.03)

    ax.set_xlim(xmin=-1, xmax=102)
    ax.set_xticks([i for i in range(102) if i%10==0])
    ax.set_xticklabels([i for i in range(102) if i%10==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=500)
    ax.set_yticks([i for i in range(500) if i%50==0])
    ax.set_yticklabels([i for i in range(500) if i%50==0], fontsize=13)

    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel('Generation number', size=16, labelpad=7)
    ax.set_ylabel("Avg num of reservoirs", size=16, y=0.5, labelpad=7)
    
    for i in range(len(run_name_list[:3])):
        run_name = run_name_list[i]
        runFolder = os.path.join(current_folder, run_name)
        filename_list = [fn for fn in os.listdir(runFolder) if fn.endswith("qpeak_cost_rank.csv") and fn.startswith("gen") ]
        generation_list = [ int(fn.split('_')[0][3:]) for fn in filename_list]
        generation_list.sort()
        summary_df = pd.read_csv(os.path.join(runFolder,"num_of_subsets_summary_{}-{}_gen_{}.csv".format(generation_list[0], generation_list[-1], run_name)))
        ax.plot(summary_df.index, summary_df["avg_res_in_subset"], linestyle='-', 
                    marker=None, color=colors[i], linewidth=1.5, markersize=4, alpha=1.0, # 0.3
                    # label='_'+run_name,
                    label = run_name,
                    )

    leg = ax.legend(loc=1, fontsize=14, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.96, left=0.10)
    # fig.patch.set_linewidth(2.8)
    # fig.patch.set_edgecolor('black')
    image_filename = "average_num_of_res_plot_1" # 2
    image_filepath = os.path.join(runFolder,"images", "{}.png".format(image_filename))
    fig.savefig(image_filepath,
                facecolor='white', edgecolor='black')
    add_border(image_filepath)



def create_slideshow(runFolder, filename_list, output_filename):
    '''
    creates a GIF file, frames in filename_list
    It saves the .gif
    '''
    gif_filename = os.path.join(runFolder, "images", output_filename)
    with imageio.get_writer(gif_filename, mode="I") as writer:
        for i in range(len(filename_list)):
            filename = filename_list[i]
            image = imageio.imread(filename)
            if i==0:
                for j in range(10):
                    writer.append_data(image)
            elif i==(len(filename_list)-1):
                for j in range(20):
                    writer.append_data(image)
            else:
                writer.append_data(image)



def get_concat_h_resize(im1, im2, resample=Image.BICUBIC, resize_big_image=True):
    '''
    resizes and concatenates images i1 and im2 side by side
    returns the mosaicked image 
    '''
    if im1.height == im2.height:
        _im1 = im1
        _im2 = im2
    elif (((im1.height > im2.height) and resize_big_image) or
          ((im1.height < im2.height) and not resize_big_image)):
        _im1 = im1.resize((int(im1.width * im2.height / im1.height), im2.height), resample=resample)
        _im2 = im2
    else:
        _im1 = im1
        _im2 = im2.resize((int(im2.width * im1.height / im2.height), im1.height), resample=resample)
    dst = Image.new('RGB', (_im1.width + _im2.width, _im1.height))
    dst.paste(_im1, (0, 0))
    dst.paste(_im2, (_im1.width, 0))
    return dst



def add_border(in_filepath, border=2):
    '''
    adds a border around the image
    It saves the image to the same in_filepath
    '''
    with Image.open(in_filepath) as im:
        im1 = ImageOps.expand(im, border=border, fill='black')
        im1.save(in_filepath)



def create_video(input_filepath, video_filepath):
    '''
    takes a GIF file in input and converts it into an .mp4 file
    It saves the file
    '''
    with imageio.get_reader(input_filepath, 'gif') as reader:
        dur = (float(reader.get_meta_data()['duration']))

        with imageio.get_writer(video_filepath, fps=3, quality=8.0) as writer:
            for frame in reader:
                writer.append_data(frame)



def plot_generation_breakdown(runFolder, runID, run_name, gen_num=100):
    '''
    plots vertical bar chartof subsets in generation gen_num
    x-axis is the generation num in which the subsets were created
    y-axis is the number of subsets created in a given generation
    most Pareto-optimal subsets were created in the last generation, but some are older
    If many subsets are old, get passed over to new generations, are not replaced by new better ones --> optimization is converging
    '''

    notes_str = run_notes(runID, run_name)

    Pareto_df = pd.read_csv(os.path.join(runFolder, "Pareto_{}_{}-{}.csv".format(run_name, 50, gen_num)), index_col=["gen","subsetID"])
    gen_breakdown_df = Pareto_df.loc[(gen_num,), "created_in_gen"]
    num_of_appearances_series = gen_breakdown_df.value_counts()
    num_of_appearances_series.sort_index(inplace=True)
    gen_of_origin_list = num_of_appearances_series.index.tolist()
    # print(type(num_of_appearances_series.tolist()[0]))
    
    fig, ax = plt.subplots(figsize=[9, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Breakdown of subsets in gen {}".format(gen_num)
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=len(gen_of_origin_list))
    ax.set_xticks([i for i in range(len(gen_of_origin_list))])
    ax.set_xticklabels(gen_of_origin_list, fontsize=10)

    ax.set_ylim(ymin=0, ymax=num_of_appearances_series.max()+2)
    ax.set_yticks([i for i in range(0, num_of_appearances_series.max()+2, 5)])
    ax.set_yticklabels([i for i in range(0, num_of_appearances_series.max()+2, 5)], fontsize=13)
    
    ax.grid(color='black', axis='y', alpha=0.2)
    ax.set_xlabel("Generation of origin", size=16, labelpad=7)
    ax.set_ylabel("Number of subsets", size=16, labelpad=7)

    ax.bar(x=[i for i in range(len(gen_of_origin_list))],
            height=num_of_appearances_series.tolist(),
            width=0.8,
            bottom=0, 
            color="dodgerblue", edgecolor="navy",
            alpha=1.0
            )

    notes = ax.text(0.04, 0.94, notes_str, transform=ax.transAxes, fontsize=12,
                    verticalalignment='top')
    notes.set_bbox(dict(boxstyle='round', facecolor='whitesmoke', edgecolor="darkgrey"))

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.96, left=0.10)
    image_filename = "generation_{}_breakdown.png".format(gen_num)
    image_filepath = os.path.join(runFolder,"images", image_filename)
    fig.savefig(image_filepath,
                facecolor='white', edgecolor='black')
    add_border(image_filepath)
   



def create_maps(current_folder, runID, run_name, gen_num):
    '''
    creates a simple map with the stream network and the reservoirs
    one map for each subset in generation gen_num
    map .png are saved    
    '''
    imageFolder = os.path.join(current_folder, run_name, "images")
    shpFolder = os.path.join(current_folder, run_name, "reservoirs_shp")
    reservoirFolder = os.path.join(current_folder, run_name, "reservoirs")

    current_folder_components = os.path.abspath(os.getcwd()).split(os.sep)
    reservoir_locations_folder = os.path.join(os.sep,
        current_folder_components[0],
##        current_folder_components[1],
##        current_folder_components[2],
        "heuristics", "reservoir_locations"
    )
    
    stream_filename = os.path.join(reservoirFolder, "allStreams_NAD83_hewett.shp")
##    reach_filename = os.path.join(reservoir_locations_folder, "allReaches_NAD83_w_distToOutlet.shp")
    damPoints_filename = os.path.join(reservoirFolder, "damPoints_NAD83_w_distToOutlet.shp")
    reservoirPolyg_shp_filename = os.path.join(reservoirFolder, "reservoirPolygon2.0_by_Vmax_to_damLength_design_cost.shp")
    resPolyg_df = gpd.read_file(reservoirPolyg_shp_filename)
    resPolyg_df = resPolyg_df.set_index("damID", drop=False)
    # resPolyg_df = h_geo.clean_resPolyg_df(orig_resPolyg_df)
    resPolyg_df.rename(columns={"CChaul_tot": "cost"}, inplace=True)

    obj_df_filename = os.path.join(current_folder, run_name, "gen{}_qpeak_cost_rank.csv".format(gen_num))
    obj_df = pd.read_csv(obj_df_filename, index_col=["subsetID"])
    Pareto_df = obj_df.loc[obj_df["rank"] == 0, :]
    subset_list = Pareto_df.index.tolist()

    gen_df_filepath = os.path.join(current_folder, run_name, "gen{}_subsets.csv".format(gen_num))
    gen_df = pd.read_csv(gen_df_filepath, index_col="damID")        

    streamLines_df = gpd.read_file(stream_filename)
    streamLines_df = streamLines_df.set_index("streamID", drop=False)
    streamLines_df.rename(columns={"Horton": "Strahler"}, inplace=True)
    streamLines_df_wgs84 = streamLines_df.to_crs("EPSG:4326")
    streamLines_df_Albers = streamLines_df.to_crs("EPSG:5070")
          
    for i in range(len(subset_list)):
        subsetID = subset_list[i]
        fig_filepath = os.path.join(imageFolder, "_Pareto_map_gen{}_{}.png".format(gen_num, subsetID))
        # if os.path.exists(fig_filepath):
        #     continue
        
        #create shapefile of the subset
        subset_series = gen_df.loc[:, subsetID]
        damID_list = subset_series[subset_series==1].index.tolist()
        subset_resPolyg_df = resPolyg_df.loc[damID_list, :]
        subset_resPolyg_df = subset_resPolyg_df.set_index("_FID", drop=True)
        subset_resPolyg_shp_filename = os.path.join(shpFolder, "{}_{}.shp".format(runID, subsetID))
        subset_resPolyg_df.to_file(subset_resPolyg_shp_filename)

        qpeak_reduction = Pareto_df.at[subsetID, "Qpeak_reduction"]
        cost = Pareto_df.at[subsetID, "cost"]
        # print(qpeak_reduction, cost)
        
        #create map of stream and subset polyg
        # subset_resPolyg_df = 
        subset_resPolyg_df = subset_resPolyg_df.set_index("damID", drop=False)
        subset_resPolyg_df_wgs84 = subset_resPolyg_df.to_crs("EPSG:4326")
        subset_resPolyg_df_Albers = subset_resPolyg_df.to_crs("EPSG:5070")

        # fig, ax = plt.subplots(figsize=[7, 7], facecolor='whitesmoke')
        # fig = plt.figure(figsize=(7,7), linewidth=1.8, edgecolor="black")
        ax = gplt.sankey(df=streamLines_df_wgs84, 
                        # projection=ccrs.UTM(zone=15),
                        # projection=subset_resPolyg_df.crs,
                        projection = gcrs.AlbersEqualArea(),
                        scale='Strahler',
                        limits=(0.5, 1.8),
                        color="lightskyblue",
                        alpha=0.8,
                        # legend=True,
                        figsize=(7,7)
                        )
        
        extent_mid = (-91.6250, 42.7177, -91.4990, 42.7965)
        gplt.polyplot(
            df=subset_resPolyg_df_wgs84,
            # projection=ccrs.epsg(zone=15),
            # projection=subset_resPolyg_df.crs,
            projection = gcrs.AlbersEqualArea(),
            facecolor='navy',
            edgecolor='navy',
            alpha=1.0,
            extent=extent_mid,
            ax=ax
        )
        
        # qpeak_string = r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$'
        unit_string = r'$\mathregular{m^\mathregular{3} \/ s^\mathregular{-1}}$'
        ax.set_title("Peak flow reduction:  {:.2f} ".format(qpeak_reduction) + \
            unit_string +"\nConstruction cost:  ${:,.2f}".format(cost),
                    fontsize=18,
                    loc='left',
                    y=0.98,
                    pad=6,
                    )
        # fig_filename = os.path.join(imageFolder, "streams_and_{}.png".format(subsetID))
        # for j in range(1000):
            # print("ciao")
        # plt.gcf().subplots_adjust(top=0.99, bottom=0.05, right=1.0, left=0.05)
        # plt.figure(linewidth=2.8)
        fig_filepath = os.path.join(imageFolder, "_Pareto_map_gen{}_{}.png".format(gen_num, subsetID))
        plt.savefig(fig_filepath, bbox_inches='tight', pad_inches=0.1, 
                    facecolor='white', edgecolor='black', dpi=100)
        if i%8==0:
            time.sleep(10)
            plt.close('all')
        add_border(fig_filepath)
        print("saved {}".format(subsetID))


def get_concat_2x2_resize(im1_f, im2_f, im3_f, im4_f, border, resample=Image.BICUBIC, resize_big_image=True):
    '''
    resizes and concatenates 4 images in a 4x4 matrix
    returns a mosaicked image
    '''
    with Image.open(im1_f) as im1:
        with Image.open(im2_f) as im2:
            with Image.open(im3_f) as im3:
                with Image.open(im4_f) as im4:   
        
                    if im1.height == im2.height == im3.height == im4.height:
                        print("heights are all the same")
                    else:
                        print(im1.height, im2.height, im3.height, im4.height)

                    if im1.width == im2.width == im3.width == im4.width:
                        print("widths are all the same")
                    else:
                        print(im1.width, im2.width, im3.width, im4.width)

    # if im1.height == im2.height:
    #     _im1 = im1
    #     _im2 = im2
    # elif (((im1.height > im2.height) and resize_big_image) or
    #       ((im1.height < im2.height) and not resize_big_image)):
    #     _im1 = im1.resize((int(im1.width * im2.height / im1.height), im2.height), resample=resample)
    #     _im2 = im2
    # else:
    #     _im1 = im1
    #     _im2 = im2.resize((int(im2.width * im1.height / im2.height), im1.height), resample=resample)
    
    # if im3.height == im3.height:
    #     _im3 = im3
    #     _im4 = im4
    # elif (((im3.height > im4.height) and resize_big_image) or
    #       ((im3.height < im4.height) and not resize_big_image)):
    #     _im3 = im3.resize((int(im3.width * im4.height / im3.height), im4.height), resample=resample)
    #     _im4 = im4
    # else:
    #     _im3 = im3
    #     _im4 = im4.resize((int(im4.width * im3.height / im4.height), im3.height), resample=resample)
    
    # if im1.width == im3.width:
    #     _im1 = im1
    #     _im3 = im3
    # elif (((im1.width > im3.width) and resize_big_image) or
    #       ((im1.width < im3.width) and not resize_big_image)):
    #     _im1 = im1.resize((int(im1.height * im3.width / im1.width), im3.width), resample=resample)
    #     _im3 = im3
    # else:
    #     _im1 = im1
    #     _im3 = im3.resize((int(im3.height * im1.width / im3.width), im1.width), resample=resample)
    
    # if im2.width == im4.width:
    #     _im2 = im2
    #     _im4 = im4
    # elif (((im2.width > im4.width) and resize_big_image) or
    #       ((im2.width < im4.width) and not resize_big_image)):
    #     _im2 = im2.resize((int(im2.height * im4.width / im2.width), im4.width), resample=resample)
    #     _im4 = im4
    # else:
    #     _im2 = im2
    #     _im4 = im4.resize((int(im4.height * im2.width / im4.width), im2.width), resample=resample)
      
                    dst = Image.new('RGB', (im1.width + im2.width - border, im1.height + im3.height - border))
                    dst.paste(im1, (0, 0))
                    dst.paste(im2, (im1.width-border, 0))
                    dst.paste(im3, (0, im1.height-border))
                    dst.paste(im4, (im1.width-border, im1.height-border))
    return dst 

    

def plot_multi_region_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run3 optimization
    plots Pareto frontiers as lines     
    ** CHANGE HERE the generation number you want to plot
    '''
    current_folder = os.getcwd()
    run_name_list = ["regionA", "regionB", "regionC", "regionD"]
    last_gen_num = 20
    
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=21)
    ax.set_xticks([i for i in range(21) if i%5==0])
    ax.set_xticklabels([i for i in range(21) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=2.55)
    ax.set_yticks([i/10 for i in range(26) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(26) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "pareto_A_B_C_D"

    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], linestyle='-', 
                marker='None', 
                color=colors[i], 
                alpha=1.0,
                linewidth=1.5, markersize=5,
                label='Region {}'.format(region[-1])
                )

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "regionABCD","images", "{}.png".format(image_filename))
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_umd_region_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run2 optimization
    plots Pareto frontiers as lines     
    ** CHANGE HERE the generation number you want to plot
    '''
    
    current_folder = os.getcwd()
    run_name_list = ["up_22apr", "mid_22apr", "down_22apr"]
    last_gen_num_dict = {"up_22apr":50, "mid_22apr":50, "down_22apr":50}
    region_name_dict = {"up_22apr":'Upstream', "mid_22apr":'Midstream', "down_22apr":'Downstream'}
    
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]
    linestyles = ['-', '--', ':']

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=41)
    ax.set_xticks([i for i in range(41) if i%5==0])
    ax.set_xticklabels([i for i in range(41) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=3.55)
    ax.set_yticks([i/10 for i in range(36) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(36) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "pareto_umd"

    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_num = last_gen_num_dict[region]
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=linestyles[i], 
                marker='None', 
                color='k', 
                alpha=1.0,
                linewidth=1.5, markersize=5,
                label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
        )

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "comb_umd_14may","images", "{}.png".format(image_filename))
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_run2_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run2 optimization
    plots Pareto frontiers as lines     
    ** CHANGE HERE the generation number you want to plot
    '''
    current_folder = os.getcwd()
    run_name_list = ["up_22apr", "mid_22apr", "down_22apr", "comb_umd_14may"]
    last_gen_num_dict = {"up_22apr":50, "mid_22apr":50, "down_22apr":50, "comb_umd_14may":200}
    region_name_dict = {"up_22apr":'upstream', "mid_22apr":'midstream', "down_22apr":'downstream', "comb_umd_14may":"whole watershed"}
    color_dict = {"up_22apr":'k', "mid_22apr":'k', "down_22apr":'k', "comb_umd_14may":'darkorange'}
    linestyle_dict = {"up_22apr":':', "mid_22apr":'--', "down_22apr":'-', "comb_umd_14may":'-'}
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]
    linestyles = [':', '--', '-']

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers, run 2"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "run2_pareto.png"

    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_num = last_gen_num_dict[region]
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=linestyle_dict[region], 
                marker='None', 
                color=color_dict[region], 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
        )

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "images", image_filename)
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_run3_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run3 optimization
    plots Pareto frontiers as lines     
    ** CHANGE HERE the generation number you want to plot
    '''
    current_folder = os.getcwd()
    run_name_list = ["regionA", "regionB", "regionC", "regionD", "regionABCD_plus"]
    last_gen_num_dict = {"regionA":20, "regionB":20, "regionC":20, "regionD":20, "regionABCD_plus":60}
    region_name_dict = {"regionA":'A', "regionB":'B', "regionC":'C', "regionD":"D", "regionABCD_plus":"A B C D"}
    color_dict = {"regionA":'k', "regionB":'k', "regionC":'grey', "regionD":'grey', "regionABCD_plus":"forestgreen"}
    linestyle_dict = {"regionA":'-', "regionB":':', "regionC":'-', "regionD":':', "regionABCD_plus":'-'}
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]
    linestyles = [':', '--', '-']

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers, run 3"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "run3_pareto.png"

    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_num = last_gen_num_dict[region]
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=linestyle_dict[region], 
                marker='None', 
                color=color_dict[region], 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
        )
    
    region = run_name_list[-1]
    last_gen_num = 200
    last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
    last_gen_df = pd.read_csv(last_gen_filepath)
    last_gen_df = last_gen_df[last_gen_df['rank']==0]
    last_gen_df.sort_values(by='cost', inplace=True)
    last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
    ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=linestyle_dict[region], 
                marker='None', 
                color="limegreen", 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format("whole watershed", last_gen_num)
    )

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*.064-.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "images", image_filename)
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_run1_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run1 optimization
    plots Pareto frontiers as lines    
    ** CHANGE HERE the generation number you want to plot 
    '''
    current_folder = os.getcwd()
    run_name_list = ["all_22apr"]
    last_gen_num_dict = {"all_22apr":200}
    region_name_dict = {"all_22apr":"whole watershed"}
    color_dict = {"all_22apr":'blue'}
    linestyle_dict = {"all_22apr":'-'}
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]
    linestyles = [':', '--', '-']

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers, run 1"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "run1_pareto.png"

    region = run_name_list[-1]
    last_gen_num = 0
    last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
    last_gen_df = pd.read_csv(last_gen_filepath)
    last_gen_df = last_gen_df[last_gen_df['rank']==0]
    last_gen_df.sort_values(by='cost', inplace=True)
    last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
    ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle='--', 
                marker='None', 
                color="grey", 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format("whole watershed", last_gen_num)
    )
    
    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_num = last_gen_num_dict[region]
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=linestyle_dict[region], 
                marker='None', 
                color=color_dict[region], 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
        )
    
    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*.064-0.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "images", image_filename)
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)



def plot_run123_Pareto():
    '''
    specific function for plotting Pareto frontiers produced in run1, run2, run3 optimization
    plots Pareto frontiers as lines    
    ** CHANGE HERE the generation number you want to plot 
    '''
    current_folder = os.getcwd()
    run_name_list = ["all_22apr", "comb_umd_14may", "regionABCD_plus"]
    last_gen_num_dict = {"all_22apr":200, "comb_umd_14may":200, "regionABCD_plus":200}
    region_name_dict = {"all_22apr":"run 1", "comb_umd_14may":"run 2", "regionABCD_plus":"run 3"}
    color_dict = {"all_22apr":'blue', "comb_umd_14may":'darkorange', "regionABCD_plus":"limegreen"}
    linestyle_dict = {"all_22apr":'-', "comb_umd_14may":'-', "regionABCD_plus":'-'}
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = ["limegreen", "darkorange", "darkviolet", "dimgrey"]
    linestyles = [':', '--', '-']

        
    fig, ax = plt.subplots(figsize=[8, 5.2], facecolor='whitesmoke')
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    
    title = "Pareto frontiers"
    ttl = ax.title
    ttl.set_position([0.5,1.05])
    ax.set_title(title, fontsize=18, y=1.03)
    
    ax.set_xlim(xmin=-1, xmax=68)
    ax.set_xticks([i for i in range(66) if i%5==0])
    ax.set_xticklabels([i for i in range(66) if i%5==0], fontsize=13)
    
    ax.set_ylim(ymin=0, ymax=5.05)
    ax.set_yticks([i/10 for i in range(51) if i%5==0])
    ax.set_yticklabels([i/10 for i in range(51) if i%5==0], fontsize=13)
    
    ax.grid(color='black', axis='both', alpha=0.2)
    ax.set_xlabel(r'$\mathregular{Peak \/ flow \/ reduction \/\/ [m^\mathregular{3} \/ s^\mathregular{-1}]}$', size=16, labelpad=7)
    ax.set_ylabel("Construction cost, $M", size=16, y=0.5, labelpad=7)
    
    image_filename = "run123_60only_pareto.png"

    for i in range(len(run_name_list)):
        region = run_name_list[i]
        last_gen_num = 60
        last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
        last_gen_df = pd.read_csv(last_gen_filepath)
        last_gen_df = last_gen_df[last_gen_df['rank']==0]
        last_gen_df.sort_values(by='cost', inplace=True)
        last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
        ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
                linestyle=':', 
                marker='None', 
                color=color_dict[region], 
                alpha=1.0,
                linewidth=2.0, markersize=5,
                label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
        )
    
    # for i in range(len(run_name_list)):
    #     region = run_name_list[i]
    #     last_gen_num = last_gen_num_dict[region]
    #     last_gen_filepath = os.path.join(current_folder, region, "gen{}_qpeak_cost_rank.csv".format(last_gen_num))
    #     last_gen_df = pd.read_csv(last_gen_filepath)
    #     last_gen_df = last_gen_df[last_gen_df['rank']==0]
    #     last_gen_df.sort_values(by='cost', inplace=True)
    #     last_gen_df.loc[:,'cost_million'] = last_gen_df.loc[:, 'cost']/1000000
        
    #     ax.plot(last_gen_df["Qpeak_reduction"], last_gen_df["cost_million"], 
    #             linestyle=linestyle_dict[region], 
    #             marker='None', 
    #             color=color_dict[region], 
    #             alpha=1.0,
    #             linewidth=2.0, markersize=5,
    #             label='{}, gen {}'.format(region_name_dict[region], last_gen_num)
    #     )

    #set legend
    leg = ax.legend(loc=(0.03, (1-0.03-len(run_name_list)*2*.064)), fontsize=12, shadow=False)
    leg.get_frame().set_facecolor('whitesmoke')
    leg.get_frame().set_alpha(1.0)

    plt.gcf().subplots_adjust(top=0.89, bottom=0.15, right=0.97, left=0.11)

    image_filepath = os.path.join(current_folder, "images", image_filename)
    fig.savefig(image_filepath, 
                facecolor='white', edgecolor='black')
    plt.close()
    add_border(image_filepath)