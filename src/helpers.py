import json
import copy

import input_generator
import job_harness
import file_parser

def merge_dicts(_d1, _d2):
    d1 = copy.deepcopy(_d1)
    d2 = copy.deepcopy(_d2)
    """Merge two dictionaries, overwriting string, number, and bool values,
    and combining nested dictionary and list objects"""
    merged = {**d1}  # Start with a copy of the first dictionary
    
    for key, value in d2.items():
        if key in merged:
            # Check types and overwrite only for str, int, float, bool
            if isinstance(merged[key], (str, int, float, bool)):
                merged[key] = value  # Overwrite with the value from d2
            elif isinstance(merged[key], list):
                if isinstance(value,list):
                    merged[key].extend(value)
                else:
                    megred[key].append(value)
            elif isinstance(merged[key],dict):
                if isinstance(value,dict):
                    merged[key] = merge_dicts(merged[key],value)
                else:
                    raise ValueError('Tried to mix dict and non-dict objects')
        else:
            merged[key] = value  # Add new key-value pair from d2

    return merged


def create_input_builder(program,**kwargs):
    if program.lower() == 'orca':
        return input_generator.ORCAInputBuilder()
    elif program.lower() == 'gaussian':
        return input_generator.GaussianInputBuilder()
    elif program.lower() == 'crest':
        return input_generator.CRESTInputBuilder()
    elif program.lower() == 'xtb':
        return input_generator.xTBInputBuilder()
    elif program.lower() == 'pyaroma':
        return input_generator.pyAromaInputBuilder()
    else:
        raise ValueError('unsupported program')


def create_job_harness(program,**kwargs):
    if program.lower() == 'gaussian':
        return job_harness.GaussianHarness()
    elif program.lower() == 'orca':
        return job_harness.ORCAHarness()
    elif program.lower() == 'crest':
        return job_harness.CRESTHarness()
    elif program.lower() == 'xtb':
        return job_harness.xTBHarness()
    elif program.lower() == 'pyaroma':
        return job_harness.pyAromaHarness()



#we have this very silly looking function in case we ever want to change
#the format of config files
def load_config_from_file(config_file):
    with open(config_file,'r') as f:
        return json.load(f)
