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


# seems to work fine.
def read_batchfile(filename):
    '''
    this file should contain a list of filenames to run,
    with some config commands allowed as well.
    creates a ledger from the batchfile
    '''
    batch = pd.read_csv(f'./{filename}',delimiter='|')
    ledger = pd.DataFrame() 
    ledger['job_name'] = batch.iloc[:,0]
    ledger['job_type'] = batch.iloc[:,1]
    ledger['job_status'] = ['not_started' for i in range (len(batch))]
    ledger['geometry_status']=['not_started' for i in range (len(batch))]
    return ledger

# seems to work fine.
def read_ledger(filename):
    #for now the ledger is stored loose in the directory; make a separate folder if this gets
    #unmanageable
    return pd.read_csv(f'./{filename}',delimiter=';')
    
# seems to work fine.
def write_ledger(ledger, filename):
    ledger.to_csv(filename, sep=';', index=False)


############needs to be tested live######
def start_job(job_name):
    '''
    assumes this script is placed in a directory, containing directories containing jobs and
    input files.
    '''
    #needs to be tested on the HPC
    #this is in testing mode and is a dummy function for now
    print(f'sbatch "./{job_name}/*.sh"')
    #subprocess.run(f'sbatch "./{job_name}/*.sh"',shell=True)


# seems to work fine. 
# shell permissions need to be tested live
#for all of them, should save the old output file in a subdirectory.
def save_old_out_files(job_name):
    os.makedirs(f'./{job_name}/history/', exist_ok=True)
    shutil.copy2(f'./{job_name}/{job_name}.out',f'./{job_name}/history/{job_name}_snapshot.out')
    subprocess.run(f'mv ./{job_name}/slurm*.out ./{job_name}/history/slurm_history.out',shell=True)
    pass



############needs to be tested live######
def clear_directory(job_name):
    '''
    deletes everything in a directory except the orbitals,
    input file, and output files.
    '''
    #make sure no exception occurs if the files don't exist,
    #or at least handle it
    subprocess.run(f'rm ./{job_name}/*.tmp',shell=True)





# seems to work fine. 
def restart_geom(job_name):
    '''
    expects name of job, and true/false whether
    it is a frequency job being restarted
    '''
    coords = jfe.get_orca_coordinates(f'./{job_name}/{job_name}.out')
    jfe.replace_geometry(f'./{job_name}/{job_name}.inp', coords)
    save_old_out_files(job_name)
    start_job(job_name)




# seems to work fine. 
def restart_freq(job_name):
    jfe.remove_opt_line(f'./{job_name}/{job_name}.inp')
    restart_geom(job_name)
    #maybe delete the directory here...



# seems to work fine. 
def restart_numfreq(job_name):
    jfe.add_freq_restart(f'./{job_name}/{job_name}.inp')
    restart_geom(job_name)

    #I should be using RIJCOSX with B3LYP YEAH, NOW I AM


# seems to work fine. 
def read_state(job_name):
    '''
    The heavy hitter state reading function
    accepts a job_name
    returns the job_state and geometry_state
    '''
    #fix that it just expects an empty slurm file
    # both failed works, only geom worked works, both completed works
    # both running works, both running geom completed works
    # call it good
    list_filenames = os.listdir(f'./{job_name}/')
    slurm_pattern = re.compile(r'slurm.+\.out',re.IGNORECASE)
    try:
        slurm_filename = [file for file in list_filenames if re.search(slurm_pattern, file)][0]
    except:
        return 'error','error'

    #should return a 1D dataframe
    #relevant column keys are completion_success and geometry_success
    job_status_df = dc.df_from_directory(f'./{job_name}/','ORCAmeta.rules',['.out'],['slurm'],recursive=False)
    print(job_status_df)
    with open(f'./{job_name}/{slurm_filename}','r') as slurmy:
        content = slurmy.read()
        if not content.strip(): #this is a really bad solution.
                                #this will break. find a more general way.
            if job_status_df['geometry_success'].iloc[0] == True:
                return 'running','completed' #opt considered 'running' even if it finished
            else:
                return 'running','running'
        else:
            results = (job_status_df['completion_success'].iloc[0], job_status_df['geometry_success'].iloc[0])
            results = ['completed' if b else 'failed' for b in results]
            return tuple(results)

