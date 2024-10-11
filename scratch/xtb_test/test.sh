#!/bin/bash

#SBATCH --job-name=test
#SBATCH -n 4
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 0-00:05:00
#SBATCH --mem-per-cpu=4GB

ulimit -s unlimited
export OMP_MAX_ACTIVE_LEVELS=1
export OMP_STACKSIZE=4G
export OMP_NUM_THREADS=4,1
/gpfs/home/gdb20/.conda/envs/crest3/bin/xtb test.xyz > test.out -P 4 --gfn2 --opt
