import helpers
import input_files
import itertools
import os
import copy


#iterate inputs has some new rules
#some of the dicts in the list_of_dicts..
#will be flags.
#this needs to handle this

#so currently, it would trace a path through these keys...

#idea being, iterate_inputs(*sort_flags(lodod))

FLAGS = ['!directories']

def do_everything(config_list,root_dir):
    """
    strings together the functions always used together
    """
    configs,flags = sort_flags(config_list)
    paths = iterate_inputs(configs,flags)
    write_input_array(paths,root_dir)
    write_batchfile(paths,root_dir,'batchfile.csv')

def xyz_files_from_directory(directory):
    molec_list = os.listdir(directory)
    molec_list = [mol for mol in molec_list if mol.endswith('.xyz')]
    molecule_dict = {}
    for xyz_filename in molec_list:
        basename = os.path.splitext(xyz_filename)[0]
        #print(basename)
        molecule_dict[basename] = {
            'xyz_directory' : os.path.abspath(directory),
            'xyz_file' : xyz_filename,
        }
    return molecule_dict

def sort_flags(list_of_dict_of_dicts):
    mod_list = copy.deepcopy(list_of_dict_of_dicts)
    flag_array = [] #list of lists
    for i, d in enumerate(list_of_dict_of_dicts):
        flag_array.append([])  
        for k, v in d.items():
            if k in FLAGS:
                del mod_list[i][k]
                if k == '!directories' and v:
                    flag_array[i].append(k)
                      
    return (mod_list,flag_array)

def iterate_inputs(list_of_dict_of_dicts,flag_array):
    all_paths = itertools.product(*[d.keys() for d in list_of_dict_of_dicts])
    all_configs = []
    #print("acknowledge meeee")
    for key_path in all_paths:
        config_dict = {}
        name_list = []
        #print(key_path)
        for index, key, flags in zip(range(0,len(key_path)),key_path,flag_array):
            #print("iterating")
            name_list.append(key)
            if '!directories' in flags:
                config_dict['write_directory'] = os.path.join(
                    config_dict.get('write_directory',''),
                    '_'.join(name_list)
                )
                name_list = []
            try:
                config_dict = helpers.merge_dicts(config_dict,list_of_dict_of_dicts[index][key])
                #print(f"CONFIG DICT: \n{config_dict}")
            except:
                print(f"""
                warning: error for items:
                {config_dict}
                {list_of_dict_of_dicts[index][key]}
                """)
        name = '_'.join([name_frag for name_frag in name_list if name_frag])
        config_dict['job_basename'] = name
        #print(f"\n\nat the end of it all: {config_dict}\n\n")
        all_configs.append(config_dict)
    return all_configs


def write_input_array(_configs,root_directory):
    if type(_configs) is dict:
        configs = copy.deepcopy(_configs.values())
    else:
        configs = copy.deepcopy(_configs)
    for config in configs:
        #print(f"CONFIG: \n{config}")
        if config['program'].lower() == 'orca':
            inp = input_files.ORCAInputBuilder()
        elif config['program'].lower() == 'gaussian':
            inp = input_files.GaussianInputBuilder()
        elif config['program'].lower() == 'crest':
            inp = input_files.CRESTInputBuilder()
        elif config['program'].lower() == 'xtb':
            inp = input_files.xTBInputBuilder()
        else:
            raise ValueError('unsupported program')
        config['write_directory'] = os.path.join(root_directory,config['write_directory'],config['job_basename'])
        inp.change_params(config)
        job = inp.build()
        #THIS NEEDS TO FAIL IF THE DIRECTORY ALREADY EXISTS
        try:
            job.create_directory()
        except:
            print(f"Job Directory NOT WRITTEN at {job.directory}")
        
        del job
        del inp

def write_batchfile(_configs,root_dir,filename):
    path = os.path.join(root_dir,filename)
    existed = os.path.exists(path)
    append_or_write = 'w'
    written_lines = {} #store every line as a key in a dict, True if written doesn't exist if not
    if existed:
        append_or_write = 'a'
        #
        with open(path,'r') as batchfile:
            lines = batchfile.readlines()
        for line in lines:
            written_lines[line] = True

    with open(path,append_or_write) as batchfile:
        if not existed:
            batchfile.write(
                f"root_directory={root_dir}\n"
            )
            batchfile.write(
                'job_directory|job_basename|program|pipe\n'
            )
        for config in _configs:
            job_basename = config['job_basename']
            #TODO: this must not redundantly inlcude root
            job_directory = os.path.join(config['write_directory'], config['job_basename'])
            program = config['program']
            coords_from = config.get('!coords_from',None)
            xyz_file = config.get('!xyz_file',None)
            pipe_string = ''
            if coords_from and xyz_file:
                pipe_string = f"coords{{{coords_from},{xyz_file}}}"
        
            line = f"{job_directory}|{job_basename}|{program}|{pipe_string}\n"

            #check that we haven't already written this
            if not written_lines.get(line,False):
                batchfile.write(line)
                written_lines[line] = True #mark this line as already written 