import sys
path = '/gpfs/home/gdb20/code/mol-maker/src'
if not path in sys.path:
    sys.path.append(path)

import input_generator
import input_combi
import cc_workflow_generator as ccwg
import file_parser

import os
import json
import shutil
import re

import subprocess

# probably most of these aren't necessary. fix later

def run_command(command, workdir):
    result = subprocess.run(command, shell=True, cwd=workdir,
                             capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def convert_xyz(filename,in_folder,out_folder):
    '''
    this breaks if your filename has the '.' character anywhere other than the extension
    '''
    # print('we doing anything here?')
    basename = filename.split('.')[0]
    command = f"""
conda init
source ~/.bashrc
conda activate CHM4411L
obabel {filename} -O {basename}.gzmat
    """
    # print(command)
    output = run_command(
        command,
        in_folder
    )
    # print(output)
    shutil.move( os.path.join( in_folder,f'{basename}.gzmat' ),os.path.join( out_folder, f'{basename}.gzmat' ) )


def gzmat_to_orca(lines,charge =None,multiplicity=None,debug=False):
    variable_pattern = r'([ard]\d+)'
    charge_mult = r'(-?\d)(?:\s+)(\d)'
    cm_line_index = -1 #also the index before coords
    coords_end_index = -1
    cm_found = False
    for i, line in enumerate(lines):
        cm = re.search(charge_mult,line)
        if cm and not cm_found:
            if not charge:
                charge = int(cm.group(1))
            if not multiplicity:
                multiplicity = int(cm.group(2))
            cm_line_index = i
            cm_found = True
            
            if debug:
                print('------------------')
                print('charge:')
                print(charge)
                print('multiplicity')
                print(multiplicity)
        if 'Variables:' in line:
            coords_end_index = i
    coords_begin_index = cm_line_index +1
    coord_lines = lines[coords_begin_index:coords_end_index]
    variable_lines = lines[coords_end_index+1:-1]
    if debug:
        print('------------------')
        print('cm_line_index:')
        print(cm_line_index)
        print('coords begin index:')
        print(coords_begin_index)
        print('coords end index:')
        print(coords_end_index)
        print('------------------')
        print('captured coordinates:')
        print(*coord_lines)
        print('------------------')
        print('variable lines:')
        print(*variable_lines)
        print('------------------')
        print('catpured variables:')
    var_pattern = r'([rad]\d+)(?:=\s*)(\d+\.\d+)'
    coord_variables = {}
    for line in variable_lines:
        var = re.search(var_pattern,line)
        if var:
            varname = var.group(1)
            value = float(var.group(2))
            coord_variables[varname] = value
    if debug:
        print('collected variables')
        print(type(coord_variables))
        print(coord_variables)

    r_vars = [var for var in coord_variables.keys() if 'r' in var]
    a_vars = [var for var in coord_variables.keys() if 'a' in var]
    d_vars = [var for var in coord_variables.keys() if 'd' in var]
    
    if debug:
        print('------------------')
        print('r vars:')
        print(*r_vars,sep='\n')
        print('a vars:')
        print(*a_vars,sep='\n')
        print('d vars:')
        print(*d_vars,sep='\n')
        print('------------------')
        print('line substitutions')
    
    var_pattern = r'[rad]\d+'

    new_lines = []
    for line in coord_lines:
        if debug: print(f'  {line}')
        for i in range(3):
            match = re.search(var_pattern,line)
            if match:
                variable = match.group(0)
                value = coord_variables[variable]
                line = re.sub(variable,str(value),line)
                if debug:
                    print(variable)
                    print(value)
                    print(line)
        new_lines.append(line)

    if debug: 
        print('--------------')
        print('rearranging columns and adding zeros')

    rearranged_lines = []
    for line in new_lines:
        fragments = re.split(r'\s+',line)
        first_frag = fragments[0]
        other_frags = fragments[1:-1]
        odd_frags = [frag for i,frag in enumerate(other_frags) if i % 2 == 1]
        even_frags = [frag for i,frag in enumerate(other_frags) if i % 2 == 0]
        while not len(odd_frags) >= 3: 
            odd_frags.append('0.000')
        while not len(even_frags) >= 3:
            even_frags.append('0')
        rearranged_fragments = [first_frag,*even_frags,*odd_frags]
        new_line = " ".join(rearranged_fragments) + '\n'
        if debug:
            print(fragments)
            print(new_line)
        rearranged_lines.append(new_line)
        
    coord_lines = []
    coord_lines.append(f'* int {charge}  {multiplicity}\n')
    coord_lines.extend(rearranged_lines)
    coord_lines.append('*\n')
    
    # coord_lines[1] = coord_lines[1].rstrip() + ' 0 0 0 0.000 0.000 0.000 \n'
    # coord_lines[2] = coord_lines[2].rstrip() + ' 0 0 0 0 \n'
    # coord_lines[3] = coord_lines[3].rstrip() + ' 0 0 \n'
    
    if debug:
        print('------------------')
        print('final ORCA internals:')
        print(*coord_lines)

    return coord_lines