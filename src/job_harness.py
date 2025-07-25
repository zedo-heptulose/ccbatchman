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
        in_progress = True # starts true.
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
                # print('---- in job_harness.update_status() ----')
                # print(f'Squeue output: {output}')
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

        
        # print(f" in progress? {in_progress}")
        if in_progress:
            if self.debug: print(f'slurm status:{slurm_status}')   
            # print(f'slurm status:{slurm_status}')
            # print('---- ----')
            if slurm_status == 'PD':
                self.status = 'pending'
                if self.debug: print("returning pending")
                return
    
            elif slurm_status == 'R':
                self.status = 'running'
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
                if self.debug: print(f'OLD OUTPUT FILE {output_filename} NOT FOUND') 
                return 'not_started' #DANGEROUS, EXPECT NEGATIVE CONSEQUENCES
                # something bad only happens if:
                # job is pending and has no slurm output yet
                # we delete the ledger
                # we restart the batch runner before it starts running
                # can be fixed by writing job id to the job's json block and using some logic for that
                # for now, it's fine not to print anything
            
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
        if self.status == 'failed':
            self.prune_temp_files()
        elif self.status == 'succeeded': #this is what we were missing
            self.final_parse()
    
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
       
        files_to_remove = glob.glob(os.path.join(self.directory, f"*{self.tmp_extension}*"))

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
        opp.orca_pp_routine()


class GaussianHarness(JobHarness):
    def __init__(self):
        JobHarness.__init__(self)
        self.ruleset = GAUSSRULES
        self.output_extension = '.log'
        self.input_extension = '.gjf'
        self.program = 'gaussian'
    
    def interpret_fp_out(self, file_parser_output):
        if file_parser_output['is_opt_freq']:
            self.status = 'succeeded' if file_parser_output['success_opt_freq'] and file_parser_output['success_opt_freq_2'] else 'failed'
            if file_parser_output['imaginary_frequencies']:
                self.status = 'failed'
        else:
            self.status = 'succeeded' if file_parser_output['success'] else 'failed'
        

    def final_parse(self):
        """Extract final coordinates from successful optimization job"""
        with open(os.path.join(self.directory,'job_config.json'),'r') as json_file:
            data = json.load(json_file)

        if data['run_type']:
            if 'opt' in data['run_type'].lower(): 
                print('################')
                print('parsing finally!')
                print('################')
                self.extract_final_coordinates() 

    @property
    def output_path(self):
        return os.path.join(self.directory, self.job_name) + self.output_extension
    
    def extract_final_coordinates(self):
        """Extract final coordinates from Gaussian output file and save as XYZ"""
        output_path = self.output_path
        xyz_path = os.path.join(self.directory, self.job_name) + '.xyz'
        
        if not os.path.exists(output_path):
            print(f"Output file not found: {output_path}")
            return
        
        try:
            with open(output_path, 'r') as f:
                lines = f.readlines()
            
            # Find the last occurrence of Standard orientation
            standard_orientation_indices = [i for i, line in enumerate(lines) if ("Input orientation" in line) or ("Standard orientation" in line)]
            
            if not standard_orientation_indices:
                print(f"No standard orientation section found in {output_path}")
                return
            
            last_orientation_index = standard_orientation_indices[-1]
            
            # Extract coordinates
            coord_lines = []
            atoms = []
            i = last_orientation_index + 5  # Skip header lines
            
            while i < len(lines) and not "---" in lines[i]:
                parts = lines[i].split()
                if len(parts) >= 6:
                    atomic_num = int(parts[1])
                    x, y, z = float(parts[3]), float(parts[4]), float(parts[5])
                    
                    # Convert atomic number to symbol
                    symbol = self._atomic_number_to_symbol(atomic_num)
                    atoms.append((symbol, x, y, z))
                i += 1
            
            # Write XYZ file
            with open(xyz_path, 'w') as xyz_file:
                xyz_file.write(f"{len(atoms)}\n")
                xyz_file.write(f"Final coordinates from {self.job_name} optimization\n")
                for atom in atoms:
                    symbol, x, y, z = atom
                    xyz_file.write(f"{symbol}  {x:.6f}  {y:.6f}  {z:.6f}\n")
            
            print(f"Successfully extracted coordinates to {xyz_path}")
            
        except Exception as e:
            print(f"Error extracting coordinates from {output_path}: {str(e)}")
    
    def _atomic_number_to_symbol(self, atomic_num):
        """Convert atomic number to element symbol"""
        elements = {
            1: 'H', 2: 'He', 3: 'Li', 4: 'Be', 5: 'B', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 10: 'Ne',
            11: 'Na', 12: 'Mg', 13: 'Al', 14: 'Si', 15: 'P', 16: 'S', 17: 'Cl', 18: 'Ar', 19: 'K',
            20: 'Ca', 21: 'Sc', 22: 'Ti', 23: 'V', 24: 'Cr', 25: 'Mn', 26: 'Fe', 27: 'Co', 28: 'Ni',
            29: 'Cu', 30: 'Zn', 31: 'Ga', 32: 'Ge', 33: 'As', 34: 'Se', 35: 'Br', 36: 'Kr'
        }
        return elements.get(atomic_num, f"X{atomic_num}")


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


