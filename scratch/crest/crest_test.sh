#!/bin/bash

#SBATCH --job-name=crest_test
#SBATCH -n 12
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 3-00:00:00
#SBATCH --mem-per-cpu=2GB

conda activate crest3
export PYTHONUNBUFFERED=1
crest test.xyz > crest_test.out --gfn2 --chrg 0 --uhf 0 --cluster --quick --prop reopt
