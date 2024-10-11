#!/bin/bash

#SBATCH --job-name=h2o2_gas_crest
#SBATCH -n 12
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 3-00:00:00
#SBATCH --mem-per-cpu=2GB

conda init bash
source ~/.bashrc
conda activate crest3
export PYTHONUNBUFFERED=1
crest h2o2.xyz > h2o2_gas_crest.out --gfn2 --chrg 0 --uhf 0 --cluster --noreftopo
