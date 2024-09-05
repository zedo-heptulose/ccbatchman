import os
import shutil
import subprocess
import re

def import_orca(c_dir):
    subprocess.run(f'module import gnu openmpi orca',shell=True,cwd=container_dir)

def request_orbitals(jobname, container_dir = False):
    if container_dir == False:
        container_dir = './{jobname}'
    import_orca(container_dir)
    process1 = subprocess.run(f'orca_2mkl {jobname} -molden',shell=True,cwd=container_dir)
    process2 = subprocess.run(f'orca_plot {jobname}.uno -i',shell=True,cwd=container_dir)

def request_uvvis_spectra(jobname,container_dir = False):
    if container_dir == False:
        container_dir = './{jobname}'
    import_orca(container_dir)
    process1 = subprocess.run(f'orca_mapspc {jobname}.out ABS -x010000 -x130000 -w1000',shell=True,cwd=container_dir)

def uvvis_whole_dir(directory):
    jobnames = os.listdir(directory)
    for job in [job for job in jobnames if not '.' in job]:
        request_uvvis_spectra(job,f'directory/{job}')
    
def orbitals_whole_dir(directory):
    jobnames = os.listdir(directory)
    for job in [job for job in jobnames if not '.' in job]:
        request_orbitals(job,f'directory/{job}')

