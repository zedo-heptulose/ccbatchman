import os
import pandas as pd
import numpy

import sys
path1 = '/gpfs/home/gdb20/code/ccbatchman/src/'
path2 = '/gpfs/home/gdb20/code/data-processor/'
paths = [path1,path2]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)
import input_combi
import helpers
import os
import re
import file_parser
import subprocess
import pandas as pd
import numpy
import matplotlib.pyplot as plt
import json

"""
Fail output
"""
from typing import Dict, List, Union, Optional, Tuple


def load_ledger(working_path: str,ledger_filename: str = '__ledger__.csv') -> pd.DataFrame:
    """
    Load ledger from disk for further analysis.

    Args:
        ledger_filename: filename of .csv file containing job information.
        working_path: directory ledger is located in

    Returns:
        DataFrame with ledger data for batch run
    """
    ledger = pd.read_csv(os.path.join(working_path,ledger_filename),sep='|')
    return ledger
    
    

def classify_failures(ledger: pd.DataFrame, working_path: str, verbose: bool = False) -> pd.DataFrame:
    """
    Analyze failed jobs and classify the type of failure.
    
    Args:
        ledger: DataFrame containing job information with at least 'job_status', 'job_directory', 'job_basename' columns
        working_path: Base path for all jobs
        verbose: Whether to print additional information during processing
    
    Returns:
        DataFrame with classified failure types
    """
    # fail_ledger = ledger[ledger['job_status'] == 'failed']
# 
    #fix bandaid changes!!!!
    fail_ledger = ledger
    new_rows = []
    
    for i, row in fail_ledger.iterrows():
        directory = row['job_directory']
        dirs = os.listdir(directory)
        job_basename = row['job_basename']
        
        # Get latest SLURM output file
        slurm_outputs = [file for file in dirs if 'slurm' in file]
        slurm_numbers = [int(re.search(r'\d+', slurm_output).group(0)) for slurm_output in slurm_outputs]
        slurm_number = max(slurm_numbers) if slurm_numbers else None
        
        if not slurm_number:
            outcome = 'NO_SLURM_OUTPUT'
        else:
            # Check SLURM job status
            result = subprocess.run(f'seff {slurm_number}', shell=True, capture_output=True, text=True)
            status_line = result.stdout.split('\n')[3] if len(result.stdout.split('\n')) > 3 else ""
            
            if 'COMPLETED' in status_line:
                outcome = 'FAILED' 
            elif 'NODE_FAIL' in status_line:
                outcome = 'NODE_FAIL'
            elif 'TIMEOUT' in status_line:
                outcome = 'TIMEOUT'
            elif 'OUT_OF_MEMORY' in status_line:
                outcome = 'OUT_OF_MEMORY'
            else:
                outcome = 'OTHER'
                if verbose:
                    print(status_line)
        
        # Extract identifiers
        identifier = directory.replace(working_path + '/', "", 1)
        molecule, method = identifier.split('/',1)
        
        new_row = pd.DataFrame({
            'full_path': [row['job_directory']],
            'identifier': [identifier],
            'system': [molecule],
            'method': [method],
            'outcome': [outcome],
        })
        
        new_rows.append(new_row)
    
    if new_rows:
        data = pd.concat(new_rows)
        data.index = range(0, len(data))
        return data
    else:
        return pd.DataFrame(columns=['full_path', 'identifier', 'system', 'method', 'outcome'])




def categorize_errors(data: pd.DataFrame, working_path: str) -> pd.DataFrame:
    """
    Further categorize computational chemistry errors in failed jobs.
    
    Args:
        data: DataFrame containing failed job information
        working_path: Base path for all jobs
        file_parser_module: Module containing extract_data function for parsing output files
        
    Returns:
        DataFrame with detailed error categories
    """
    new_data = data.copy()
    new_data.index = range(0, len(new_data))
    
    for i, row in new_data.iterrows():
        base_path = os.path.join(working_path, row['system'], row['method'], row['method'])
        
        # # Try to find and parse output file
        out_path = f"{base_path}.out"
        if os.path.exists(out_path):
            # ORCA output
            output = file_parser.extract_data(
                out_path, 
                '/gpfs/home/gdb20/code/ccbatchman/config/file_parser_config/orca_rules.dat'
            )
        else:
            # Gaussian output
            out_path = f"{base_path}.log"
            if os.path.exists(out_path):
                output = file_parser.extract_data(
                    out_path, 
                    '/gpfs/home/gdb20/code/ccbatchman/config/file_parser_config/gaussian_rules.dat'
                )
            else:
                # No output file found
                continue
        
        # # Save parsed data as JSON
        
        json_path = f"{base_path}.json"
        with open(json_path, 'w') as json_file:
            json.dump(output, json_file, indent=6)
            
        # Load JSON to analyze errors
    
        with open(json_path, 'r') as json_file:
            run_data = json.load(json_file)
    
        if run_data.get('normal_exit_opt_freq_2',None) is not None and not run_data.get('normal_exit_opt_freq_2',None):
            print('normal_exit opt freq...')
            print(run_data.get('normal_exit_opt_freq_2',True))
            print(row['system'])
            print(run_data)
        
        
        # Categorize specific error types
        if run_data.get('imaginary_frequencies', False):
            new_data.loc[i, 'outcome'] = 'imaginary_freq'
        elif run_data.get('opt_fail', False):
            new_data.loc[i, 'outcome'] = 'opt_maxcycle'
        elif run_data.get('scf_fail', False):
            new_data.loc[i, 'outcome'] = 'scf_fail'
        elif run_data.get('bad_internals', False):
            new_data.loc[i, 'outcome'] = 'bad_internals'
        elif not run_data.get('normal_exit_opt_freq_2',True):
            new_data.loc[i, 'outcome'] = 'bad_stationary_point'
        # delete this part later
        else:
            new_data.loc[i,'outcome'] = 'not_failed'

        new_data = new_data[(new_data['outcome'] != 'not_failed')]

    return new_data




