#!/bin/bash

#SBATCH --job-name=stgap1

#SBATCH --mail-user=gdb20@fsu.edu
#SBATCH --mail-type=END

#SBATCH -n 8
#SBATCH -N 1

#SBATCH -p genacc_q

#SBATCH -t 0-12:00:00
#SBATCH --mem=24GB

module load gnu openmpi orca

/gpfs/research/software/orca/orca_5_0_1_linux_x86-64_openmpi411/orca stgap1.inp > stgap1.out
