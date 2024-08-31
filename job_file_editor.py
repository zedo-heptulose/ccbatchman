import re
import os


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



def copy_change_name(jobname,rules,existing_dir='.',destination_dir='.'):
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


            
    

