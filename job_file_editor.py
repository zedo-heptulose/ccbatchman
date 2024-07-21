import re

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
    def multiply_re(match):
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
            elif re.search(r'--mem',line) and 'memory' in flags:
                line = re.sub(r'(\d+)',mult_integer(1.6),line)
    # Open the file in write mode
    with open (filename, 'w') as f:
        # Write the new lines to the file (modified in place now)
        f.writelines(lines)
        
        
        
        
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
        if re.match(r'\s*\*\s*'):
            geom_end = index
    if geom_start == -1 or geom_end == -1:
        raise ValueError('No Proper Coordinate Block in Input File')
    
    new_lines = lines[0:geom_start] + coordinates + [' * \n\n']
    
    if len(lines) > geom_end + 1:
        new_lines += lines[geom_end+1:]
    
    with open (filename,'w') as f:
        f.writelines(new_lines)



def add_freq_restart(filename, flags):
    '''
    '''
    if type(flags) is not list: flags = [flags]
    
    with open(filename,'r') as f:
        lines=f.readlines()
    newlines = []
    
    lines[0] = re.sub(r'OPT',r'',lines[0])
    freq_block_start = -1
    
    for index, line in enumerate(lines):
        if 'memory' in flags and re.search(r'%Maxcore',line,flag=re.I):
            lines[index] = re.sub(r'\d+',mult_integer(1.4),line)
        if re.search(r'%freq',line,flag=re.I):
            freq_block_start = index
        if re.search(r'restart\s+true'):
            return True #handle this somehow. Means the job already failed.
    
    if freq_block_start != -1:
        newlines = lines[:freq_block_start+1] + ['restart true'] + lines[freq_block_start+1:]
    else:
        newlines = lines[:1] + [r'% freq','  restart true','end'] + lines[1:]
        
    with open(filename,'w') as f:
        f.writelines(newlines)
    return False #false for, "job has NOT failed here before"

    #will need to debug these with real orca output files



    # seems to be everything necessary for the babysitter to do its work.