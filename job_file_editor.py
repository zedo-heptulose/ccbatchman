import re
import os
import shutil

# this looks pretty solid.
def get_orca_coordinates(filename):
    '''
    This function gets the coordinates from a file
    '''
    # Open the file
    with open(filename, 'r') as f:
        # Read the lines of the file
        lines = f.readlines()  
        #find the lines to read between
        start = 0
        end = 0
        for i, line in enumerate(lines):
            if 'CARTESIAN COORDINATES (ANGSTROEM)' in line:
                start = i + 2
            if 'CARTESIAN COORDINATES (A.U.)' in line:
                end = i - 2
        # Initialize the coordinates list
        coord_lines = []
        # Iterate over the lines
        for line in lines[start:end]:
            coord_lines.append(line)
    
        return coord_lines
    
    
def mult_integer(integer):
    # Convert the matched string to an integer, double it, and return as string
    print('mult_integer called')
    def multiply_re(match):
        print(f're match group: {match.group(0)}')
        return str(int(int(match.group(0)) * int))
    return multiply_re

# alright, solid function for modifying batch files. 
# note - also would want the manager to make a safety directory with old output files,
# not just overwrite them.
def change_sbatch_file(filename,flags):
    '''
    This function changes the sbatch file
    '''
    if type(flags) is not list:
        flags = [flags]
    # Open the file
    with open (filename, 'r') as f:
        # Read the lines of the file
        lines = f.readlines()
        # Initialize the new lines list
        new_lines = []
        # Iterate over the lines
        for line in lines:
            #replace problem lines with good lines
            if re.search(r'-t',line) and 'time' in flags:
                line = re.sub(r'(\d+)(?:-)',mult_integer(2),line)
                #want to switch to nodeless and mem-per-core
            elif re.search(r'--mem',line) and 'memory' in flags:
                line = re.sub(r'(\d+)',mult_integer(1.6),line)
    # Open the file in write mode
    with open (filename, 'w') as f:
        # Write the new lines to the file (modified in place now)
        f.writelines(lines)
        
        
#debugged and works fine
def replace_geometry(filename,coordinates):
    '''
    fixes failed geometry optimization
    '''
    with open(filename,'r') as f:
        lines = f.readlines()
        
    geom_start = -1
    geom_end = -1
    for index, line in enumerate(lines):
        if re.search(r'\*\s*XYZ',line):
            geom_start = index
        if re.match(r'\s*\*\s*',line):
            geom_end = index
    if geom_start == -1 or geom_end == -1:
        raise ValueError('No Proper Coordinate Block in Input File')
    
    new_lines = lines[0:geom_start+1] + coordinates + [' * \n\n']
    
    if len(lines) > geom_end + 1:
        new_lines += lines[geom_end+1:]
    
    with open (filename,'w') as f:
        f.writelines(new_lines)

def remove_opt_line(filename):
    '''
    '''
    with open(filename,'r') as f:
        lines=f.readlines()
    
    lines[0] = re.sub(r'OPT',r'',lines[0])

    with open(filename,'w') as f:
        f.writelines(lines)


#debugged and works fine
def add_freq_restart(filename):
    '''
    '''
    
    with open(filename,'r') as f:
        lines=f.readlines()
    newlines = []
    
    lines[0] = re.sub(r'OPT',r'',lines[0])
    freq_block_start = -1
    
    for index, line in enumerate(lines):
        freq_pattern = re.compile(r'%\s*freq',re.I)
        if re.search(freq_pattern,line):
            freq_block_start = index
        
        if re.match(r'\s*restart\s+true\s*',line):
            return True # no edit takes place if this is already here

    if freq_block_start == -1:
        newlines = lines[:1] + ['\n',r'%freq' + '\n','  restart true\n','end\n','\n'] + lines[1:]
    else:
        newlines = lines[:freq_block_start+1] + ['  restart true\n'] + lines[freq_block_start+1:]
    
    with open(filename,'w') as f:
        f.writelines(newlines)
    return False #false for, "job has NOT failed here before"


def increase_memory(filename, multiplier):
    
    with open(filename,'r') as f:
        lines= f.readlines()
        
    print('in increase_memory')
    maxcore_pattern = re.compile(r'%maxcore',re.IGNORECASE)
    for index, line in enumerate(lines):
        if  re.search(maxcore_pattern,line):
            print('updating memory settings')
            lines[index] = re.sub(r'(\d+)',str(int(int(re.search(r'(\d+)',line).group(0)) * multiplier)),line)

    with open(filename,'w') as f:
        f.writelines(lines)



