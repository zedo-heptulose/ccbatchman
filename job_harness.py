import file_peruser

import os
import re
import shutil
import subprocess
import json
import time

ORCARULES = 'rules/orca_rules.dat'

class JobHarness:
    def __init__(self):
        #filesystem
        self.directory = './' #directory where input files are located
        self.job_name = '' #job_name should be the root of the input file and .sh file

        #run data
        self.status = ''
        self.job_id = None

        #flags
        self.ruleset = ORCARULES #used to choose rules for parsing
        self.restart = True #when this flag is enabled, we will look for old temp files and use them
    
    def write_json(self):
        data_dict = {
            'directory' : self.directory,
            'job_name' : self.job_name,
            'status' : self.status,
            'job_id' : self.job_id,
            'restart' : self.restart,
            'ruleset' : self.ruleset,
        }
        with open(os.path.join(self.directory,'run_info.json'),'w') as json_file:
            json.dump(data_dict, json_file)

    
    def read_json(self,filename):
        with open(filename,'r') as json_data:
            data = json.load(json_data)
        self.directory = data['directory']
        self.job_name = data['job_name']
        self.status = data['status']
        self.job_id = data['job_id']
        self.restart = data['restart']
        self.ruleset = data['ruleset']

    
    def update_status(self):
        '''
        The heavy hitter state reading function
        accepts a job_name
        returns the job_state and geometry_state
        '''
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
                print(f'Squeue output: {output}')
                if re.search('error:',output):
                    in_progress = False
                else:
                    captureline = output.splitlines()[1] 
                    slurm_status = re.search(
                                        r'(?:\S+\s+){4}(\S+)',
                                        captureline).group(1)  
                break
            except:
                print(f"Bad capture of squeue response: Attempt {attempt + 1}")
    
        if in_progress:
            print(f'status:{slurm_status}')   
            if slurm_status == 'PD':
                self.status = 'pending'
                return
    
            elif slurm_status == 'R':
                self.status == 'running'
                return

            else:
                raise ValueError('Something broke here')
        
        else:
            temp_status = file_peruser.extract_data(
                          f"{os.path.join(self.directory,self.job_name)}.out",
                          self.ruleset
                          )
            self.status = 'succeeded' if temp_status['completion_success'] else 'failed'
            return
        
            
    def submit_job(self):
        processdata = subprocess.run(f"sbatch {self.job_name}.sh",
                                     shell=True,
                                     cwd=self.directory,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        output = processdata.stdout.decode('utf-8')
        try:    
            print(f"slurm submission output: {output}")
            if re.search('error:',output):
                print(f"Directory: {self.directory}")
                raise ValueError(f"Bad submission script! output: {output}")
            self.job_id = int(re.search(r'\d+',output).group(0))
        except:
            raise ValueError(f"Bad submission script! output: {output}")    


    def parse_output(self):
        data = file_peruser.extract_data(
                    f"{os.path.join(self.directory,self.job_name)}.out",
                    self.ruleset
                    )
        with open(f"{os.path.join(self.directory, self.job_name)}.json",'w') as json_file:
            json.dump(data, json_file)

    
    def manage_job(self):
        data_path = os.path.join(self.directory,'run_info.json')
        if os.path.exists(data_path) and self.restart:
            self.read_json(data_path)
        if not (self.status == 'running' or self.status == 'pending'):
            self.submit_job()
            self.status = 'pending'
        print(f"Id: {self.job_id}")
        print(f"Status : {self.status}")
        
        while self.status == 'running' or self.status == 'pending':
            self.update_status()
            self.write_json()
            time.sleep(5)
            print(f"Status : {self.status}")

        self.parse_output()
        
        if self.status == 'failed':
            return 1
        elif self.status == 'succeeded':
            return 0
        