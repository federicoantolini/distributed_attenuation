'''
sets up the files for wflow
sets up the list of subsets to run
sets up the job file for parallelization
runs the subsets using parall in argon
'''


import os
import subprocess
#import arcpy
import math
import time
import random
import copy
# import numpy as np
import pandas as pd
# import geopandas as gpd
# import pysal as ps

# import heur_geospatial as h_geo



def d2u(filename):
    '''
    converts formatting to UNIX friendly format
    '''
    d2u = subprocess.Popen(["dos2unix", filename])



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



def df_to_TXTfiles(df, gen_n, runFolder):
    '''
    creates the .ini files, a .txt file with the list of subsets to model, and the .txt files listing the damIDs in the subset
    '''
    resSubsets_TXTFolder = os.path.join(runFolder,"res_subsets")
    if not os.path.exists(resSubsets_TXTFolder):
        os.mkdir(resSubsets_TXTFolder)
    iniFolder = os.path.join(runFolder,"ini_files")
    if not os.path.exists(iniFolder):
        os.mkdir(iniFolder)
    
    with open(os.path.join(runFolder, "gen{}_subsets.txt".format(gen_n)), 'w') as gentxt:
        lines_to_copy = ''
        d2u(os.path.join(iniFolder,"wflow_sbm_reservoir_template.ini"))
        with open(os.path.join(iniFolder, "wflow_sbm_reservoir_template.ini"), 'r') as template_ini:
            lines_to_copy = template_ini.read()

        for subset_name in df.columns:
            if not os.path.exists(os.path.join(runFolder, subset_name)):
                damID_list = df.loc[df.loc[:, subset_name]==1, :].any(axis=1).index.tolist()
                with open(os.path.join(resSubsets_TXTFolder,"{}.txt".format(subset_name)), 'w') as f:
                    f.write("damID\n")
                    for damID in damID_list:
                        f.write("{}\n".format(damID))
                d2u(os.path.join(resSubsets_TXTFolder,"{}.txt".format(subset_name)))

                with open(os.path.join(iniFolder,"{}.ini".format(subset_name)), 'w') as ini:
                    ini.write("[files]\n")
                    ini.write("selected_reservoirs = res_subsets/{}.txt\n".format(subset_name))
                    ini.write("reservoir_coords = reservoirs/reservoir_coords.txt\n")
                    ini.write("reservoir_charact = reservoirs/all_reservoirs_df.txt\n")
                d2u(os.path.join(iniFolder,"{}.ini".format(subset_name)))

                with open(os.path.join(iniFolder,"wflow_sbm_reservoir_{}.ini".format(subset_name)), 'w') as ini:
                    ini.write(lines_to_copy)
                    ini.write("\n")
                    ini.write("[outputcsv_0]\n")
                    ini.write("samplemap = staticmaps/step2/wflow_gauges_fixed.map\n")
                    ini.write("self.SurfaceRunoff = run_max_{}.csv\n".format(subset_name))
                    ini.write("function = maximum\n")
                    ini.write("\n")
                    ini.write("[outputcsv_1]\n")
                    ini.write("samplemap = {}/reservoirs/ReservoirLocs_{}.map\n".format(subset_name, subset_name))
                    ini.write("self.SurfaceRunoff = reservoir_inflow_{}.csv\n".format(subset_name))
                    ini.write("self.OutflowSR = reservoir_outflow_{}.csv\n".format(subset_name))
                    ini.write("self.ReservoirVolume = reservoir_volume_{}.csv\n".format(subset_name))
                    ini.write("\n")
                d2u(os.path.join(iniFolder,"wflow_sbm_reservoir_{}.ini".format(subset_name)))


            
                gentxt.write("{}\n".format(subset_name))
    
    d2u(os.path.join(runFolder, "gen{}_subsets.txt".format(gen_n)))



def create_job(runFolder, gen_n, job_name, gentxt_filename, queue='UI-MPI', core_num=56, core_needed=56):
    '''
    creates the .job file to submit on HPC infrastructure (written for U Iowa's Argon)
    
    runFolder: folder w/ files for a certain rain event simulation, e.g. hewett_ts1min_70mm1_0mm5
    job_name: name of the job, e.g. hewett_gen0_run
    gentxt: txt w/ all the subsets to test, e.g. distribution_list_5.txt
    core_num: number of cores needed for the job, e.g. 56, 80, 64
    '''
    with open(gentxt_filename, 'r') as subsets_f:
        subsets_list = subsets_f.readlines()
        num_of_subsets = len(subsets_list)
    
    core_needed = math.ceil(num_of_subsets/core_num) * core_num  
    with open(os.path.join(runFolder, "gen{}_mpi_{}cpn.job".format(gen_n, core_num)), 'w') as jobf:
        jobf.write("#!/bin/sh\n")
        # jobf.write("#$ -cwd\n")  ##change folder, add cd later
        jobf.write("#$ -M federico-antolini@uiowa.edu -m e\n")
        jobf.write("#$ -N {}\n".format(job_name))
        jobf.write("#$ -q {}\n".format(queue))
        # jobf.write("#$ -q all.q\n")
        jobf.write("#$ -e {} -o {} -j y\n".format(runFolder, runFolder))
        jobf.write("#$ -pe {}cpn {}\n".format(core_num, core_needed))
        jobf.write("#OMP_NUM_THREADS=2\n")
        jobf.write("\nconda activate fedepy38\n")
        jobf.write("\ncd /Users/antolini/miniconda3/envs/fedepy38/lib/python3.8/site-packages/wflow\n")
        jobf.write("\nmpirun -n {} --map-by node python -m mpi_distrib_RR -C {} -D {}\n".format(num_of_subsets, runFolder, gentxt_filename))



