#!/bin/bash

#SBATCH -n 1
#SBATCH -N 1
#SBATCH -A genacc_q
#SBATCH -t 3-00:00:00

conda init bash
source ~/.bashrc
conda activate automation_scripts
export PYTHONUNBUFFERED=1
export NUMEXPR_MAX_THREADS=1
python3 kimberley.py > kimberley.log
