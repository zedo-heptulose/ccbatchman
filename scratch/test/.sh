#!/bin/bash


module load gnu/8.5.0 openmpi/4.1.6 orca/6.0.0
/gpfs/research/software/orca/orca_6_0_0_shared_openmpi416/orca test.xyz > test.out -P 1 --gfn2 --opt
