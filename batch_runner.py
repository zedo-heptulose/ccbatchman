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
        self.strict = False
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
    
    #TODO: generalize to all dependencies
    def dependencies_satisfied(self,row):
        completed_jobs = self.completed_jobs()
        if pd.isna(row['coords_from']):
            if self.debug: print('dependency is nan, satisfied')
            return True
        dependencies = row['coords_from']
        #TODO: fix this, if we ever make dependencies a list
        if self.debug and type(dependencies) is str: print(
                f"dependencies: {os.path.abspath(os.path.join(row['job_directory'],dependencies))}"
                )
        dependency_abs_path = os.path.abspath(os.path.join(row['job_directory'],row['coords_from']))
        if len(completed_jobs) != 0:
            completed_abs_paths = [os.path.abspath(comp_row['job_directory']) for i, comp_row in completed_jobs.iterrows()]
            if (dependency_abs_path in completed_abs_paths):
                if self.debug: print(f"dependencies satisfied")
                return True
        if self.debug: print(f"dependencies not satisfied")
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
            if self.debug: print(f"job directory: {job.directory}")

            
            job.OneIter()
           
            if self.debug: print(f"job status: {job.status}")
            self.ledger.loc[self.ledger['job_id'] == job.job_id, 'job_status'] = job.status
            if job.status == 'failed' or job.status == 'succeeded':
                self.jobs.pop(index)


    
    def transfer_coords(self,ledger_row,job):
        xyz_directory = ledger_row['coords_from']
        xyz_filename = ledger_row['xyz_filename']
        
        if not xyz_directory or pd.isna(xyz_directory)\
        or not xyz_filename or pd.isna(xyz_filename):
            return
        #todo: jobs should have basename and input_filename properties
        input_directory = job.directory
        input_filename = job.job_name + job.input_extension
        input_path = os.path.join(input_directory,input_filename)
        
        xyz_path = os.path.join(input_directory,xyz_directory,xyz_filename)
        xyz_path = os.path.normpath(xyz_path)


        input_program = job.program
        
        if self.debug: print("calling replace_xyz_file({0},{1},{2}) with args:")
        if self.debug: print(f"""
                    0: {input_path}
                    1: {xyz_path}
                    2: {input_program}
                    """)
        xyz_directory = os.path.join(job.directory,xyz_directory)
        editor.replace_xyz_file(
                input_path,xyz_path,input_program
        )

    
    def create_job_harness(self,program,**kwargs):
        if program.lower() == 'gaussian':
            if self.debug: print('Using Gaussian parsing rules')
            return job_harness.GaussianHarness()
        elif program.lower() == 'orca':
            if self.debug: print('Using ORCA parsing rules')
            return job_harness.ORCAHarness()
        elif program.lower() == 'crest':
            if self.debug: print('Using CREST parsing rules')
            return job_harness.CRESTHarness()
        elif program.lower() == 'xtb':
            if self.debug: print('Using xTB parsing rules')
            return job_harness.xTBHarness()
        elif program.lower() == 'pyaroma':
            if self.debug: print('Using pyAroma parsing rules')
            return job_harness.pyAromaHarness()
            
        else:
            raise ValueError('Invalid Program Specified')
        
    
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
                job = self.create_job_harness(not_started_jobs.iloc[i]['program'])
                
                job.job_name = not_started_jobs.iloc[i]['job_basename']
                #jobs in directory with their basename, and their files have this basename
                job.directory = not_started_jobs.iloc[i]['job_directory']
                if self.debug: print(f"directory set to {job.directory}")
                
                self.transfer_coords(not_started_jobs.iloc[i],job)
               
                try:
                    job.check_success_static() #so this didn't work?
                    job.write_json()
                except:
                    print("job.check_success_static() failed, check that output exists")

                if job.status == 'succeeded':
                    job.job_id = max([int(re.search(r'\d+',fn).group(0)) for fn in os.listdir(job.directory) if re.search(r'slurm-\d+.out',fn)])
                
                elif job.status == 'failed':
                    print("WARNING: JOB ALREADY FAILED")
                    print(f"job name: {job.job_name}")
                    print(f"job directory: {job.directory}")

                elif job.status =='not_started':
                    job.submit_job()
                else:
                    raise ValueError(f"check_success_static() returned unexpected value: {job.status}")

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
        
        return self

    
    def read_old_ledger(self,**kwargs):
        ledger_path = os.path.join(self.scratch_directory,self.ledger_filename)
        if not os.path.exists(ledger_path):
            raise ValueError('ledger path does not exist')
        old_ledger = pd.read_csv(ledger_path,sep='|')
        if self.debug: print(f"Old ledger loaded with filename:\n{self.ledger}")
            
        self.ledger = pd.concat([self.ledger, old_ledger])\
        .drop_duplicates(subset=['job_directory', 'job_basename'], keep='last')
        #I think this is the one! let's try it in a sec
        return self
    
    def restart_job_harnesses(self,**kwargs):
        #this is a bad way to do this and causes issues, presently.
        #would rather just update job status on a case by case basis...
        
        #TODO: check if this caused any issues
        current_job_mask = (self.ledger['job_id'] != -1) & (self.ledger['job_status'] != 'succeeded') & (self.ledger['job_status'] != 'failed')
        
        for index, row in self.ledger[current_job_mask].iterrows():
            new_job = self.create_job_harness(row['program'])
            
            new_job.job_id = row['job_id']
            new_job.status = row['job_status'] #would be running for the offending jobs
            new_job.directory = row['job_directory'] 
            new_job.job_name = row['job_basename'] #sure
            new_job.restart = True  #why does this fail
            self.jobs.append(new_job) 
            if self.debug: print(f"JOB ADDED TO QUEUE. {new_job.job_name}")
 
    def initialize_run(self):
        '''
        this reads the batchfile into a ledger in memory.
        If restart is enabled, we overwrite any conflicts using the old ledger.
        That is primarily to allow us to add jobs as we please, without messing everything up.
        '''
        self.read_batchfile()
        if self.debug: print("LEDGER AFTER READING BATCHFILE")
        if self.debug: self.ledger.to_csv('lar.csv')
        
        if self.restart:
            try:
                if self.debug: print("READING OLD LEDGER AND MERGING")
                self.read_old_ledger()
                if self.debug: print("LEDGER AFTER MERGE:")
                if self.debug: self.ledger.to_csv('lam.csv')
                if self.debug: print("RESTARTING OLD JOB HARNESSES")
                self.restart_job_harnesses()
            except:
                print("NO LEDGER FOUND TO RESTART FROM")
        return self

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

    def try_parse_all_jobs(self,**kwargs):
        print(f"trying to parse all jobs in ledger!!")
        for index, row in self.ledger.iterrows():
            dirname = row['job_directory']
            basename = row['job_basename']
            jh = self.create_job_harness(row['program'])
            jh.directory = dirname
            jh.job_name = basename
            try:
                print(f"parsing data in dir : {dirname} basename: {basename}")
                jh.parse_output()
                jh.final_parse()
            except:
                print(f"parse_data failed for job with base path:")
                print(os.path.join(dirname,basename))
    
    def MainLoop(self,**kwargs):
        print('batch_runner\nInitializing run\n')
        self.initialize_run()
        while not self.check_finished():
            if self.debug: print('updating ledger and running job loops')
            self.run_jobs_update_ledger()
            if self.debug: print('queueing new jobs')
            self.queue_new_jobs()
            if self.debug: print('writing ledger')
            self.write_ledger()
            if self.debug: print('sleeping')
            time.sleep(1)
        print("\n\nEXITING\n\n")