def update_state(df,num_jobs_running):
    '''
    decrements counter based on number of completed jobs
    '''
    # Update job_status and geometry_status for rows where job_status is 'running'
    running_mask = df['job_status'] == 'running'
    for index in df[running_mask].index:
        updated_job_status, updated_geometry_status = read_state(df.at[index, 'job_name'])
        df.at[index, 'job_status'] = updated_job_status
        df.at[index, 'geometry_status'] = updated_geometry_status

    # # Update job_status for rows where job_status is 'restarted'
    # restarted_mask = df['job_status'] == 'restarted'
    # for index in df[restarted_mask].index:
    #     updated_job_status, updated_geometry_status = read_state(df.at[index, 'job_name'])
    #     if updated_job_status == 'failed':
    #         df.at[index, 'job_status'] = 'failed_twice'

    # Update job counter for completed jobs
    completed_jobs = ledger[ledger['job_status'] == 'completed']
    num_jobs_running -= len(completed_jobs)
    # for job_name in completed_jobs['job_name']:
    #     print(f'Job {job_name} completed.')
    # print(f'{num_jobs_running} jobs running')

    return num_jobs_running



def act_on_state(ledger, num_jobs_running):
    '''
    clears directories of failed jobs, decrements counter.
    '''
    # Define patterns for matching job types
    geom_pattern = re.compile(r'opt', re.IGNORECASE)
    freq_pattern = re.compile(r'freq', re.IGNORECASE)
    numfreq_pattern = re.compile(r'numfreq', re.IGNORECASE)

    # # Kill twice failed jobs
    # failed_twice_jobs = ledger[ledger['job_status'] == 'failed_twice']
    # num_jobs_running -= len(failed_twice_jobs)
    # for job_name in failed_twice_jobs['job_name']:
    #     clear_directory(job_name)
    #     print(f'Job {job_name} failed.')
    # print(f'{num_jobs_running} jobs running')

    # Handle failed jobs with specific conditions
    failed_jobs = ledger[ledger['job_status'] == 'failed']
    for index, row in failed_jobs.iterrows():
        job_name = row['job_name']
        job_type = row['job_type']
        geom_status = row['geometry_status']
        
        # this should only be here if restart functionality is not being used.
        clear_directory(job_name)
        num_jobs_running -= 1
        print(f'Job {job_name} failed.')
        print(f'{num_jobs_running} jobs still running')
        
        # if geom_pattern.search(job_type) and geom_status == 'failed':
        #     restart_geom(job_name)
        #     ledger.at[index, 'geometry_status'] = 'restarted'
        #     ledger.at[index, 'job_status'] = 'restarted'
        
        # elif numfreq_pattern.search(job_type):
        #     restart_numfreq(job_name)
        #     ledger.at[index, 'job_status'] = 'restarted'

        # elif freq_pattern.search(job_type):
        #     restart_freq(job_name)
        #     ledger.at[index, 'job_status'] = 'restarted'
        
        # else:  # If an SPE or property job fails, kill it
        #     clear_directory(job_name)
        #     num_jobs_running -= 1
        #     print(f'Job {job_name} failed.')
        #     print(f'{num_jobs_running} jobs still running')

        #TODO: HANDLE OOM KILL

    return num_jobs_running

def queue_new_jobs(ledger,num_jobs_running,max_jobs_running):
    job_mask = ledger['job_status'] == 'not_started'
    jobs_to_run = ledger[job_mask]
    for index, row in ledger.iterrows():
        if (num_jobs_running >= max_jobs_running):
            return num_jobs_running
        if ledger.at[index,'job_status'] == 'not_started':
            job_to_run = ledger.at[index,'job_name']
            start_job(job_to_run)
            num_jobs_running += 1
            ledger.at[index,'job_status'] = 'running'
    
    return num_jobs_running
    
def check_finished(ledger):
    
    finished_criteria = ['completed','twice_failed']
    if ledger['job_status'].isin(finished_criteria).all():
        return True
    else:
        return False

if __name__ == '__main__':
    complete = False
    try:
        ledger = read_ledger('__ledger__.csv',sep='|')
    except:
        #batchfile is for now a textfile with a list of (job_name\n)'s
        ledger = read_batchfile('batchfile.csv',sep='|')

    #variables, besides the state in the ledger:
    #(should read config or the batch file for this.)
    #(for now, it's hardcoded)
    num_jobs_running = 0
    max_jobs_running = 3

    while not complete:
        
        #store in-memory ledger to file
        #update ledger
        
        ledger.to_csv('__ledger__.csv',sep='|')
        
        num_jobs_running = update_state(ledger)
        
        num_jobs_running = act_on_state(ledger,num_jobs_running)
        
        num_jobs_running = queue_new_jobs(ledger,num_jobs_running,max_jobs_running)

        
        ledger.to_csv('__ledger__.csv',sep='|')
        
        complete = check_finished(ledger)

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