def run_job(runFolder, job_filename, timeout=600):
    '''
    this function submits (qsub) the job in the UNIX environment
    the job contains an mpi function, which distributes the subsets/wflow runs among HPC nodes
    '''
    # job_filename = os.path.join(runFolder, job_name)
    mpi_run = subprocess.Popen(["qsub", job_filename], 
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT, 
    text=True
    )

    try:
        with open(os.path.join(runFolder, "stdout", job_filename + '_o.txt'), 'w') as output_file:
            output_file.write(mpi_run.stdout.read())
    except:
        pass
    try:
        with open(os.path.join(runFolder, "stdout", job_filename + '_e.txt'), 'w') as error_file:
            error_file.write(mpi_run.stderr.read())
    except:
        pass



def check_ready(runFolder, gentxt_filename, timesteps, gen_num, sleep_time=60):
    ''''
    check if files produced by parallel wflow runs are done, so that the script can move past
    if one of the parallel run is not ready, it will keep waiting and checking
    
    ** IF IT TAKES LONGER than expected, quit the job and check the output of wflow and of the job to see where an error occurred
    '''
    
    subset_list = []
    with open(gentxt_filename, 'r') as gentxt:
        line = gentxt.readline().strip()
        while line:
            subset_list.append(line)
            line = gentxt.readline().strip()

    ready = False
    try:
        for subset_name in subset_list:
            run_max_filename = os.path.join(runFolder,"{}".format(subset_name),"run_max_{}.csv".format(subset_name))
            q_df = pd.read_csv(run_max_filename, index_col="# Timestep")
            if q_df.shape[0] < timesteps:
                time.sleep(sleep_time)
                ready = False
                break
            else:
                ready = True
    except:
        time.sleep(sleep_time)
        ready = False
    return ready



def job_setup_and_launch(curr_generation_df, gen_num, runFolder, lowercase_watershed, timesteps, queue='UI-MPI', core_num=56, core_needed=56):
    '''
    for each subset in generation_df creates files to run wflow
    creates txt with list of subsets to run (gentxt_filename)
    creates job file (job_filename)
    
    '''
    # gen_name = get_name_from_num(gen_n, 2)
    # num_subsets_in_generation = curr_generation_df.shape[1]
    # digits = len(str(num_subsets_in_generation))
    df_to_TXTfiles(curr_generation_df, gen_num, runFolder)
    job_name = "{}_gen{}".format(lowercase_watershed[0], gen_num)
    gentxt_filename = os.path.join(runFolder, "gen{}_subsets.txt".format(gen_num))
    job_filename = os.path.join(runFolder, "gen{}_mpi_{}cpn.job".format(gen_num, core_num))
    create_job(runFolder, gen_num, job_name, gentxt_filename, queue, core_num, core_needed)
    run_job(runFolder, job_filename)

    sleep_command_counter = 0
    ready = False
    while not ready:
        ready = check_ready(runFolder, gentxt_filename, timesteps, gen_num, 60)
        sleep_command_counter += 1
        # if sleep_command_counter > 30:
        #     # subset_folder = os.path.join(runFolder,"{}_{}".format(gen_name, 0))
        #     if "{}_{}".format(gen_name, get_name_from_num(0, digits)) not in (os.listdir(runFolder)):
        #         print("\nThe job was not launched !!! Change queue, core_num or try later...\n")
        #         return

    # # i = 0
    # finished = False
    # while finished == False:
    #     in_runFolder = os.listdir(runFolder)
    #     if "0_0" in in_runFolder:
    #         in_subsetFolder = os.listdir(os.path.join(runFolder, "0_0"))
    #         if "run_max.csv" in in_subsetFolder:
    #             finished = True
    #         else:
    #             p.wait(timeout)
    #             continue
    #     else:
    #         p.wait(timeout)
    #         continue

            # for entry in it:
            #     if not entry.name.startswith('.') and entry.is_file():
            #         print(entry.name)
        # try:

        #     finished = True
        #     # exit_status_code = p.returncode
        # except:
        #     p.wait(timeout)
        #     i+=1
            # print(i, exit_status_code)
    # print("\nexit_status_code = {}\n".format(exit_status_code))

