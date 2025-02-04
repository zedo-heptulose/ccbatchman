import file_parser

import postprocessing

import os
import re
import shutil
import subprocess
import json
import time

import glob

this_script_path = os.path.abspath(__file__)
rules_dir = os.path.join(this_script_path,'../../config/file_parser_config')
rules_dir = os.path.normpath(rules_dir)
ORCARULES  = os.path.join(rules_dir,'orca_rules.dat')
GAUSSRULES = os.path.join(rules_dir,'gaussian_rules.dat')
XTBRULES   = os.path.join(rules_dir,'xtb_rules.dat')
CRESTRULES = os.path.join(rules_dir,'crest_rules.dat')
PYAROMARULES=os.path.join(rules_dir,'pyaroma_rules.dat')


class JobHarness:
    def __init__(self):
        self.strict = False
        self.parse_fail_counter = 0
        self.parse_fail_threshold = 10

        self.debug = False
        self.silent = False
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
        self.mode = 'slurm' #slurm or direct
        self.tmp_extension= '.tmp'
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
            json.dump(data_dict, json_file,indent="")

    def from_dict(self,data): #TODO: FIX RULESET HACK!
        old_data = self.to_dict()
        old_data.update(data)
        data = old_data.copy()
        self.directory = data['directory']
        self.job_name = data['job_name']
        self.status = data['status']
        self.job_id = data['job_id']
        self.restart = data['restart']
        if not self.ruleset:
            self.ruleset = data['ruleset']
        return self
    
    def read_json(self,filename):
        with open(filename,'r') as json_data:
            data = json.load(json_data)
        self.from_dict(data)

    #this will make things more robust. On startup, we check for this...
    def get_id(self):
        files = os.listdir(self.directory)
        pattern = '(?:slurm-)(\d+)(?:\.out)'
        id_list = [file for file in files if re.match(pattern,file)]
        id_list = [int(re.match(pattern,file).group(1)) for file in id_list]
        max_id = -1
        if len(id_list) != 0:
            max_id = max(id_list)
        if max_id != -1:
            self.job_id = max_id


    #all that's required is a simple update_status here...
    def update_status(self,**kwargs):
        '''
        The heavy hitter state reading function
        accepts a job_name
        returns the job_state and geometry_state
        '''
        debug = kwargs.get('debug',False)
        in_progress = True
        slurm_status = "N/A"
        slurm_read = False
        #this way we avoid complication; just do this when updating status.
        #allows us to check status given only a directory and basename
        if not self.job_id or self.job_id == -1:
            self.get_id()
            

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
                slurm_read = True
                break #if we get to the end, don't bother trying again
            except:
                if debug: print(f"Bad capture of squeue response: Attempt {attempt + 1}")
        
        if not slurm_read:
            raise RuntimeError("Could not capture job status through squeue")

        if in_progress:
            if self.debug: print(f'slurm status:{slurm_status}')   
            if slurm_status == 'PD':
                self.status = 'pending'
                if self.debug: print("returning pending")
                return
    
            elif slurm_status == 'R':
                if self.debug: self.status = 'running'
                if self.debug: print("returning with running")
                return

            else:
                in_progress = False
            
        if not in_progress: #this isn't an if-else because in_progress can be changed in the last conditional
            #TODO: FIX THIS
            if self.debug: print(f'updating status with ruleset found at: {self.ruleset}')
            if self.debug: print(f"slurm output before static success check: {output}")
            output_filename = f"{os.path.join(self.directory,self.job_name)}{self.output_extension}"
            if not os.path.exists(output_filename):
                return 'not_started' #DANGEROUS, EXPECT NEGATIVE CONSEQUENCES
            self.check_success_static()
            return 
            
    def check_success_static(self):
        '''
        used for jobs which are not running; they either succeeded or failed
        this is a separate function so that it can be called on its own, even though the logic is simple
        '''
        if self.debug : print(f"using ruleset at path: {self.ruleset}")
        if self.debug : print(f"absolute ruleset path: {os.path.abspath(self.ruleset)}")
        output_filename = f"{os.path.join(self.directory,self.job_name)}{self.output_extension}"
        if not os.path.exists(output_filename):
            print(f"FILE DOES NOT EXIST: {output_filename}")
            self.status = 'not_started' #CHECK ERROR
            return
        temp_status = file_parser.extract_data(
                          output_filename,
                          self.ruleset #this fails?
                          )
        self.interpret_fp_out(temp_status)
    
    def interpret_fp_out(self, file_parser_output):
        #this function exists to be overwritten
        self.status = ('succeeded' if file_parser_output['success'] else 'failed')
            
        
    def submit_job(self,**kwargs):
        debug = kwargs.get('debug',False)
        if debug: print(f"In directory {self.directory}")
        if debug: print(f"Executing command: sbatch {self.job_name}.sh")
        if self.mode == 'slurm':
            processdata = subprocess.run(f"sbatch {self.job_name}.sh",
                                         shell=True,
                                         cwd=self.directory,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
            output = processdata.stdout.decode('utf-8')
            try:    
                if debug: print(f"slurm submission output: {output}")
                #TODO: put this back the way it was. this will be silenced for now to brute force
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
                #TODO: FIX THIS
        elif self.mode == 'direct':
            raise NotImplementedError('direct run mode not working yet')
            processdata = subprocess.run(f"chmod +x {self.job_name}.sh",
                                        shell=True,
                                        cwd=self.directory)
            processdata = subprocess.run(f"./{self.job_name}.sh",
                                        shell=True,
                                        cwd=self.directory)

    def parse_output(self,**kwargs):
        debug = kwargs.get('debug',False)
        path = os.path.join(self.directory,self.job_name) + self.output_extension
        data = None
        for trial in range(0,3):
            #TODO: fix failure here
            if os.path.exists(path):
                data = file_parser.extract_data(
                    path,
                    self.ruleset
                )
                break

            else:
                time.sleep(1)
                print("in parse_output, file not found. Trial number: {trial}")
        
        if not data:
            print(f"Attempted to read output at {path}.")
            self.parse_fail_counter += 1

        if self.parse_fail_counter >= self.parse_fail_threshold:
            raise RuntimeError('TOO MANY PARSE FAILS')

        with open(f"{os.path.join(self.directory, self.job_name)}.json",'w') as json_file:
            json.dump(data, json_file,indent="")

    def OneIter(self,**kwargs):
        if self.status == 'failed':
            self.parse_output()
            self.prune_temp_files()
            return self.status
        if self.status == 'completed':
            self.parse_output() #maybe have a flag for whether to do this?
            #right now, I need this to happen
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
    
    def final_parse(self):
        pass
    
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
            self.prune_temp_files()
            return 1
        elif self.status == 'succeeded':
            self.final_parse()
            return 0

    def prune_temp_files(self):
        print()
        print("////////////////////////////////////////////////////////") 
        print('removing .tmp files')
        files_to_remove = glob.glob(os.path.join(self.directory, '*{self.tmp_extension}*'))

        for file in files_to_remove:
            print(file)
            try:
                os.remove(file)
                print(f"Removed: {file}")
            except OSError as e:
                print(f"Error removing {file}: {e}")

        print("////////////////////////////////////////////////////////")
        print()


class ORCAHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = ORCARULES
        self.output_extension = '.out'
        self.input_extension = '.inp'
        self.program = 'orca'

    def interpret_fp_out(self,file_parser_output):
        self.status = 'failed'
        if file_parser_output['is_opt']:
            if file_parser_output['success'] and file_parser_output['opt_success']:
                self.status = 'succeeded'
            if file_parser_output['imaginary_frequencies']:
                self.status = 'failed'
        else:
            self.status = 'succeeded' if file_parser_output['success'] else 'failed'

    def final_parse(self):
        opp = postprocessing.OrcaPostProcessor(self.directory,self.job_name)
        opp.pp_routine()


class GaussianHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = GAUSSRULES
        self.output_extension = '.log'
        self.input_extension = '.gjf'
        self.program = 'gaussian'
    
    def interpret_fp_out(self, file_parser_output):
        if file_parser_output['is_opt_freq']:
            self.status = 'succeeded' if file_parser_output['success_opt_freq'] else 'failed'
        else:
            self.status = 'succeeded' if file_parser_output['success'] else 'failed'

class CRESTHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = CRESTRULES
        self.output_extension = '.out'
        self.input_extension = '.sh'
        self.program = 'crest'

class xTBHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = XTBRULES
        self.output_extension = '.out'
        self.input_extension = '.sh'
        self.program = 'xtb'

class pyAromaHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = PYAROMARULES
        self.output_extension = '.out'
        self.input_extension = '.sh'
        self.program = 'pyaroma'


