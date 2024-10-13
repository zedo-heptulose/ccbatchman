import helpers
import input_files
import itertools
import os

def iterate_inputs(list_of_dict_of_dicts):
    all_paths = itertools.product(*[d.keys() for d in list_of_dict_of_dicts])
    all_configs = {}
    for key_path in all_paths:
        config_dict = {}
        name_list = []
        for index, key in enumerate(key_path):
            name_list.append(key)
            try:
                config_dict = helpers.merge_dicts(config_dict,list_of_dict_of_dicts[index][key])
            except:
                print(f"""
                warning: error for items:
                {config_dict}
                {list_of_dict_of_dicts[index][key]}
                """)
        name = '_'.join(name_list)
        config_dict['job_basename'] = name
        all_configs[name] = config_dict
    return all_configs

def add_global_config(_configs,global_config):
    if type(_configs) is dict:
        configs = {key : helpers.merge_dicts(global_config,value) for key,value in _configs.items()}
    elif type(_configs) is list:
        configs = [helpers.merge_dicts(global_config,value) for value in configs]
    return configs

def write_input_array(_configs):
    if type(_configs) is dict:
        configs = _configs.values()
    else:
        configs = _configs
    for config in configs:
        if config['program'].lower() == 'orca':
            inp = input_files.ORCAInputBuilder()
        elif config['program'].lower() == 'gaussian':
            inp = input_files.GaussianInputBuilder()
        elif config['program'].lower() == 'crest':
            inp = input_files.CRESTInputBuilder()
        else:
            raise ValueError('unsupported program')
        config['write_directory'] = os.path.join(config['write_directory'],config['job_basename'])
        inp.change_params(config)
        job = inp.build()
        job.create_directory()

def generate_batchfile(_configs,existing_batchfile=None):
    pass

