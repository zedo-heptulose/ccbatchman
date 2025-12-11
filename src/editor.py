import os
import shutil
import re
import input_generator

def replace_xyz_file(input_path,xyz_path,program):
    '''
    expects a full path to an input file or script,
    and a full path to the xyz coordinates to use,
    and the program that the input is for
    '''
    if program.lower() == 'orca':
        input_obj = input_generator.ORCAInput()
    elif program.lower() == 'gaussian':
        input_obj = input_generator.GaussianInput()
    elif program.lower() == 'xtb':
        input_obj = input_generator.xTBScript()
    elif program.lower() == 'pyaroma':
        input_obj = input_generator.pyAromaScript()
    else:
        raise ValueError(
        """
        Invalid Program. List of acceptable programs:
        ORCA | GAUSSIAN | XTB | PYAROMA
        """
        )
    #TODO: fix inconsistent naming conventions
    input_dirpath = os.path.dirname(input_path)
    input_filename = os.path.basename(input_path)
    input_basename = os.path.splitext(input_filename)[0]

    xyz_filename = os.path.basename(xyz_path)
    new_input_xyz_path = os.path.join(input_dirpath,xyz_filename)
    shutil.copy(xyz_path, new_input_xyz_path)

    #the actual logic of this....
    input_obj.directory = input_dirpath
    input_obj.basename = input_basename
    input_obj.load_file(input_path)
    input_obj.xyzfile = os.path.basename(xyz_path)
    input_obj.write_file()


def setup_orbital_read(input_path, gbw_path, program):
    '''
    Copy .gbw file to job directory and modify ORCA input to read orbitals.

    Parameters:
        input_path: full path to the ORCA input file
        gbw_path: full path to the source .gbw file
        program: should be 'orca' (only ORCA supported for now)

    Adds MORead keyword and %moinp block to the input file.
    '''
    if program.lower() != 'orca':
        raise ValueError("Orbital read currently only supported for ORCA")

    input_obj = input_generator.ORCAInput()

    input_dirpath = os.path.dirname(input_path)
    input_filename = os.path.basename(input_path)
    input_basename = os.path.splitext(input_filename)[0]

    # Copy .gbw file to job directory
    gbw_filename = os.path.basename(gbw_path)
    new_gbw_path = os.path.join(input_dirpath, gbw_filename)
    shutil.copy(gbw_path, new_gbw_path)

    # Load and modify input
    input_obj.directory = input_dirpath
    input_obj.basename = input_basename
    input_obj.load_file(input_path)

    # Add MORead keyword if not present
    if 'MORead' not in input_obj.keywords and 'MOREAD' not in input_obj.keywords:
        input_obj.keywords.append('MORead')

    # Add %moinp string pointing to the gbw file
    moinp_string = f'%moinp "{gbw_filename}"'
    # Remove any existing %moinp lines
    input_obj.strings = [s for s in input_obj.strings if not s.strip().lower().startswith('%moinp')]
    input_obj.strings.append(moinp_string)

    input_obj.write_file()
