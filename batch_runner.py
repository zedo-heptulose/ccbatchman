import job_harness
import pandas as pd
import json
import os
import time
#jobs should be a list or dict of job_harness objects

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
        print(full_path_basename)
        with open(f"{full_path_basename}.json",'r') as jsonfile:
            self.from_dict(json.load(jsonfile))


    def run_jobs_update_ledger(self,**kwargs):
        debug = kwargs.get('debug',False)
        for index in range(len(self.jobs) - 1, -1, -1):
            job = self.jobs[index]
            print(f"running OneIter on job with\nbasename: {job.job_name}\nid: {job.job_id}")
            job.OneIter()
            print(f"job status: {job.status}")
            self.ledger.loc[self.ledger['job_id'] == job.job_id, 'job_status'] = job.status
            if job.status == 'failed' or job.status == 'succeeded':
                self.jobs.pop(index)
    
    def queue_new_jobs(self,**kwargs):
        debug = kwargs.get('debug',False)
        running_mask = (self.ledger['job_status'] == 'running') |\
                       (self.ledger['job_status'] == 'pending') 
        num_running_jobs = len(self.ledger[running_mask])
        
        if num_running_jobs < self.max_jobs_running:
            not_started_jobs = self.ledger.loc[self.ledger['job_status'] == 'not_started']
            for i in range(min(self.max_jobs_running-num_running_jobs,
                               len(not_started_jobs))):
                job = job_harness.JobHarness()
                job.job_name = not_started_jobs.iloc[i]['job_basename']
                #jobs in directory with their basename, and their files have this basename
                job.directory = os.path.join(not_started_jobs.iloc[i]['job_directory'],job.job_name) #TODO: make this toggleable
                #job.ruleset = SOME MAP BETWEEN PROGRAMS AND RULE SETS
                job.submit_job()
                ledger_index = not_started_jobs.index[i]
                #this seems to be failing
                if debug: print(f"Ledger index: {ledger_index}")
                if debug: print(f"before: {self.ledger.loc[ledger_index]}")
                if debug: print(f"job id: {job.job_id}")
                self.ledger.loc[ledger_index,'job_id'] = job.job_id
                if debug: print(f"job status: {job.job_status}")
                #self.ledger.loc[ledger_index,'job_status'] = job.status #doesn't work; for now update ledger will be able to tell
                if debug: print(f"after: {self.ledger.loc[ledger_index]}")
                
                self.jobs.append(job)
            

    def check_finished(self,**kwargs):
        debug = kwargs.get('debug',False)
        not_finished_mask = (self.ledger['job_status'] == 'not_started') |\
                            (self.ledger['job_status'] == 'running') |\
                            (self.ledger['job_status'] == 'pending')
        if len(self.ledger.loc[not_finished_mask]) == 0:
            return True
        return False

    def write_ledger(self,**kwargs):
        ledger_path = os.path.join(self.scratch_directory,self.ledger_filename)
        self.ledger.to_csv(ledger_path,sep='|',index=False)

    def load_ledger(self,**kwargs):
        full_path_basename = os.path.join(self.scratch_directory,self.ledger_filename)
        if not os.path.exists(full_path_basename):
            raise ValueError('ledger path does not exist')
        self.ledger = pd.read_csv(full_path_basename,sep='|',index=False)
        
    
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
        #batchfile starts with a series of variable assignment statements used as config
        try:
            self.run_root_directory = lines[0].split('=')[1].strip()
        except:
            raise ValueError('Invalid Batchfile Format')
        #then job_basename | job_directory | program | dependencies | 
        # jobs must have all have unique basenames!
        batch = pd.read_csv(batch_path,delimiter='|',skiprows=1)
        print(f"batchfile contents:\n{batch}")
        self.ledger = pd.DataFrame() 
        
        self.ledger['job_id']=[-1 for i in range (len(batch))]
        self.ledger['job_basename'] = batch['job_basename']
        self.ledger['job_directory'] = [os.path.join(root_dir, batch_dir if type(batch_dir) is str else "") for batch_dir in batch['job_directory']]
        #ledger['depends_on'] = batch.iloc[:,1].fillna('')
        self.ledger['job_status'] = ['not_started' for i in range (len(batch))]
        self.ledger['program'] = batch['program'] #ORCA,CREST,GAUSSIAN,ETC
        return self.ledger
        
    
    def MainLoop(self,**kwargs):
        debug = kwargs.get('debug',False)
        complete = False
        try:
            self.load_ledger()
            print('reading old ledger on startup')
        except:
            self.read_batchfile()
            print('reading batchfile on startup')
        while not self.check_finished():
            self.run_jobs_update_ledger()
            self.write_ledger()
            self.queue_new_jobs()
            time.sleep(10)
