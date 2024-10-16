#!/bin/bash

#SBATCH --job-name=xtbtest
#SBATCH -n 4
#SBATCH -N 1
#SBATCH -p genacc_q
#SBATCH -t 0-00:05:00
#SBATCH --mem-per-cpu=2GB

conda init bash
source ~/.bashrc
conda activate crest3
xtb test.xyz > xtbtest.out --gfn 2 --chrg 0 --uhf 0 --opt --cma
