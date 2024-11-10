#!/bin/bash

#SBATCH -n 1
#SBATCH -N 1
#SBATCH -A genacc_q
#SBATCH -t 1-00:00:00

conda init bash
source ~/.bashrc
conda activate automation_scripts
export PYTHONUNBUFFERED=1
export NUMEXPR_MAX_THREADS=1
python3 mike_test.py > mike_test.log
