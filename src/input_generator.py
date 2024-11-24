import os
import re
import shutil
import json
import helpers

CONFIGPATH = '../config/input_generator_config/'
ORCACONFIG = 'orca_config.json'
GAUSSCONFIG = 'gaussian_config.json'
CRESTCONFIG = 'crest_config.json'
XTBCONFIG = 'xtb_config.json'
PYAROMACONFIG = 'pyaroma_config.json'
BATCHRUNNERCONFIG = 'batch_runner_config.json'

class Input:
    def __init__(self): 
        self.directory = ""
        self.basename = ""
        self.extension = ""

    def cleanup(self):
        raise NotImplementedError()

    def write_file(self):
        raise NotImplementedError()

    def load_file(self,filename,directory=''):
        raise NotImplementedError()

class CCInput(Input):
    def __init__(self):
        Input.__init__(self)
        self.keywords = []
        self.charge = 0
        self.multiplicity = 1
        self.xyzfile = "" 
        self.coordinates = []
        self.debug = False


class ORCAInput(CCInput):
    def __init__(self):
        CCInput.__init__(self)
        self.strings = []
        self.blocks = {}
        self.extension = '.inp'

    def cleanup(self):
        self.keywords = [keyword for keyword in self.keywords if keyword]
        self.strings = [string for string in self.strings if string]
        self.blocks = {block : self.blocks[block] for block in self.blocks if block}
        return self
    
    def write_file(self):
        self.cleanup()
        full_path= os.path.join(self.directory,self.basename) + self.extension 
        with open (full_path,'w') as file:
            for keyword in self.keywords:
                file.write(f'! {keyword.strip()}\n')
            file.write('\n')
            for string in self.strings:
                file.write(f'{string.strip()}\n')
            file.write('\n')
            for block in self.blocks:
                file.write(f'%{block.strip()}\n')
                for line in self.blocks[block]:
                    file.write(f' {line.strip()}\n')
                file.write('end\n\n')
            file.write('\n')
            file.write(f"* xyzfile {self.charge} {self.multiplicity} {self.xyzfile} \n\n")

    def load_file(self,path):
        path = os.path.normpath(path)
        filename = os.path.basename(path)
        self.basename = os.path.splitext(filename)[0]
        self.directory = os.path.dirname(path)
        
        with open(path,'r') as input_file:
            lines = input_file.readlines()
             
        self.keywords = []
        self.blocks = {}
        self.strings = []
        self.charge = 0
        self.multiplicity = 1
        self.xyzfile = ''
        self.coordinates = []

        in_block_flag = False
        temp_block = ['',[]]
        for line in lines:
            if self.debug: print(line)
            #TODO: MAKE THIS MORE FLEXIBLE TO MATCH WITH ALL ORCA SYNTAX
            if in_block_flag:
                if re.match(r'\s*end',line,re.I):
                    self.blocks[temp_block[0]] = temp_block[1]
                    in_block_flag = False
                    temp_block[0] = ''
                    temp_block[1] = []
                    if self.debug: print(f'ending block')
                else:
                    if self.debug: print('in temp block')
                    temp_block[1].append(line.strip())

            elif re.match(r'\s*%\s*maxcore\s+\d+',line,re.I):
                if self.debug: print('maxcore line found')
                self.strings.append(line.strip())

            elif re.match(r'\s*!',line):
                line = re.match(r'(?:\s*!)(.*)',line).group(1)
                keys = list(re.split(r'\s+',line))
                self.keywords.extend(keys)
                if self.debug: print(f'adding keywords: {keys}')
           
            elif re.match(r'\s*%',line):
                name = re.match(r'(?:\s*%)(\b.+\b)',line).group(1)
                temp_block[0] = name
                in_block_flag = True
                if self.debug: print(f'starting block with name: {name}')


            elif re.match(r'\s*\*\s*xyz',line,re.I):
                self.charge = int(re.search(r'([-0-9]+)(?:\s+\d+)',line).group(1))
                self.multiplicity = int(re.search(r'(?:[-0-9]\s+)(\d+)',line).group(1))
                if re.match(r'\s*\*\s*xyzfile',line,re.I):
                    self.xyzfile = re.search(r'(\S+\.xyz\b)',line).group(1)
                if self.debug: print(f'charge: {self.charge} multiplicity: {self.multiplicity} xyz fn: {self.xyzfile}')









