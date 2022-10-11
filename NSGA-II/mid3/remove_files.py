import os
import subprocess
import glob

run_name_list = [
                "mid_2080_01feb/",
                # "mid_5050_01feb/",
                "mid_8020_01feb/",
                "mid_2080SP_01feb/",
                # "mid_5050SP_01feb/",
                # "mid_8020SP_01feb/d1/"
                "mid_8020SP_01feb"
                ]
cwd = os.getcwd()
for run_name in run_name_list:
#     runFolder = os.path.join(cwd, run_name)
#     subprocess.Popen(["cd", run_name])
    for i in range(1,7):
        subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/reservoirs/*", shell=True)
        # subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/outstate/*", shell=True)
        # subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/cover*", shell=True)
        # subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/wflow*", shell=True)
        # subprocess.call("rm " + "-r " + run_name + "_" + str(i) + "*/intbl/*", shell=True)
#     subprocess.Popen(["cd",".."])
        print("done with {}\n".format(i))
    print("done with {}\n".format(run_name))