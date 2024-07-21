import PIPELINING.shell_macros.job_file_editor as cg
import data_cruncher as dc
import os
import shutil
import pandas as pd

def get_file_conditions(directory):
    '''
    This function gets the file conditions
    '''
    # Get the file names

    conds = dc.df_from_directory(dir_path,'ORCAmeta.rules','.out','slurm')
        
    conds = conds[conds['completion_success'] == False]
            
    return conds



def make_restart_directory(top_directory, restart_directory, conds):
    '''
    This function makes a restart directory and copies directories from the top directory
    '''
    os.makedirs(restart_directory, exist_ok=True)
    for root, dirs, files in os.walk(top_directory):
        for dir in dirs:
            if dir in conds.index:
                # Define the source and destination directory paths
                source_dir = os.path.join(root, dir)
                destination_dir = os.path.join(restart_directory, dir)
                
                # Copy the directory
                shutil.copytree(source_dir, destination_dir)
                        



def change_restart_sbatch_files(restart_directory):
    '''
    This function changes the sbatch files in the restart directory
    '''
    for root, dirs, files in os.walk(restart_directory):
        for file in files:
            if file.endswith('.sh'):
                # Define the file path
                file_path = os.path.join(root, file)
                # Change the sbatch file
                cg.change_sbatch_file(file_path)
                        
                        
                        
                        
def fix_restart_r2scan3c_files(restart_directory):
    '''
    This function fixes the r2scan3c files in the restart directory
    '''
    for root, dirs, files in os.walk(restart_directory):
        for file in files:
            if 'r2scan3c' in file and file.endswith('.inp'):
                # Define the file path
                file_path = os.path.join(root, file)
                # Fix the r2scan3c file
                cg.fix_r2scan3c_file(file_path)
                            

def fix_geom_successes(restart_directory,conds):
    '''
    This function fixes the geom success files in the restart directory
    '''
    for root, dirs, files in os.walk(restart_directory):
        for dir in dirs:
            if conds.loc[dir,'geometry_success'] is True:
                path = os.path.join(root,dir)
                for subroot, subdirs, files in os.walk(path):
                    for file in files:
                        if file.endswith('.inp'):
                            # Define the file path
                            file_path = os.path.join(subroot, file)
                            # Get the coordinates
                            coordinates = cg.get_coordinates(file_path.replace('.inp', '.out'))
                            # Replace the geometry
                            cg.replace_geometry(file_path, coordinates)
                            cg.fix_geom_success(file_path)
                        
                        
                        
                            
def fix_scf_fails(restart_directory):
    '''
    This function fixes the scf fail files in the restart directory
    '''
    for root, dirs, files in os.walk(restart_directory):
        for dir in dirs:
            if 'scf' in dir:
                for subroot, subdirs, files in os.walk(dir):
                    for file in files:
                        if file.endswith('.inp'):
                            # Define the file path
                            file_path = os.path.join(subroot, file)
                            # Get the coordinates
                            coordinates = cg.get_coordinates(file_path.replace('.inp', '.out'))
                            # Fix the scf fail file
                            cg.replace_geometry(file_path, coordinates)
                            cg.fix_scf_fail(file_path)
                    
                    
                            
if __name__ == "__main__":
    top_directory = os.getcwd()
    restart_directory = 'restart'
    conds = get_file_conditions(top_directory)
    make_restart_directory(top_directory, restart_directory, conds)
    change_restart_sbatch_files(restart_directory)
    fix_restart_r2scan3c_files(restart_directory)
    fix_geom_successes(restart_directory,conds)
    fix_scf_fails(restart_directory)