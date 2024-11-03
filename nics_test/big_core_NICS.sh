#!/bin/bash

#SBATCH --job-name=big_core_NICS
#SBATCH -n 1
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 0-00:05:00
#SBATCH --mem-per-cpu=3GB

~/code/pyAroma/src/preprocessingDriver.py big_core.xyz -o big_core_NICS.xyz -p Gaussian -v > big_core_NICS.txt
