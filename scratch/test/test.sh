#!/bin/bash

#SBATCH --job-name=test
#SBATCH -n 20
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 5-00:00:00
#SBATCH --mem-per-cpu=4GB

module load gnu/8.5.0 openmpi/4.1.6 orca/6.0.0
/gpfs/research/software/orca/orca_6_0_0_shared_openmpi416/orca test.inp > test.out