def copy_change_name(jobname,rules,existing_dir='.',destination_dir='.',change_coords=True):
    '''
    expects a list of rules,
    which are pairs of arguments passed to re.sub
    and applied to all filenames and the contents of the whole file
    
    obviously this can go wrong if you sub something like '.xyz',
    so don't be stupid about it

    note also that this uses regular expressions by default.
    '''
    #TODO: tolerate appended '/' or lack thereof on dir arguments.
    #for now, assume there will be no trailing slash.
    existpath = f'{existing_dir}/{jobname}/{jobname}'
    extensions = ['.sh','.inp']

    if len(rules) == 0:
        raise ValueError('Cannot call copy_change_name without rules')
    
    new_jobname = jobname
    for rule in rules:
        if len(rule) != 2:
            raise ValueError('Rules for job_file_editor.copy_change_name() must be length-2 tuples or lists')
        if rule[0] == '--append':
            new_jobname = jobname + rule[1]
        else:
            pattern = re.compile(rule[0])
            replace = rule[1]
            new_jobname = re.sub(pattern,replace,new_jobname)

    newpath = f'{destination_dir}/{new_jobname}/{new_jobname}'
    newdirpath = f'{destination_dir}/{new_jobname}'
    if not os.path.exists(newdirpath):
        os.makedirs(newdirpath)

    for extension in extensions:
        with open(existpath + extension,'r') as old_file:
            lines = old_file.readlines()
            newlines = []
            for line in lines:
                new_line = re.sub(jobname,new_jobname,line)
                newlines.append(new_line)

            with open(newpath + extension,'w') as new_file:
                new_file.writelines(newlines)

    if change_coords:
        coords = get_orca_coordinates(f'{existpath}.out')
        replace_geometry(f'{newpath}.inp',coords)

def sort_into_directories(directory,extension,sh_filename):
    files = os.listdir(directory)
    files = [file for file in files if file.endswith(extension)]
    for file in files:
        jobname = os.path.basename(file).split('.')[0]
        os.mkdir(f'./{jobname}')
        shutil.copyfile(f'./{directory}/{file}',f'./{jobname}/{file}')
        #now get the shell script ready
        with open(sh_filename,'r') as script:
            lines = script.readlines()
            new_lines = []
            for line in lines:
                new_line = re.sub(r'\<job_name\>',jobname,line)
                new_lines.append(new_line)
        
            with open(f'./{jobname}/{jobname}.sh','w') as scr_copy:
                scr_copy.writelines(new_lines)
            
        

def add_tddft_block(filename):
    '''
    '''
    #TODO: get rid of this entirely. There is a better, more general way.
    with open(filename,'r') as old_version:
        lines = old_version.readlines()
        insert_index = -1
        coordinate_pattern = re.compile(r'\s*\*\s*XYZ',re.I)
        tddft_pattern = re.compile(r'%\s*tddft',re.I)
        for index, line in enumerate(lines):
            if re.search(coordinate_pattern,line):
                insert_index = index
            elif re.search(tddft_pattern,line):
                print(f'file {filename} already contains tddft block')
                return 

        if insert_index == -1:
            raise ValueError('Bad Orca File Format, Needs Coordinates')
        
        new_lines = []
        new_lines += lines[:insert_index]
        new_lines += [
                '%tddft\n',
                '  nroots = 50\n',
                '  maxdim = 5\n',
                'end\n',
                ]
        new_lines += lines[insert_index:]

        with open(filename,'w') as new_version:
            new_version.writelines(new_lines)

def add_block(filename,add_lines):
    with open(filename,'r') as old_version:
        lines = old_version.readlines()
        insert_index = -1
        coordinate_pattern = re.compile(r'\s*\*\s*XYZ',re.I)
        for index, line in enumerate(lines):
            if re.search(coordinate_pattern,line):
                insert_index = index

        if insert_index == -1:
            raise ValueError('Bad Orca File Format, Needs Coordinates')
        
        new_lines = []
        new_lines += lines[:insert_index]
        new_lines += add_lines
        new_lines += lines[insert_index:]

        with open(filename,'w') as new_version:
            new_version.writelines(new_lines)