def regenerate_jobs(data: pd.DataFrame, new_configs: Dict) -> Dict:
    """
    Generate new job configurations based on failed jobs with updated parameters.
    
    Args:
        data: DataFrame containing job information
        new_configs: Dictionary of configuration parameters to update
        
    Returns:
        Dictionary of job identifiers and their updated configurations
    """
    job_dict = {}
    
    for i, row in data.iterrows():
        config_path = os.path.join(row['full_path'], 'job_config.json')
        
        try:
            with open(config_path, 'r') as json_file:
                config = json.load(json_file)
                config.update(new_configs)
                job_dict[row['identifier']] = config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error processing {row['identifier']}: {e}")
            
    return job_dict



def get_outcome_statistics(data: pd.DataFrame) -> Dict:
    """
    Get statistics on job outcomes.
    
    Args:
        data: DataFrame containing job information
        
    Returns:
        Dictionary with statistics
    """
    outcomes = data['outcome'].value_counts().to_dict()
    total = len(data)
    
    stats = {
        'total_jobs': total,
        'outcome_counts': outcomes,
        'outcome_percentages': {k: (v/total)*100 for k, v in outcomes.items()}
    }
    
    return stats



def filter_by_fail(data: pd.DataFrame,fail_type: Union[str,List[str]]) -> pd.DataFrame:
    """
    Filter job outcomes by particular fail type.

    Args:
        data: DataFrame containing job information
        fail_type: string of type of fail to filter by

    Returns:
        DataFrame containing only fails of specified type
    """
    if isinstance(fail_type,str):
        return data[data['outcome'] == fail_type]
    elif isinstance(fail_type,list):
        data_filter = data['outcome'] == fail_type[0]
        if len(fail_type) > 1:
            for fail in fail_type[1:]:
                data_filter = data_filter | (data['outcome'] == fail)
        return data[data_filter]



def plot_outcomes(stats_dict, title='Computational Chemistry Job Outcomes', save_path=None, figsize=(10, 6)):
    """
    Plot job outcome statistics from the dictionary returned by get_outcome_statistics.
    
    Args:
        stats_dict: Dictionary with outcome statistics from get_outcome_statistics()
        title: Plot title
        save_path: Path to save the figure (optional)
        figsize: Figure size as (width, height) tuple
        
    Returns:
        matplotlib figure object
    """
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Get outcome counts
    outcomes = stats_dict['outcome_counts']
    
    # Define category ordering and colors
    system_failures = ['NODE_FAIL', 'TIMEOUT', 'OUT_OF_MEMORY']
    chem_failures = ['imaginary_freq', 'opt_maxcycle', 'scf_fail', 'bad_internals','bad_stationary_point']
    other_failures = ['FAILED', 'OTHER', 'NO_SLURM_OUTPUT']
    
    # Create ordered lists for plotting
    labels = []
    values = []
    colors = []
    
    # Add system failures (green)
    for key in system_failures:
        if key in outcomes:
            labels.append(key)
            values.append(outcomes[key])
            colors.append('#B3FFB3')  # Light green
    
    # Add chemistry failures (orange/red)
    for key in chem_failures:
        if key in outcomes:
            labels.append(key)
            values.append(outcomes[key])
            if key == 'imaginary_freq':
                colors.append('#FFCC99')  # Light orange
            else:
                colors.append('#FFB3B3')  # Light red
    
    # Add other failures (blue)
    for key in other_failures:
        if key in outcomes:
            labels.append(key)
            values.append(outcomes[key])
            colors.append('#B3D9FF')  # Light blue
    
    # Create the plot
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor('#f0f0f0')  # Figure background color
    ax.set_facecolor('#e0e0e0')  # Axes background color
    
    # Create the bar plot
    bars = ax.bar(labels, values, color=colors)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}',
                   xy=(bar.get_x() + bar.get_width() / 2, height),
                   xytext=(0, 3),  # 3 points vertical offset
                   textcoords="offset points",
                   ha='center', va='bottom')
    
    # Customize the plot
    ax.set_title(title)
    ax.set_xlabel('REASON')
    ax.set_ylabel('Number of Jobs')
    ax.set_ylim(0, max(values) + max(5, int(max(values) * 0.1)))  # Add some padding
    
    # Rotate x labels for better readability if needed
    plt.xticks(rotation=30, ha='right')
    
    plt.tight_layout()
    
    # Save the figure if a path is provided
    if save_path:
        plt.savefig(save_path)
    
    # return fig