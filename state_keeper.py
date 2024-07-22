#read and write to ledger file

#read from batch file

#read from orca files to check state

#main function loop with a sleep timer, carries out these instructions as needed

#ignore memory for now, just have it set a limit of how many run at once

#would then need to group together jobs of like size. We can figure out more later


#ledger file is a csv; uses a pd.DataFrame in memory operations

#assumes jobs each in their own subdirectory below this script

#for now, only one layer

import pandas as pd
import subprocess
import job_file_editor as jfe
import os 
import shutil
import time
import re

# ok simple enough lol
#write ledger, read ledger, start job, restart job

# job name ; job_status ; job_type ; geometry_status
# status options : not started, running, failed, restarted, twice failed, completed 
# type options : 

def read_batchfile(filename):
    '''
    this file should contain a list of filenames to run,
    with some config commands allowed as well.
    '''


def read_ledger(filename):
    #for now the ledger is stored loose in the directory; make a separate folder if this gets
    #unmanageable
    return pd.read_csv(f'./{filename}')

def write_ledger(filename):
    pd.to_csv(filename)

def check_done(filename):
    pass

def start_job(job_name):
    '''
    assumes this script is placed in a directory, containing directories containing jobs and
    input files.
    '''
    subprocess.run(f'sbatch "./{job_name}/*.sh"',shell=True)

#what handles what?
#do we detect what type of failure occurs when restarting the job?
#do I use one function for this, or a separate one for every type of reset?
#would be cool to always replace the geometry, maybe.
#in general, use the simplest functions possible as building blocks.

#for all of them, should save the old output file in a subdirectory.
def save_old_out_files(job_name):
    shutil.move(f'./{job_name}/{job_name}.out','./{job_name}/history/{job_name}_snapshot.out')
    subprocess(f'mv "./{job_name}/slurm*.out" "./{job_name}/history/slurm*.out"',shell=True)
    pass

def clear_directory(job_name):
    '''
    deletes everything in a directory except the orbitals,
    input file, and output files.
    '''
    #make sure no exception occurs if the files don't exist,
    #or at least handle it
    shutil.move(f'./{job_name}/{job_name}.out','./{job_name}/history/{job_name}.out')
    shutil.move(f'./{job_name}/{job_name}.inp','./{job_name}/history/{job_name}.inp')
    shutil.move(f'./{job_name}/{job_name}.gbw','./{job_name}/history/{job_name}.gbw')
    shutil.move(f'./{job_name}/{job_name}.cube','./{job_name}/history/{job_name}.cube')
    shutil.move(f'./{job_name}/{job_name}.uno','./{job_name}/history/{job_name}.uno')
    subprocess(f'mv ./{job_name}/slurm*.out ./{job_name}/history/slurm*.out',shell=True)
    subprocess(f'rm ./{job_name}/* ',shell=True)

def restart_geom(job_name):
    '''
    expects name of job, and true/false whether
    it is a frequency job being restarted
    '''
    coords = jfe.get_orca_coordinates(f'./{job_name}/{job_name}.out')
    jfe.replace_geometry(f'./{job_name}/{job_name}.inp', coords)
    save_old_outfile(job_name)
    start_job(job_name)

def restart_freq(job_name):
    jfe.remove_opt_line(job_name)
    jfe.restart_geom(job_name)
    #maybe delete the directory here...
    
def restart_numfreq(job_name):
    jfe.add_freq_restart(job_name)
    jfe.restart_geom(job_name)

    #I should be using RIJCOSX with B3LYP



if __name__ == '__main__':
    complete = False
    try:
        ledger = read_ledger('ledger.csv')
    except:
        #batchfile is for now a textfile with a list of (job_name\n)'s
        ledger = read_batchfile('batch.txt')

    #variables, besides the state in the ledger:
        #num_jobs_running
        #max_jobs_running

    while not complete:
        #repeat this only every 100 seconds
        write_ledger('ledger.csv')

        #restart failed jobs
        for index, row in ledger.iterrows():
            if row['job_status'] == 'failed':
                #so far, 
                if row['job_type']
                if row['geometry_status']
        #kill twice failed jobs

        #queue up unstarted jobs
        while num_jobs_running < max_jobs_running:
            job_to_run = leger[leger['job_status'] == 'not_started'].iloc[0]['job_name']
            start_job(job_to_run)
        


        time.sleep(100)
        if check_done(ledger):
            complete = True


#need to get this tested on the HPC today.
#all I need is a basic batch file that it can accept and some
#example jobs to run.
#that part is probably better completed at home.
#I'll just finish everything I think this needs and run it
#when I'm home and debug.
#then I can start submitting these jobs when I'm home.
#I think I can do it alone, too.

