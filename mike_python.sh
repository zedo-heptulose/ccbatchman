#!/bin/bash

#SBATCH -n 8
#SBATCH -N 1
#SBATCH -A genacc_q
#SBATCH -t 1-00:00:00

module load python/3
export PYTHONUNBUFFERED=1
export NUMEXPR_MAX_THREADS=8
python3 mike_prod.py > mike_prod.log
