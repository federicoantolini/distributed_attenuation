import os
import getopt
import glob
import sys
import subprocess

from mpi4py import MPI

configs = ["mix0001",
           "mix2001",
           "0601667",
           "cen2301",
           "ds43201",
           "mix6n01",
           "mix6y01",
           "ne43201",
           "us54321"]

def main(argv=None):
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    
    caseName = "/Users/antolini/Volga/Hewett"
    distributions_file = caseName + "distribution_list_1.txt"
    
    if argv is None:
        argv = sys.argv[1:]
        if len(argv) == 0:
            usage()
            return
    
    
    try:
        opts, args = getopt.getopt(argv, "C:D:")
    except getopt.error as msg:
        pcrut.usage(msg)

    for o, a in opts:
        if o == "-C":
            caseName = a
        if o == "-D":
            distributions_file = a
            
    inputFolder = caseName
    # distributions_file = inputFolder + os.path.sep + distributions_file
    distributions_list = []
    
    if rank == 0:
        #os.mkdir(inputFolder + "/stdout/")
        with open(distributions_file) as file:
            line = file.readline()  #no header in the distributions file
            while line:
                distrib = line.strip()
                distributions_list.append(distrib)
                line = file.readline()
    
    distributions_list = comm.bcast(distributions_list, root=0)
    comm.Barrier()
    
    for i, distrib in enumerate(distributions_list):
        if i%size != rank:
            continue
        
        # distrib   is parameter for  -R
        initialization_file = os.path.join("ini_files", "wflow_sbm_reservoir.ini")   #-c
        distrib_subset_file = os.path.join("ini_files", distrib + ".ini")   #-r
#        command_string = "python -m wflow_sbm_federico -C {} -R {} -c {} -r {} -f".format(inputFolder,
#                                                          distrib,
#                                                          initialization_file,
#                                                          distrib_subset_file)
#        # os.system(command_string)
        distrib_run = subprocess.Popen(["python", "-m", "wflow_sbm_federico",
                          "-C", inputFolder, "-R", distrib,
                          "-c", initialization_file,
                          "-r", distrib_subset_file,
                          "-f"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd="/Users/antolini/miniconda3/lib/python3.7/site-packages/wflow",
        text=True
        )
        with open(inputFolder + '/stdout/' + distrib + '_o.txt', 'w') as output_file:
            output_file.write(distrib_run.stdout.read())


        
if __name__ == "__main__":
    main()        
            