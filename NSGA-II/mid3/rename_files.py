import os
import subprocess
# import glob

run_name_list = [
                # "mid_2080_01feb/",
                # "mid_5050_01feb/",
                # "mid_8020_01feb/",
                # "mid_2080SP_01feb/",
                # "mid_5050SP_01feb/",
                "mid_8020SP_01feb/"
                ]
cwd = os.getcwd()
for run_name in run_name_list:
    runFolder = os.path.join(cwd, run_name)
    # subprocess.call("cd "+run_name, shell=True)
    # subprocess.call("dir", shell=True)
    for gen_num in range(101,201):
        foldername_list = [fn for fn in os.listdir(runFolder) if fn.startswith("_"+str(gen_num)) and len(fn)==8]
        # new_foldername_list = [fn+"d" for fn in foldername_list]
        for fn in foldername_list:
            subprocess.call("mv " + run_name + fn + " " + run_name + fn[:-1], shell=True ) 
            # subprocess.call("mv " + run_name + fn + "/reservoir_inflow_" + fn[:-1] + "d.csv" + " " + run_name + fn + "/reservoir_inflow_" + fn[:-1] + ".csv", shell=True)
            # subprocess.call("mv " + run_name + fn + "/reservoir_outflow_" + fn[:-1] + "d.csv" + " " + run_name + fn + "/reservoir_outflow_" + fn[:-1] + ".csv", shell=True)
            # subprocess.call("mv " + run_name + fn + "/reservoir_volume_" + fn[:-1] + "d.csv" + " " + run_name + fn + "/reservoir_volume_" + fn[:-1] + ".csv", shell=True)
            # subprocess.call("mv " + run_name + fn + "/run_max_" + fn[:-1] + "d.csv" + " " + run_name + fn + "/run_max_" + fn[:-1] + ".csv", shell=True)
            # break
        # break
#     # for i in range(0,10):
#     #     subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/cover*", shell=True)
#     #     subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/wflow*", shell=True)
#     #     subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/intbl/*", shell=True)
        print("done with {}\n".format(gen_num))
#     subprocess.call("cd ..", shell=True)

    
    # for gen_num in range(101, 201):
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_subsets.csv" + " " + run_name + "gen" + str(gen_num) + "d_subsets.csv", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_subsets.txt" + " " + run_name + "gen" + str(gen_num) + "d_subsets.txt", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_mpi_56cpn.job" + " " + run_name + "gen" + str(gen_num) + "d_mpi_56cpn.job", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_mpi_56cpn.job_e.txt" + " " + run_name + "gen" + str(gen_num) + "d_mpi_56cpn.job_e.txt", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_mpi_56cpn.job_o.txt" + " " + run_name + "gen" + str(gen_num) + "d_mpi_56cpn.job_o.txt", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_qpeak_cost.csv" + " " + run_name + "gen" + str(gen_num) + "d_qpeak_cost.csv", shell=True)
    #     subprocess.call("mv " + run_name + "gen" + str(gen_num) + "_qpeak_cost_rank.csv" + " " + run_name + "gen" + str(gen_num) + "d_qpeak_cost_rank.csv", shell=True)
    #     # foldername_list = [fn for fn in os.listdir(runFolder) if fn.startswith("_"+str(gen_num))]
    # subsetsFolder = os.path.join(cwd, run_name, "res_subsets/")
    # for gen_num in range(101, 201):
    #     subsetname_list = [fn for fn in os.listdir(subsetsFolder) if fn.startswith("_"+str(gen_num)) and len(fn)==12]
    #     for fn in subsetname_list:
    #         subprocess.call("mv " + subsetsFolder + fn + " " + subsetsFolder + fn[:8] + "d.txt", shell=True)
