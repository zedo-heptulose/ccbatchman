import file_parser

import os
import re
import shutil
import subprocess
import json
import time

ORCARULES = 'rules/orca_rules.dat'
GAUSSRULES = 'rules/gaussian_rules.dat'
CRESTRULES = 'rules/crest_rules.dat'

class JobHarness:
    def __init__(self):
        #filesystem
        self.directory = './' #directory where input files are located
        self.job_name = '' #job_name should be the root of the input file and .sh file
        self.output_extension = '.out'
        #run data
        self.status = 'not_started'
        self.job_id = None

        #flags
        self.ruleset = ORCARULES #used to choose rules for parsing
        self.restart = True #when this flag is enabled, we will look for old temp files and use them

    def to_dict(self):
        return {
            'directory' : self.directory,
            'job_name' : self.job_name,
            'status' : self.status,
            'job_id' : self.job_id,
            'restart' : self.restart,
            'ruleset' : self.ruleset,
        }
    
    def write_json(self):
        data_dict = self.to_dict()
        with open(os.path.join(self.directory,'run_info.json'),'w') as json_file:
            json.dump(data_dict, json_file)

    def from_dict(self,data):
        self.directory = data['directory']
        self.job_name = data['job_name']
        self.status = data['status']
        self.job_id = data['job_id']
        self.restart = data['restart']
        self.ruleset = data['ruleset']
        return self
    
    def read_json(self,filename):
        with open(filename,'r') as json_data:
            data = json.load(json_data)
        self.from_dict(data)

    
    def update_status(self,**kwargs):
        '''
        The heavy hitter state reading function
        accepts a job_name
        returns the job_state and geometry_state
        '''
        debug = kwargs.get('debug',False)
        in_progress = True
        slurm_status = "N/A"
    
        for attempt in range(5):    #needs
            try:
                processdata = subprocess.run(
                                f'squeue --job {self.job_id}',
                                shell=True,
                                cwd=self.directory,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT
                                )
                output = processdata.stdout.decode('utf-8')
                if debug: print(f'Squeue output: {output}')
                if re.search('error:',output):
                    if debug: print('gets to 1st if')
                    in_progress = False
                elif re.match(
r'^\s+JOBID\s+PARTITION\s+NAME\s+USER\s+ST\s+TIME\s+NODES\s+NODELIST\(REASON\)\s+$',
                    output):
                    if debug: print('gets to 2nd if')
                    in_progress = False
                else:
                    if debug: print('gets to 3rd if')
                    captureline = output.splitlines()[1] 
                    slurm_status = re.search(
                                        r'(?:\S+\s+){4}(\S+)',
                                        captureline).group(1)  
                break #if we get to the end, don't bother trying again
            except:
                if debug: print(f"Bad capture of squeue response: Attempt {attempt + 1}")
    
        if in_progress:
            print(f'slurm status:{slurm_status}')   
            if slurm_status == 'PD':
                self.status = 'pending'
                print("returning pending")
                return
    
            elif slurm_status == 'R':
                self.status == 'running'
                print("returning with running")
                return

            else:
                in_progress = False
        
        if not in_progress: #this isn't an if-else because in_progress can be changed in the last conditional
            #TODO: FIX THIS 
            temp_status = file_parser.extract_data(
                          f"{os.path.join(self.directory,self.job_name)}{self.output_extension}",
                          self.ruleset
                          )
            self.status = self.check_success(temp_status) 
            return

    def check_success(self, file_parser_output):
        return 'succeeded' if file_parser_output['completion_success'] else 'failed'

        
    def submit_job(self,**kwargs):
        debug = kwargs.get('debug',False)
        if debug: print(f"In directory {self.directory}")
        if debug: print(f"Executing command: sbatch {self.job_name}.sh")
        processdata = subprocess.run(f"sbatch {self.job_name}.sh",
                                     shell=True,
                                     cwd=self.directory,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        output = processdata.stdout.decode('utf-8')
        try:    
            if debug: print(f"slurm submission output: {output}")
            if re.search('error:',output):
                if debug: print(f"Directory: {self.directory}")
                raise ValueError(f"Bad submission script! output: {output}")
            self.job_id = int(re.search(r'\d+',output).group(0))
            self.status = 'pending'
            self.write_json()
        except:
            raise ValueError(f"""Bad submission script!
                    in directory: {self.directory}
                    output: {output}""")    

    def parse_output(self,**kwargs):
        debug = kwargs.get('debug',False)
        data = file_parser.extract_data(
                    f"{os.path.join(self.directory,self.job_name)}{self.output_extension}",
                    self.ruleset
                    )
        with open(f"{os.path.join(self.directory, self.job_name)}.json",'w') as json_file:
            json.dump(data, json_file)

    def OneIter(self,**kwargs):
        if self.status == 'failed' or self.status == 'completed':
            return self.status
        debug = kwargs.get('debug',False)
        data_path = os.path.join(self.directory,'run_info.json')
        if os.path.exists(data_path): #this MUST happen if using this
            self.read_json(data_path)
        else:
            raise ValueError('OneIter called without run_info.json existing')
        self.update_status()
        self.write_json()
        if not (self.status == 'not_started' or self.status == 'pending'):
            self.parse_output()
            
    
    def MainLoop(self,**kwargs):
        debug = kwargs.get('debug',False)
        data_path = os.path.join(self.directory,'run_info.json')
        if os.path.exists(data_path) and self.restart:
            self.read_json(data_path)
        if(self.status == 'not_started'):
            self.submit_job()
        if debug: print(f"Id: {self.job_id}")
        if debug: print(f"Status : {self.status}")
        
        while self.status == 'running' or self.status == 'pending':
            self.update_status()
            self.write_json()
            time.sleep(5)
            if debug: print(f"Status : {self.status}")

        self.parse_output()
        
        if self.status == 'failed':
            return 1
        elif self.status == 'succeeded':
            return 0

class ORCAHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = ORCARULES
        self.output_extension = '.out'
        self.input_extension = '.inp'

class GaussianHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = GAUSSRULES
        self.output_extension = '.log'
        self.input_extension = '.gjf'

    def check_success(self, file_parser_output):
        if file_parser_output['is_opt_freq']:
            return 'succeeded' if file_parser_output['successful_completion_optfreq'] else 'failed'
        else:
            return 'succeeded' if file_parser_output['successful_completion'] else 'failed'

class CRESTHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = CRESTRULES
        self.output_extension = '.out'
        self.input_extension = None
