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
import data_cruncher as dc

# ok simple enough lol
#write ledger, read ledger, start job, restart job

# job name ; job_status ; job_type ; geometry_status
# status options : not started, running, failed, restarted, failed_twice, completed 
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
    shutil.move(f'./{job_name}/{job_name}.out',f'./{job_name}/history/{job_name}_snapshot.out')
    subprocess(f'mv "./{job_name}/slurm*.out" "./{job_name}/history/slurm*.out"',shell=True)
    pass

def clear_directory(job_name):
    '''
    deletes everything in a directory except the orbitals,
    input file, and output files.
    '''
    #make sure no exception occurs if the files don't exist,
    #or at least handle it
    shutil.move(f'./{job_name}/{job_name}.out',f'./{job_name}/history/{job_name}.out')
    shutil.move(f'./{job_name}/{job_name}.inp',f'./{job_name}/history/{job_name}.inp')
    shutil.move(f'./{job_name}/{job_name}.gbw',f'./{job_name}/history/{job_name}.gbw')
    shutil.move(f'./{job_name}/{job_name}.cube',f'./{job_name}/history/{job_name}.cube')
    shutil.move(f'./{job_name}/{job_name}.uno',f'./{job_name}/history/{job_name}.uno')
    subprocess(f'mv ./{job_name}/slurm*.out ./{job_name}/history/slurm*.out',shell=True)
    subprocess(f'rm ./{job_name}/* ',shell=True)

def restart_geom(job_name):
    '''
    expects name of job, and true/false whether
    it is a frequency job being restarted
    '''
    coords = jfe.get_orca_coordinates(f'./{job_name}/{job_name}.out')
    jfe.replace_geometry(f'./{job_name}/{job_name}.inp', coords)
    save_old_out_files(job_name)
    start_job(job_name)

def restart_freq(job_name):
    jfe.remove_opt_line(job_name)
    jfe.restart_geom(job_name)
    #maybe delete the directory here...
    
def restart_numfreq(job_name):
    jfe.add_freq_restart(job_name)
    jfe.restart_geom(job_name)

    #I should be using RIJCOSX with B3LYP



def read_state(job_name):
    '''
    The heavy hitter state reading function
    accepts a job_name
    returns the job_state and geometry_state
    '''
    #this one probably needs to read the slurm-%j.out file.
    #if that file is empty, we know the job is still running.
    #otherwise, we will assume the job ended.
    #we will then parse the ORCA out file to check if it ended well or poorly.
    # need to capture subprocess output here
    list_filenames = os.listdir(f'./{job_name}/')
    slurm_pattern = re.compile(r'slurm.\.out',re.IGNORECASE)
    slurm_filename = [file for file in list_filenames if re.search(slurm_pattern, file)][0]

    #should return a 1D dataframe
    #relevant column keys are completion_success and geometry_success
    job_status_df = dc.df_from_directory(f'./{job_name}/','ORCAmeta.rules','.out','slurm')
    
    with open(f'./{job_name}/slurm_filename','r') as slurmy:
        content = slurmy.read()
        if not content.strip():
            if job_status_df['geometry_success'] == True:
                return 'running','completed' #opt considered 'running' even if it finished
            else:
                return 'running','running'
        else:
            results = (job_status_df['completion_success'], job_status_df['geometry_success'])
            results = ['completed' if b else 'failed' for b in results]
            return tuple(results)


if __name__ == '__main__':
    complete = False
    try:
        ledger = read_ledger('ledger.csv')
    except:
        #batchfile is for now a textfile with a list of (job_name\n)'s
        ledger = read_batchfile('batch.txt')

    #variables, besides the state in the ledger:
    #(should read config or the batch file for this.)
    #(for now, it's hardcoded)
    num_jobs_running = 0
    max_jobs_running = 3

    while not complete:
        #repeat this only every 100 seconds
        write_ledger('ledger.csv')


        #check the status of the running jobs.
        #nothing should ever have the staus 'failed' 
        #after the block following this one. 
        #everything is 'not_started','running','restarted','twice_failed'
        for index, row in ledger[ledger['job_status'] == 'running'].iterrows():
            row['job_status'], row['geometry_status'] = read_state(row['job_name'])


        for index, row in ledger[ledger['job_status'] == 'restarted'].iterrows():
            updated_job_status, updated_geometry_status = read_state(row['job_name'])
            if updated_job_status == 'failed':
                row['job_status'] = 'failed_twice'



        #restart failed jobs, prune twice failed jobs
        for index, row in ledger.iterrows():
            #update job counter for completed jobs
            if row['job_status'] == 'completed':
                num_jobs_running -= 1
                print(f'Job {row['job_name']} completed.')
                print(f'{num_jobs_running} jobs running')

            #kill twice failed jobs
            elif row['job_status'] == 'failed_twice':
                clear_directory(row['job_name'])
                num_jobs_running -= 1
                print(f'Job {row['job_name']} failed.')
                print(f'{num_jobs_running} jobs running')

            elif row['job_status'] == 'failed':
                #so far, 
                geom_pattern = re.compile(r'opt',re.IGNORECASE)
                freq_pattern = re.compile(r'freq',re.IGNORECASE)
                numfreq_pattern = re.compile(r'numfreq',re.IGNORECASE)

                geom_condition = re.search(geom_pattern,row['job_type'])
                if geom_condition and re.row['geometry_status'] == 'failed':
                    restart_geom(row['job_name'])
                    row['geometry_status'] == 'restarted'
                    row['job_status'] == 'restarted'

                elif re.search(numfreq_pattern,row['job_type']):
                    restart_numfreq(row['job_name'])
                    row['job_status'] == 'restarted'

                elif re.search(freq_pattern,row['job_type']):
                    restart_freq(row['job_name'])
                    row['job_status'] == 'restarted'

                else: #if an SPE or property job fails, kill it
                    clear_directory(row['job_name'])
                    num_jobs_running -= 1
                    print(f'Job {row['job_name']} failed.')
                    print(f'{num_jobs_running} jobs still running')


        #queue up unstarted jobs
        while num_jobs_running < max_jobs_running:
            job_to_run = ledger[ledger['job_status'] == 'not_started'].iloc[0]['job_name']
            start_job(job_to_run)
            num_jobs_running += 1
        
        finished_criteria = ['completed','twice_failed']
        if ledger['job_status'].isin(finished_criteria).all():
            complete = True

        time.sleep(100)

    print()
    print('Batch job finished!')

#need to get this tested on the HPC today.
#all I need is a basic batch file that it can accept and some
#example jobs to run.
#that part is probably better completed at home.
#I'll just finish everything I think this needs and run it
#when I'm home and debug.
#then I can start submitting these jobs when I'm home.
#I think I can do it alone, too.