class GaussianInput(CCInput):
    def __init__(self):
        CCInput.__init__(self)
        self.nprocs = 1
        self.mem_per_cpu_gb = 2
        self.title = "super secret special scripts shaped sthis submission sfile"
        self.extension = ".gjf"
        self.chkpath = '' 

    def cleanup(self):
        self.keywords = [keyword for keyword in self.keywords if keyword]
    
    def write_file(self):
        self.cleanup()
        full_path = os.path.join(self.directory,self.basename) + self.extension
        #NOTE: Gaussian input assumes an xyz file in the same directory as the .gjf file to be made 
        #full_xyz_path = os.path.join(self.directory,self.xyzfile)  
        if not self.coordinates:
            if self.debug: print('existing coordinates not found')
            xyz_path = os.path.join(self.directory,self.xyzfile)
            if self.debug: print(f"reading coordinates from path {xyz_path}")
            if os.path.exists(xyz_path):
                with open(xyz_path,'r') as xyzfile:
                    self.coordinates = xyzfile.readlines()[2:]
            else:
                print("wrote gaussian input without coordinates")
            if self.debug: print(f"self.coordinates after reading:\n{self.coordinates}")
        
        with open(full_path,'w') as gjffile:
            path_noext = os.path.splitext(full_path)[0]
            gjffile.write(f"%nprocshared={self.nprocs}\n")
            gjffile.write(f"%mem={int(self.nprocs*self.mem_per_cpu_gb)}gb\n")
            gjffile.write(f"%chk={path_noext}.chk\n")
            gjffile.write(f"#{' '.join(self.keywords)}\n")
            gjffile.write(f"\n")
            gjffile.write(f"{self.title}\n")
            gjffile.write(f"\n")
            gjffile.write(f"{self.charge} {self.multiplicity}\n")
            if self.coordinates:
                gjffile.writelines(self.coordinates)
            gjffile.write(f"\n\n")
    
    def load_file(self,path):
        #BE WARY, WE MUST USE ABSOLUTE PATHS WHEN WORKING WITH GAUSSIAN
        path = os.path.normpath(path)
        filename = os.path.basename(path)
        self.basename = os.path.splitext(filename)[0]
        self.directory = os.path.dirname(path)

        with open(path,'r') as input_file:
            lines = input_file.readlines()

        self.keywords = []
        self.charge = 0
        self.multiplicity = 1
        self.xyzfile = ''
        self.nprocs = -1
        self.mem_per_cpu_gb = -1
        self.title = ""
        self.chkpath = ''
        self.coordinates = []

        mem = -1 
        keywords_passed_flag = False
        start_title_flag = False
        read_coordinates_flag = False
        for line in lines:
            if self.debug: print(line)
            #TODO: match flexibility of Gaussian syntax
            #TODO: FIX THIS. Sometimes there is input after the coordinates; 
            #this does not acknowledge that presently.
            if read_coordinates_flag:
                if self.debug: print(f"looking for coordinates")
                if not re.match(r'^\s*$',line):
                    self.coordinates.append(line)
                
            elif re.match(r'\s*%\s*nprocs',line,re.I):
                self.nprocs = int(re.search(r'\d+',line)[0])
                if self.debug: print(f'setting nprocs: {self.nprocs}')
            
            elif re.match(r'\s*%\s*mem\s*',line,re.I):
                mem = int(re.search(r'(\d+)(?:\s*gb)',line,re.I).group(1)) / self.nprocs
                if self.debug: print(f'setting mem_per_cpu: {self.mem_per_cpu_gb}')

            elif re.match(r'\s*chk\s*',line,re.I):
                self.chkpath = re.search(r'(?:=)(.+\.chk)',line).group(1)
                if self.debug: print(f'setting chkpath: {self.chkpath}')
                
            elif re.match(r'\s*#',line):
                line = re.match(r'(?:\s*#)(.*)',line).group(1)
                keys = list(re.split(r'\s+',line))
                self.keywords.extend([key for key in keys if key])
                keywords_passed_flag = True
                if self.debug: print('reading keywords: {keys}')
                
            elif re.match(r'^\s*$',line) and start_title_flag == True:
                start_title_flag = False
                keywords_passed_flag = False
                if self.debug: print('blank line after title, no longer reading title')
            
            elif re.match(r'^\s*$',line) and keywords_passed_flag == True:
                start_title_flag = True
                if self.debug: print('blank line found after keywords, looking for title')

            elif re.match(r'\s*\S+',line) and start_title_flag == True:
                self.title += line
                if self.debug: print(f'adding line to title. Title so far: {self.title}')
            
            elif re.match(r'\s*[-0-9]+\s+\d+',line):
                #THE OFFENDER: \d+ does not see the '-' character
                self.charge = int(re.search(r'([-0-9]+)(?:\s+\d+)',line).group(1))
                self.multiplicity = int(re.search(r'(?:[-0-9]+\s+)(\d+)',line).group(1))
                read_coordinates_flag = True
                if self.debug: print(f'reading charge and multiplicity. Charge: {self.charge} Multiplicity: {self.multiplicity}')
            

        #TODO: allow more flexibility here
        self.mem_per_cpu_gb = int(mem // self.nprocs)
        if mem == -1:
            raise ValueError('memory flag not read')
            #if self.debug: print('WARNING: mem_per_cpu not found! using default 2gb/core')
            #self.mem_per_cpu_gb = 2
        if self.nprocs == -1:
            raise ValueError('nprocs flag not read')
            #if self.debug: print('WARNING: nprocs not found! using default 1 processor')
            #self.nprocs = 1

        self.title = self.title.strip()
        if self.debug: print(f"coordinates:\n{self.coordinates}")







class SbatchScript(Input):
    def __init__(self):
        Input.__init__(self)
        self.extension = '.sh'
        self.sbatch_statements = []
        self.commands = []

    @property
    def full_path(self):
        return os.path.join(self.directory,self.basename) + '.sh'
    
    def cleanup(self):
        self.sbatch_statements = [statement for statement in self.sbatch_statements if statement]
        self.commands = [command for command in self.commands if command]
    
    def write_file(self):
        self.cleanup()
        with open (self.full_path,'w') as file:
            file.write('#!/bin/bash\n\n')
            for statement in self.sbatch_statements:
                file.write(f'#SBATCH {statement.strip()}\n')
            file.write('\n')
            for command in self.commands:
                file.write(f'{command.strip()}\n')

    def reset(self):
        self.directory = ""
        self.basename = ""
        self.sbatch_statements = []
        self.commands = []
    
    def load_file(self,path):
        
        with open(path,'r') as file:
            lines = file.readlines()
        for line in lines:
            if line.strip() == '#!/bin/bash':
                pass
            elif line.startswith('#SBATCH'):
                self.sbatch_statements.append(line[7:].strip())
            elif line.strip():
                self.commands.append(line.strip())


class pyAromaScript(SbatchScript):
    def __init__(self):
        SbatchScript.__init__(self)
        self.xyzfile = ""
        #for now, we feed it the right xyz filename from the start.
        #in fact, in input_combi, whenever using coords_from,
        #we just shouldn't have coordinates!
        #for gaussian, iunno, make it one ghost atom or something


#TODO: FIX THIS!!!!!!!!!!!!!!!
#THIS IS BROKEN
#for now, this is kinda a hack that can't be
#modified beyond just changing the coordinates
class xTBScript(SbatchScript):
    def __init__(self):
        SbatchScript.__init__(self)
        self.xyzfile = ""

    def write_file(self):
        new_commands = []
        for command in self.commands.copy():
            match = re.match(r'(?:\b)([A-Za-z0-9_+-]+.xyz)',command)
            if match:
                command = re.sub(match.group(1),self.xyzfile,command)
            new_commands.append(command)
        self.commands = new_commands
        SbatchScript.write_file(self)
    
    def load_file(self,path):
        SbatchScript.load_file(self,path)
        #no commands, so this does nothing
        for command in self.commands:#this is a blank slate if loading.
            match = re.match(r'(?:\b)([A-Za-z0-9_+-]+.xyz)',command)
            if match:
                self.xyzfile = match.group(1)

    #this looks wrong. Has this all actually been working?



class Job:
    def __init__(self):
        self.debug = False
        self.directory = "./"
        self.inp = Input() #or None, or other type #this throws an exception if not replaced
        self.sh = SbatchScript()
        self.xyz_directory = "./"
        self.xyz = "test.xyz"
        
    def create_directory(self,**kwargs):
        force_overwrite = kwargs.get('force',False)
        file_exists = os.path.exists(self.directory)
        if file_exists:
            if force_overwrite:
                print(f"overwriting directory: {self.directory}")
                shutil.rmtree(self.directory)
            else:
                raise ValueError('input_files.Job tried to overwrite existing directory')
        
        if self.debug: print(f"making directory: {self.directory}")
        os.makedirs(self.directory)
        source_file = os.path.join(self.xyz_directory,self.xyz)
        if self.debug: print(f"xyz source file: {source_file}")
        dest_file = os.path.join(self.directory,self.xyz)
        if self.debug: print(f"xyz destination file: {dest_file}")
        try:
            shutil.copyfile(source_file, dest_file)
        except Exception as e:
            print(f"Error copying file: {e}")
        
        if self.debug: print('writing input, if applicable')
        if self.inp:
            self.inp.directory = self.directory
            self.inp.write_file()
        if self.debug: print('writing shell script.')
        self.sh.directory = self.directory
        self.sh.write_file()









class InputBuilder:
    def __init__(self):
        raise NotImplementedError('InputBuilder is an abstract class')
        self.config = helpers.load_config_from_file('/path/to/config')
        self.debug = False

    def change_params(self,diff_config):
        for key in diff_config:
            self.config[key] = diff_config[key]
        return self

    def build_input(self):
        raise NotImplementedError()

    def submit_line(self):
        raise NotImplementedError()

    def build_submit_script(self):
        sh = SbatchScript()
        sh.directory = self.config['write_directory']
        sh.basename = self.config['job_basename']
        sh.sbatch_statements = [
            f"--job-name={self.config['job_basename']}",
            f"-n {self.config['num_cores']}",
            f"-N 1",
            f"-p genacc_q",
            f"-t {self.config['runtime']}",
            f"--mem-per-cpu={self.config['mem_per_cpu_GB']}GB",
        ]
        if self.config['pre_submit_lines'] is not None:
            for line in self.config['pre_submit_lines']:
                sh.commands.append(line) 
        
        sh.commands.append(self.submit_line())

        if self.config['post_submit_lines'] is not None:
            for line in self.config['post_submit_lines']:
                sh.commands.append(line)
        return sh


    def build(self):
        newjob = Job()
        
        newjob.directory = self.config['write_directory']
        newjob.xyz_directory = self.config.get('xyz_directory',None) 
        newjob.xyz = self.config.get('xyz_file',None)

        newjob.sh = self.build_submit_script() 
        newjob.inp = self.build_input()
        
        return newjob
       










class ORCAInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(f'{CONFIGPATH}{ORCACONFIG}') 
    
    def submit_line(self):
        return f"{self.config['path_to_program']} {self.config['job_basename']}.inp > {self.config['job_basename']}.out"
    
    def build_input(self):
        ################ inp options #####################
        inp = ORCAInput() 
        inp.directory = self.config['write_directory']
        inp.basename = self.config['job_basename']
        
        inp.keywords = [
            'UKS' if self.config['uks'] else None,
            self.config['functional'],
            self.config['basis'],
            self.config['aux_basis'],
            self.config['density_fitting'],
            self.config['dispersion_correction'],
            self.config['bsse_correction'],
            self.config['run_type'],
            'UNO' if self.config['natural_orbitals'] else None,
            'MOREAD' if self.config['moread'] else None,
            self.config['integration_grid'],
            self.config['scf_tolerance'],
            self.config['verbosity'],
        ]
        if type(self.config['other_keywords']) is list:
            inp.keywords.extend(self.config['other_keywords'])
        elif type(self.config['other_keywords']) is str:
            inp.keywords.append(self.config['other_keywords'])

        maxcore = int(self.config['mem_per_cpu_GB']) * 1000 * (3 / 4)
        inp.strings.append(f"%maxcore {int(maxcore)}")
        if not self.config['blocks'].get('pal',None):
            inp.blocks['pal'] = [f"nprocs {self.config['num_cores']}",]
                
        for name in self.config['blocks']:
            inp.blocks[name] = self.config['blocks'][name]
        if self.config['solvent']:
            inp.blocks['CPCM'] = [
                    'SMD TRUE',
                    f"SMDSOLVENT \"{self.config['solvent']}\"", 
                    ]

        if self.config['broken_symmetry']:
            if not inp.blocks.get('scf',None):
                #TODO: bruh. look at this duuuude
                inp.blocks['scf'] = ['brokensym 1,1']
            else:
                condition = False
                for line in inp.blocks['scf']:
                    if 'brokensym' in line.lower():
                        condition = True
                if not condition:
                    inp.blocks['scf'].append('brokensym 1,1')
        
        inp.charge = self.config['charge']
        inp.multiplicity = self.config['spin_multiplicity']
        inp.xyzfile = self.config['xyz_file']
        return inp










class GaussianInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(f"{CONFIGPATH}{GAUSSCONFIG}")

    def submit_line(self):
        return f"{self.config['path_to_program']} < {self.config['job_basename']}.gjf > {self.config['job_basename']}.log"

    def build_input(self):
        inp = GaussianInput()
        #TODO: FIX THIS LATER

        inp.directory = self.config['write_directory']
        inp.basename = self.config['job_basename']
        
        inp.keywords = [
            self.config['run_type'],
            f"{'u' if self.config['uks'] else ''}{self.config['functional']}/{self.config['basis']}",
            self.config['aux_basis'],
            self.config['density_fitting'],
            self.config['dispersion_correction'],
            self.config['bsse_correction'],
            self.config['integration_grid'],
        ]
        if self.config['solvent']:
            inp.keywords.append(f"SCRF(SMD,Solvent={self.config['solvent']})",)
        #TODO: this is untested, look here if there's a problem. 
        if type(self.config['other_keywords']) is list:
            inp.keywords.extend(self.config['other_keywords']) 
        elif type(self.config['other_keywords']) is str:
            inp.keywords.append(self.config['other_keywords'])
    
        if self.config['broken_symmetry']:
            raise ValueError("Gaussian does not support Broken Symmetry")
        if self.config['mix_guess']:
            inp.keywords.append('Guess=Mix')

        inp.nprocs = self.config['num_cores']
        inp.mem_per_cpu_gb = self.config['mem_per_cpu_GB']
        inp.charge = self.config['charge']
        inp.multiplicity = self.config['spin_multiplicity']
        inp.xyzfile = os.path.join(self.config['xyz_file']) 
        return inp










class CRESTInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(f"{CONFIGPATH}{CRESTCONFIG}")

    def submit_line(self):
        command = self.config['path_to_program']
        basename = self.config['job_basename']
        xyz_file = self.config['xyz_file']
        
        options = []
        if self.config['functional'] in ['gfn2','gfn0','gfnff','gfn2//gfnff']:
            options.append(f"--{self.config['functional']}")
        else:
            print('Warning: invalid functional, defaulting to gfn2')
            options.append('--gfn2')
        options.append(f"--chrg {self.config['charge'] if self.config['charge'] else 0}")
        if self.config['uks']:
            options.append(f"--uhf {self.config['spin_multiplicity'] - 1}")
        if self.config['solvent']:
            options.append(f"--alpb {self.config['solvent']}")
        if self.config['cluster']:
            options.append('--cluster')
        if self.config['quick'] in ['quick','squick','mquick']:
            options.append(f"--{self.config['quick']}")
        if self.config['reopt']:
            options.append('--prop reopt')
        
        if self.config['noreftopo']:
            options.append('--noreftopo')
            
        if type(self.config['other_keywords']) is list:
            for keyword in self.config['other_keywords']:
                options.append(f"--{keyword}")
        elif type(self.config['other_keywords']) is str:
            options.append(f"--{self.config['other_keywords']}")

        submit_line = f"{command} {xyz_file} > {basename}.out " + " ".join(options)
        return submit_line

    def build_input(self):
        return None










class xTBInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(os.path.join(CONFIGPATH,XTBCONFIG))

    def submit_line(self):
        command = self.config['path_to_program']
        basename = self.config['job_basename']
        xyz_file = self.config['xyz_file']
        
        options = []
        functional = self.config['functional']
        if functional in ['gfn2','gfn0','gfnff','2',2,'0',0,'ff']:
            functional = functional[3:] if str(functional).startswith('gfn') else functional
            options.append(f"--gfn {functional}")
        else:
            print('Warning: invalid functional, defaulting to gfn2')
            options.append('--gfn 2')

        options.append(f"-P {self.config['num_cores']}")
        
        options.append(f"--chrg {self.config['charge'] if self.config['charge'] else 0}")
        
        if self.config['uks']:
            options.append(f"--uhf {self.config['spin_multiplicity'] - 1}")
        
        if self.config['solvent']:
            options.append(f"--alpb {self.config['solvent']}")
       
        if self.config['run_type']:
            options.append(f"--{self.config['run_type']}")
            
        if type(self.config['other_keywords']) is list:
            for keyword in self.config['other_keywords']:
                options.append(f"--{keyword}")
        elif type(self.config['other_keywords']) is str:
            options.append(f"--{self.config['other_keywords']}")

        
        submit_line = f"{command} {xyz_file} > {basename}.out " + " ".join(options)
        return submit_line
        
    def build_input(self):
        return None






class pyAromaInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(os.path.join(CONFIGPATH,PYAROMACONFIG))


    def submit_line(self):
        command = self.config['path_to_program']
        basename = self.config['job_basename']
        xyz_file = self.config['xyz_file']
        program = self.config['cc_program']

        submit_line = f"python3 {command} {xyz_file} -o {basename}.xyz -p {program} -v > {basename}.out"
        return submit_line

    def build_input(self):
        return None

    #TODO: rename this json loader function, this is kinda dumb
class BatchRunnerInputBuilder(InputBuilder):
    def __init__(self):
        self.config = helpers.load_config_from_file(os.path.join(CONFIGPATH,BATCHRUNNERCONFIG))

    def submit_line(self):
        command = self.config['path_to_program']
        job_basename = self.config['job_basename']
        max_jobs = self.config['max_jobs']
        verbose = self.config['verbosity']

        verbose_string = '-v' if verbose else ''
        submit_line = f"python3 {command} batchfile.csv {verbose_string} -j {max_jobs} > {job_basename}.out"
        return submit_line

    def build_input(self):
        return None #this is handled by input_combi
