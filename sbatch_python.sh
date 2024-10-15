#!/bin/bash

#SBATCH -n 1
#SBATCH -N 1
#SBATCH -A genacc_q
#SBATCH -t 0-01:00:00

module load python/3
export PYTHONUNBUFFERED=1
python3 batch_runner_testing.py > testing.log