def strip_keywords(filename,*args):
    with open(filename,'r') as old_version:
        lines=old_version.readlines()
    new_lines = []
    for line in lines:
        for keyword in args:
            line = re.sub(keyword,'',line)
        new_lines.append(line)

    with open(filename,'w') as new_version:
        new_version.writelines(new_lines)

def add_keywords(filename,*args):
    '''
    This function is used to add commands starting with '!'
    the ! operator is implicit here, so just include the command.
    '''
    with open(filename,'r') as old_version:
        lines=old_version.readlines()
    new_lines = []
    commands_end_index = -1
    for index, line in enumerate(lines):
        if re.match('\s*!',line):
            commands_end_index = index
    if commands_end_index == -1:
        raise ValueError('Invalid ORCA File Format')
    new_lines = []
    new_lines += lines[:commands_end_index+1]
    for command in args:
        new_lines.append(f'! {command} \n')
    new_lines += lines[commands_end_index+1:]

    with open(filename,'w') as new_version:
        new_version.writelines(new_lines)

def new_jobs_from_existing(old_dir,new_dir,search,name_rules,remove_keywords,append_keywords,other_functions,change_coords=True):
    job_dir_list = os.listdir(old_dir)
    for jobname in (dn for dn in job_dir_list if re.search(search,dn)):
        try:
            copy_change_name(jobname,name_rules,old_dir,new_dir,change_coords)
        except:
            print('{old_dir}/{jobname} ommitted, unfinished job or other error')
    new_job_dir_list = os.listdir(new_dir)
    for jobname in (dn for dn in new_job_dir_list if re.search(search,dn)):
        new_path = f'{new_dir}/{jobname}/{jobname}.inp'
        for function in other_functions:
            #this expects a function with one argument, which is a filename
            function(new_path)
        strip_keywords(new_path,*remove_keywords)
        add_keywords(new_path,*append_keywords)

def tddft_from_finished_jobs(old_dir,new_dir,search=''):
    new_jobs_from_existing(old_dir,new_dir,search,
                            name_rules=[('--append','_tddft')],
                            remove_keywords=[r'\bOPT\b',r'\bFREQ\b',r'\bUNO\b'],
                            append_keywords=['TightSCF'],
                            other_functions=[add_tddft_block],
                            change_coords=True
                            )

def singlepoint_from_finished_jobs(old_dir,new_dir,search=''): 
    new_jobs_from_existing(old_dir,new_dir,search,
                            name_rules=[('--append','_singlepoint')],
                            remove_keywords=[r'\bOPT\b',r'\bFREQ\b',r'\bUNO\b'],
                            append_keywords=[],
                            other_functions=[],
                            change_coords=True
                            )

def frequencies_from_finished_jobs(old_dir,new_dir,search=''):
    new_jobs_from_existing(old_dir,new_dir,search,
                            name_rules=[('--append','_freq'),('opt','')],
                            remove_keywords=[r'\bOPT\b',r'\bFREQ\b'],
                            append_keywords=['FREQ'],
                            other_functions=[],
                            change_coords=True
                            )

#this one doesn't cleanly work with the DRY function, I guess I'll leave it like this
def uno_analysis_from_finished_jobs(old_dir,new_dir,search='',functional=''):
    #this is a brutal hack
    job_dir_list = os.listdir(old_dir)
    for jobname in (dn for dn in job_dir_list if re.search(search,dn)):
        copy_change_name(jobname,[('--append','_uno-analysis')],old_dir,new_dir)
        shutil.copyfile(f'./{old_dir}/{jobname}/{jobname}.uno',f'./{new_dir}/{jobname}_uno-analysis/{jobname}_uno-analysis.uno') 
    new_job_dir_list = os.listdir(new_dir)
    for jobname in(dn for dn in new_job_dir_list if re.search(search,dn)):
        old_out_path = f'{old_dir}/{jobname}/{jobname}.out'
        new_path = f'{new_dir}/{jobname}/{jobname}.inp'
        strip_keywords(new_path,r'\bUKS\b',r'\bOPT\b',r'\bFREQ\b',r'\bUNO\b',
                r'\bRIJCOSX\b',r'\bAUTOAUX\b',f'\\b{functional}\\b')
        add_keywords(new_path,'Normalprint noiter MOREAD')
        add_block(new_path,[f'%moinp "{jobname}.uno"\n'])
