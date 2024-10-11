#!/bin/bash

#SBATCH --job-name=test
#SBATCH -n 12
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 3-00:00:00
#SBATCH --mem-per-cpu=4GB

module purge
module load gaussian16
g16 < test.gjf > test.log
