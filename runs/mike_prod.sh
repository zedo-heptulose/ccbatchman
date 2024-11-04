#!/bin/bash

#SBATCH -n 1
#SBATCH -N 1
#SBATCH -A genacc_q
#SBATCH -t 1-00:00:00
export PYTHONUNBUFFERED=1
python3 mike_prod.py > mike_prod.log
