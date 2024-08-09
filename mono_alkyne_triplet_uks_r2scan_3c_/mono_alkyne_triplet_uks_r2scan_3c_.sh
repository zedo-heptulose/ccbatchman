#!/bin/bash

#SBATCH --job-name=mono_alkyne_triplet_uks_r2scan_3c_

#SBATCH --mail-user=gdb20@fsu.edu
#SBATCH --mail-type=FAIL

#SBATCH -n 8
#SBATCH -N 1

#SBATCH -p genacc_q

#SBATCH -t 3-00:00:00
#SBATCH --mem=32GB

module load gnu openmpi orca

/gpfs/research/software/orca/orca_5_0_1_linux_x86-64_openmpi411/orca mono_alkyne_triplet_uks_r2scan_3c_.inp > restart_mono_alkyne_triplet_uks_r2scan_3c_.out

