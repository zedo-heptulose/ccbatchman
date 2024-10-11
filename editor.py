import os
import shutil
import re
import input_files

def replace_xyz_file(input_filename,input_directory,xyz_filename,xyz_directory):
    if os.path.splitext(input_filename)[1] == '.inp':
        input_obj = input_files.ORCAInput()
    elif os.path.splitext(input_filename)[1] == '.gjf':
        input_obj = input_files.GaussianInput()
    else:
        raise ValueError('replace_xyz_file only works with ORCA (.inp) or GAUSSIAN (.gjf) input')
    
    xyz_path = os.path.join(xyz_directory,xyz_filename)
    destination = os.path.join(input_directory,xyz_filename)
    shutil.copy(xyz_path,destination)

    input_obj.load_file(input_filename,input_directory)
    input_obj.coordinates = []
    input_obj.xyzfile = xyz_filename
    input_obj.write_file()


