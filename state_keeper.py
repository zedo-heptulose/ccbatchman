#ledger file is a csv; uses a pd.DataFrame in memory operations
import re
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

# job_name ; job_status ; job_type ; geometry_status ; job_id
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
    #ledger['job_type'] = batch.iloc[:,1]
    ledger['depends_on'] = batch.iloc[:,1].fillna('')
    ledger['job_status'] = ['not_started' for i in range (len(batch))]
    ledger['geometry_status']=['not_started' for i in range (len(batch))]
    ledger['job_id']=[-1 for i in range (len(batch))]
    
    return ledger

# seems to work fine.
def read_ledger(filename):
    #for now the ledger is stored loose in the directory; make a separate folder if this gets
    #unmanageable
    return pd.read_csv(f'./{filename}',delimiter='|')
    
# seems to work fine.
def write_ledger(ledger, filename):
    ledger.to_csv(filename, sep='|', index=False)


def start_job(job_name):
    #TODO: address that sometimes slurm submissions fail
    # ex, too many jobs currently running, memory quota, etc
    #MAKE SURE UTF8 IS RIGHT FOR THIS
    processdata = subprocess.run(f'sbatch *.sh',shell=True,cwd=f'../{job_name}/',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output = processdata.stdout.decode('utf-8')
    #TODO: delete this print statement when done using it
    print(f'output:{output}')
    try:
        job_id = int(re.search('\d+',output).group(0))
        return job_id
    except:
        return -2
    #TODO: parent process should acknowledge an error if this is recieved



def clear_directory(job_name):
    '''
    deletes everything in a directory except the orbitals,
    input file, and output files.
    '''
    #make sure no exception occurs if the files don't exist,
    #or at least handle it
    subprocess.run(f'rm *.tmp',cwd=f'../{job_name}/',shell=True)





# # seems to work fine. 
# def restart_geom(job_name):
#     '''
#     expects name of job, and true/false whether
#     it is a frequency job being restarted
#     '''
#     coords = jfe.get_orca_coordinates(f'./{job_name}/{job_name}.out')
#     jfe.replace_geometry(f'./{job_name}/{job_name}.inp', coords)
#     save_old_out_files(job_name)
#     start_job(job_name)




# # seems to work fine. 
# def restart_freq(job_name):
#     jfe.remove_opt_line(f'./{job_name}/{job_name}.inp')
#     restart_geom(job_name)
#     #maybe delete the directory here...



# # seems to work fine. 
# def restart_numfreq(job_name):
#     jfe.add_freq_restart(f'./{job_name}/{job_name}.inp')
#     restart_geom(job_name)

# seems to work fine. 
def read_state(job_name, job_id):
    '''
    The heavy hitter state reading function
    accepts a job_name
    returns the job_state and geometry_state
    '''
    
    #capture slurm output here, use it in the business logic
    
    #the fifth capture group (\b.+\b) will be the job status
    #R is running
    #PD is pending
    #that's good enough for now
    #need to recognize bad job.
    
    in_progress = True
    slurm_status = "N/A"

    for attempt in range(5):    
        try:
            processdata = subprocess.run(f'squeue --job {job_id}',shell=True,cwd=f'../{job_name}/',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            output = processdata.stdout.decode('utf-8')
            print(f'OUTPUT: {output}')
            if re.search('error:',output):
                in_progress = False
            else:
                captureline = output.splitlines()[1] 
                slurm_status = re.search(r'(?:\S+\s+){4}(\S+)',captureline).group(1)  
            break
        except:
            print("Bad capture of squeue response")

            #I lied, error error can also come from this
            #not sure if job should die for this, but for the time being it will

    #print(job_status_df)
    print(f'status:{slurm_status}')   
    if slurm_status == 'PD':
        #TODO: implement a pending status for the ledger
        return 'running','running'

    try:
      job_status_df = dc.df_from_directory(f'../{job_name}/','ORCAmeta.rules',['.out'],['slurm'],recursive=False)
      results = (job_status_df['completion_success'].iloc[0], job_status_df['geometry_success'].iloc[0])
    except:
        print("#########################\nBAD READ\n###########################")
        return 'error','error'
        #this is the ONLY way to get 'error' as a status, is if files can't be read
    
    if in_progress and slurm_status == 'R':
        if job_status_df['geometry_success'].iloc[0] == True:
            return 'running','completed' #opt considered 'running' even if it finished
        else:
            return 'running','running'

    else:
        results = ['completed' if b else 'failed' for b in results]
        return tuple(results)

def update_state(df,num_jobs_running):
    '''
    decrements counter based on number of completed jobs
    '''
    #TODO: fix bug that causes crash here 
    # Update job_status and geometry_status for rows where job_status is 'running'
    running_mask = df['job_status'] == 'running'
    for index in df[running_mask].index:
        #the offending line vvv 
        updated_job_status, updated_geometry_status = read_state(df.at[index, 'job_name'],df.at[index,'job_id'])
        if not updated_job_status == 'error':
            df.at[index, 'job_status'] = updated_job_status
            df.at[index, 'geometry_status'] = updated_geometry_status

    # # Update job_status for rows where job_status is 'restarted'
    # restarted_mask = df['job_status'] == 'restarted'
    # for index in df[restarted_mask].index:
    #     updated_job_status, updated_geometry_status = read_state(df.at[index, 'job_name'])
    #     if updated_job_status == 'failed':
    #         df.at[index, 'job_status'] = 'failed_twice'

    # Update job counter for completed jobs
    completed_jobs = df[df['job_status'] == 'completed']
    # for job_name in completed_jobs['job_name']:
    #     print(f'Job {job_name} completed.')
    # print(f'{num_jobs_running} jobs running')

    num_jobs_running = len(df[df['job_status'] == 'running'])
    return num_jobs_running



def act_on_state(ledger, num_jobs_running):
    '''
    clears directories of failed jobs, decrements counter.
    '''
    # Define patterns for matching job types
    #geom_pattern = re.compile(r'opt', re.IGNORECASE)
    #freq_pattern = re.compile(r'freq', re.IGNORECASE)
    #numfreq_pattern = re.compile(r'numfreq', re.IGNORECASE)
    # Handle failed jobs with specific conditions
    failed_jobs = ledger[ledger['job_status'] == 'failed']
    for index, row in failed_jobs.iterrows():
        job_name = row['job_name']
        #geom_status = row['geometry_status']
        clear_directory(job_name)
        #print(f'Job {job_name} failed.')
        #print(f'{num_jobs_running} jobs still running')
    return num_jobs_running
        
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



def queue_new_jobs(ledger,num_jobs_running,max_jobs_running):
    job_mask = ledger['job_status'] == 'not_started'
    jobs_to_run = ledger[job_mask]
    for index, row in ledger.iterrows():
        if (num_jobs_running >= max_jobs_running):
            return num_jobs_running
        if ledger.at[index,'job_status'] == 'not_started':
            dependency = ledger.at[index,'depends_on']
            if dependency:
                #TODO: ADDRESS THIS.
                #this would have it so that, if you misspelled a dependency, the next job would just up and start without it. which is not desired...
                filtered_ledger = ledger[ledger['job_name'] == dependency]
                if not filtered_ledger.empty: 
                    dependency_data = filtered_ledger.iloc[0]
                    dependency_completion = dependency_data['job_status']
                    
                    #TODO: make this more general
                    if dependency_completion == 'completed':
                        #coordinate moving helper function is activated here, before starting the job.
                        job_name = ledger.at[index,'job_name']
                        coords = jfe.get_orca_coordinates(f'../{dependency}/{dependency}.out')
                        jfe.replace_geometry(f'../{job_name}/{job_name}.inp',coords)
                    else:
                        continue
                else:
                    continue
            job_to_run = ledger.at[index,'job_name']
            
            ledger.at[index,'job_id'] = start_job(job_to_run)
            num_jobs_running += 1
            ledger.at[index,'job_status'] = 'running'
    
    return num_jobs_running
   


def check_finished(ledger):    
    finished_criteria = ['completed','failed','error']
    if ledger['job_status'].isin(finished_criteria).all():
        return True
    else:
        return False

if __name__ == '__main__':
    complete = False
    try:
        ledger = read_ledger('__ledger__.csv')
        print('reading old ledger on startup')
    except:
        #batchfile is for now a textfile with a list of (job_name\n)'s
        ledger = read_batchfile('batchfile.csv')
        print('reading batchfile on startup')
    
    #variables, besides the state in the ledger:
    #(should read config or the batch file for this.)
    #(for now, it's hardcoded)
    num_jobs_running = 0
    max_jobs_running = 3

    while not complete:
        
        #store in-memory ledger to file
        #update ledger
        num_jobs_running = update_state(ledger,num_jobs_running)
        print('writing ledger')
        print(ledger)
        ledger.to_csv('__ledger__.csv',sep='|',index=False)
        print('state updated')
        #need to create a job that WILL fail to test this
        print('acting on measured state (clearing failed job temp files for now)')
        num_jobs_running = act_on_state(ledger,num_jobs_running)
        print('queueing new jobs, if necessary')
        num_jobs_running = queue_new_jobs(ledger,num_jobs_running,max_jobs_running)
        
        num_jobs_running = update_state(ledger,num_jobs_running)
        print('state updated')
        print('ledger written')
        complete = check_finished(ledger)
        print(f'completion status: {complete}')
        print('sleeping')
        time.sleep(10)
        
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

