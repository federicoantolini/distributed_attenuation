import os
import subprocess
import glob

# run_name_list = [
#                 # "upstream/",
#                 # "midstream/",
#                 # "downstream/",
#                 "all_22apr/",
#                 # "comb_umd_14may/"
#                 ]
# cwd = os.getcwd()
# for run_name in run_name_list:
# #     runFolder = os.path.join(cwd, run_name)
# #     subprocess.Popen(["cd", run_name])
#     for i in range(2,10):
#         for j in range(0,10): 
#             subprocess.call("rm " + "-r " + run_name + "_" + str(i) + str(j) + "*/reservoirs/*", shell=True)           
#             # subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/outstate/*", shell=True)
#             subprocess.call("rm " + "-r " + run_name + "_" + str(i) + str(j) + "*/cover*", shell=True)
#             subprocess.call("rm " + "-r " + run_name + "_" + str(i) + str(j) + "*/wflow*", shell=True)
#             subprocess.call("rm " + "-r " + run_name + "_" + str(i) + str(j) + "*/intbl/*", shell=True)
#     #     subprocess.Popen(["cd",".."])
#         print("done with {}".format(i))
#     print("done with {}\n".format(run_name))
    
    
def remove_useless_files(run_name, gen_num):
    if gen_num < 10:
        gen_num_str = str(0) + str(gen_num)
    elif gen_num < 100:
        gen_num_str = str(gen_num) + str(0)
    else:
        gen_num_str = str(gen_num)
    subprocess.call("rm " + "-r " + run_name + "/_" + gen_num_str + "*/reservoirs/*", shell=True)           
    subprocess.call("rm " + "-r " + run_name + "/_" + gen_num_str + "*/cover*", shell=True)
    subprocess.call("rm " + "-r " + run_name + "/_" + gen_num_str + "*/wflow*", shell=True)
    subprocess.call("rm " + "-r " + run_name + "/_" + gen_num_str + "*/intbl/*", shell=True)
    #     subprocess.Popen(["cd",".."])
    print("done with {}".format(gen_num))
    print("done with {}\n".format(run_name))