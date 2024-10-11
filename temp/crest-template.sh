#!/bin/bash

#SBATCH --job-name=<job_name>

#SBATCH -n 20
#SBATCH -N 1
#SBATCH --mem-per-cpu=2GB

#SBATCH -p genacc_q

#SBATCH -t 5-00:00:00

start=$(date +%s) 

echo "Calculation started on $(date)" >> RUNTIME
export PYTHONUNBUFFERED=1 

crest <job_name>.xyz > <job_name>.out --T 20 --uhf 2 --chrg 0 --gfn2 --cluster --quick

end=$(date +%s)
secs=$((end - start))
printf '%dh:%dm:%02ds\n' $((secs / 3600)) $(((secs % 3600) / 60)) $((secs % 60)) >> RUNTIME

