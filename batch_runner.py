import job_harness
import pandas as pd
import json
import os
import time
import re
#jobs should be a list or dict of job_harness objects
import editor
import numpy as np


class BatchRunner:
    #tested
    def __init__(self,**kwargs):
        self.batch_name = "test"
        self.scratch_directory = "./"
        self.run_root_directory = "./" #read from batchfile
        self.jobs = [] #list of JobHarness objects
        self.ledger = pd.DataFrame() #ledger containing instructions and status
        self.batchfile = kwargs.get('batchfile',None)
        self.ledger_filename = kwargs.get('ledger_filename','__ledger__.csv') #
        self.restart = kwargs.get('restart',True) #This option is for using an old ledger file
        self.max_jobs_running = kwargs.get('maxjobs',1)
        self.debug = False

    #tested
    def to_dict(self): #DOES NOT INCLUDE LEDGER, BUT ONLY LEDGER FILENAME
        return {
            'batch_name' : self.batch_name,
            'scratch_directory' : self.scratch_directory,
            'run_directory' : self.run_directory,
            'jobs' : [job.to_dict() for job in self.jobs],
            'batchfile' : self.batchfile,
            'ledger_filename' : self.ledger_filename,
            'restart' : self.restart,
            'max_jobs_running' : self.max_jobs_running,
        }
    #tested
    def from_dict(self,data):
        self.batch_name = data['batch_name']
        self.scratch_directory = data['scratch_directory']
        self.jobs = [job_harness.JobHarness().from_dict(job_dict) for job_dict in data['jobs']]
        self.batchfile = data['batchfile']
        self.ledger_filename = data['ledger_filename']
        self.restart = data['restart']
        self.max_jobs_running = data['max_jobs_running']
        return self
        
    #tested
    def write_json(self):
        full_path_basename = os.path.join(self.scratch_directory,self.batch_name)
        with open(f"{full_path_basename}.json",'w') as jsonfile:
            json.dump(self.to_dict(),jsonfile)
    #tested
    def read_json(self):
        full_path_basename = os.path.join(self.scratch_directory,self.batch_name)
        if self.debug: print(full_path_basename)
        with open(f"{full_path_basename}.json",'r') as jsonfile:
            self.from_dict(json.load(jsonfile))

    def dependencies_satisfied(self,row):
        completed_jobs = self.completed_jobs()
        if self.debug: print('completed jobs:')
        if self.debug: print(f"{completed_jobs}")
        if pd.isna(row['coords_from']):
            if self.debug: print('dependency is nan, satisfied')
            return True
        dependencies = row['coords_from']
        if self.debug: print(f"dependencies: {dependencies}")
        if (dependencies in list(completed_jobs['job_basename'])):
            if self.debug: print(f"returning fact")
            return True
        if self.debug: print(f"returning cap")
        return False


    def completed_jobs(self):
        return self.ledger[self.ledger['job_status']=='succeeded']

    def dependency_mask(self):
        return self.ledger.apply(
                    lambda row: self.dependencies_satisfied(
                        row
                        ),axis=1
                )
    
    def run_jobs_update_ledger(self,**kwargs):
        debug = kwargs.get('debug',False)
        for index in range(len(self.jobs) - 1, -1, -1):
            job = self.jobs[index]
            if self.debug: print(f"running OneIter on job with\nbasename{job.job_name}\nid: {job.job_id}")
            job.OneIter()
            if self.debug: print(f"job status: {job.status}")
            self.ledger.loc[self.ledger['job_id'] == job.job_id, 'job_status'] = job.status
            if job.status == 'failed' or job.status == 'succeeded':
                self.jobs.pop(index)

    def replace_coords(self,job,xyz_directory,xyz_filename):
        input_filename = f"{job.basename}{job.extension}"
        input_directory = f"{job.directory}"
        xyz_directory = os.path.join(job.directory,xyz_directory)
        editor.replace_xyz_file(input_filename,input_directory,xyz_filename,xyz_directory)

    def transfer_coords(self,ledger_row,job):
        coords_from = ledger_row['coords_from']
        xyz_filename = ledger_row['xyz_filename']
        if (coords_from and not pd.isna(coords_from)) and (xyz_filename and not pd.isna(xyz_filename)):
            if self.debug: print("calling replace_coords(0,2,3) with args:")
            if self.debug: print(f"""
                    0: {job} with {job.basename} and {job.directory}
                    1: {coords_from}
                    2: {xyz_filename}
                    """)
            replace_coords(job,coords_from,xyz_filename)

    def queue_new_jobs(self,**kwargs):
        running_mask = (self.ledger['job_status'] == 'running') |\
                       (self.ledger['job_status'] == 'pending') 
        num_running_jobs = len(self.ledger[running_mask])
        
        if num_running_jobs < self.max_jobs_running:
            if self.debug: print(f"jobs with satisfied dependencies:\n{self.ledger.loc[self.dependency_mask()]}")
            not_started_mask = (self.dependency_mask()) & (self.ledger['job_status'] == 'not_started')
            not_started_jobs = self.ledger.loc[not_started_mask]
            if self.debug: print(f"available jobs:\n{not_started_jobs}")
            for i in range(min(self.max_jobs_running-num_running_jobs,
                               len(not_started_jobs))):
                if not_started_jobs.iloc[i]['program'].lower() == 'gaussian':
                    job = job_harness.GaussianHarness()
                    if self.debug: print('Using Gaussian parsing rules')
                elif not_started_jobs.iloc[i]['program'].lower() == 'orca':
                    job = job_harness.ORCAHarness()
                    if self.debug: print('Using ORCA parsing rules')
                elif not_started_jobs.iloc[i]['program'].lower() == 'crest':
                    job = job_harness.CRESTHarness()
                    if self.debug: print('Using CREST parsing rules')
                else:
                    if self.debug: print(f"Warning: No program read. Parameter set as {not_started_jobs.iloc[i]['program']}")
                    if self.debug: print(f"Assuming ORCA Input")
                    job = job_harness.ORCAHarness()
                job.job_name = not_started_jobs.iloc[i]['job_basename']
                #jobs in directory with their basename, and their files have this basename
                job.directory = not_started_jobs.iloc[i]['job_directory']
                if self.debug: print(f"directory set to {job.directory}")
                
                self.transfer_coords(not_started_jobs.iloc[i],job)
                
                job.update_status()
                job.write_json()
                job.check_success_static()

                if job.status == 'succeeded':
                    job.job_id = max([int(re.search(r'\d+',fn).group(0)) for fn in os.listdir(job.job_directory) if re.search(r'slurm-\d+.out',fn)])
                
                else:
                    job.submit_job()

                ledger_index = not_started_jobs.index[i]
                if self.debug: print(f"job id: {job.job_id}")
                self.ledger.loc[ledger_index,'job_id'] = job.job_id
                if self.debug: print(f"job status: {job.status}")
                self.ledger.loc[ledger_index,'job_status'] = job.status #doesn't work; for now update ledger will be able to tell
                if self.debug: print(f"after: {self.ledger.loc[ledger_index]}")
                
                self.jobs.append(job)
            

    def check_finished(self,**kwargs):
        debug = kwargs.get('debug',False)
        not_finished_mask = (self.ledger['job_status'] == 'not_started') |\
                            (self.ledger['job_status'] == 'running') |\
                            (self.ledger['job_status'] == 'pending')
        if len(self.ledger.loc[not_finished_mask & self.dependency_mask()]) == 0:
            return True
        return False

    def write_ledger(self,**kwargs):
        ledger_path = os.path.join(self.scratch_directory,self.ledger_filename)
        self.ledger.to_csv(ledger_path,sep='|',index=False)

    def restart_from_ledger(self,**kwargs):
        ledger_path = os.path.join(self.scratch_directory,self.ledger_filename)
        if not os.path.exists(ledger_path):
            raise ValueError('ledger path does not exist')
        self.ledger = pd.read_csv(ledger_path,sep='|')
        if self.debug: print(f"Ledger loaded:\n{self.ledger}")
        #this also needs to create job objects for each existing job
        current_job_mask = (self.ledger['job_id'] != -1)
        
        for index, row in self.ledger[current_job_mask].iterrows():
            if row['program'].lower() == 'gaussian':
                new_job = job_harness.GaussianHarness()
                if self.debug: print('Gaussian!')
            elif row['program'].lower() == 'orca':
                if self.debug: print('ORCA!')
                new_job = job_harness.ORCAHarness()
            elif row['program'].lower() == 'crest':
                if self.debug: print('CREST!')
                new_job = job_harness.CRESTHarness()
            else:
                if self.debug: print('JOB PROGRAM NOT SPECIFIED, ASSUMING ORCA')
                new_job = job_harness.ORCAHarness()
            new_job.job_id = row['job_id']
            new_job.status = row['job_status']
            new_job.directory = os.path.join(row['job_directory'],row['job_basename'])
            new_job.job_name = row['job_basename']
            new_job.restart = True 
            self.jobs.append(new_job)

    def read_batchfile(self):
        '''
        this file should contain a list of filenames to run,
        with some config commands allowed as well.
        creates a ledger from the batchfile
        '''
        batch_path = os.path.join(self.scratch_directory,self.batchfile)
        if not os.path.exists(batch_path):
            raise ValueError(f"Invalid Batchfile Specified at path\n{batch_path}")
        with open(batch_path,'r') as batchfile:
            lines = batchfile.readlines()
        if not os.path.exists(batch_path):
            raise ValueError(f"Invalid Batchfile Specified at path\n{batch_path}")
        with open(batch_path,'r') as batchfile:
            lines = batchfile.readlines()
        #batchfile starts with a series of variable assignment statements used as config
        try:
            self.run_root_directory = lines[0].split('=')[1].strip()
        except:
            raise ValueError('Invalid Batchfile Format')
        #then job_basename | job_directory | program | dependencies | 
        # jobs must have all have unique basenames!
        batch = pd.read_csv(batch_path,delimiter='|',skiprows=1)
        if self.debug: print(f"batchfile contents:\n{batch}")
        self.ledger = pd.DataFrame() 
        
        self.ledger['job_id']=[-1 for i in range (len(batch))]
        self.ledger['job_basename'] = batch['job_basename']
        self.ledger['job_directory'] = [os.path.join(self.run_root_directory,batch_dir if type(batch_dir) is str else "") for batch_dir in batch['job_directory']]
        #ledger['depends_on'] = batch.iloc[:,1].fillna('')
        self.ledger['job_status'] = ['not_started' for i in range (len(batch))]
        self.ledger['program'] = batch['program'] #ORCA,CREST,GAUSSIAN,ETC
       
       
        #TODO: more general piping here
        self.ledger[['coords_from','xyz_filename']] = batch['pipe'].apply(self.parse_pipe).apply(pd.Series)
        
        return self.ledger


    def parse_pipe(self,pipe_command):
        if self.debug: print(pipe_command)
        if pipe_command is np.nan:
            return np.nan
        match = re.match('(?:\s*)(\S+)(?:\s*\{\s*)(\S+)(?:\s*,\s*)(\S*)(?:\s*\})',pipe_command)
        args = list(match.groups())
        if self.debug: print(args)
        command = args[0]
        dirname = args[1]
        basename = os.path.basename(dirname)
        xyz_filename = args[2]
        if xyz_filename == '': xyz_filename = basename+'.xyz'
        
        if command.lower() == 'coords':
            return (dirname,xyz_filename)
        else:
            raise NotImplementedError(f"No pipe keyword for {command}")


    def MainLoop(self,**kwargs):
        debug = kwargs.get('debug',False)
        complete = False
        try:
            self.restart_from_ledger()
            if self.debug: print('reading old ledger on startup')
        except:
            self.read_batchfile()
            if self.debug: print('reading batchfile on startup')
        if self.debug: print('entering for loop')
        while not self.check_finished():
            if self.debug: print('\n\nupdating ledger and running job loops\n\n')
            self.run_jobs_update_ledger()
            if self.debug: print('\n\nqueueing new jobs\n\n')
            self.queue_new_jobs()
            if self.debug: print('\n\nwriting ledger\n\n')
            self.write_ledger()
            if self.debug: print('\n\nsleeping\n\n')
            time.sleep(5)
        print("\n\nEXITING\n\n")
