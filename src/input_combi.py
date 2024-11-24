import helpers
import input_generator
import itertools
import os
import re
import copy
import pandas as pd


#iterate inputs has some new rules
#some of the dicts in the list_of_dicts..
#will be flags.
#this needs to handle this

#so currently, it would trace a path through these keys...

#idea being, iterate_inputs(*sort_flags(lodod))

FLAGS = ['!directories']

def delete_old_tmp_files(root_directory):
    ledger_path = os.path.join(root_directory,'__ledger__.csv')
    if not os.path.exists(ledger_path):
        raise ValueError('tried to delete old .tmp files without ledger')
    ledger = pd.read_csv(ledger_path,sep='|')
    failed_mask = ledger['job_status'] == 'failed'
    for i, row in ledger.loc[failed_mask].iterrows():
        # print(row)
        job_dir = row['job_directory']
        files = os.listdir(job_dir)
        for file in files:
            path = os.path.join(job_dir,file)
            basename = os.path.basename(file)
            if re.search('\.tmp',basename):
                # print(path) #dry run with print before we remove
                os.remove(path)
            if re.search('\.rwf',basename):
                os.remove(path)
                
                

def do_everything(root_directory,run_settings,*args):
    """
    accepts any number of lists of dicts of settings to combine
    """
    for config_list in args:
        configs,flags = sort_flags(config_list)
        paths = iterate_inputs(configs,flags)
        write_input_array(paths,root_directory)
        print('editing batchfile')
        write_batchfile(paths,root_directory,'batchfile.csv')
    if run_settings is not None:
        print('creating script for run')
        write_own_script(run_settings,root_directory)

def write_own_script(run_settings,root_dir):
    br_builder = input_files.BatchRunnerInputBuilder()
    br_builder.change_params({
        **run_settings,
        'write_directory' : root_dir,
        })
    #TODO: clean this up some
    job = br_builder.build()
    job.sh.directory = job.directory
    print(f'writing file to {job.sh.directory}')
    job.sh.write_file()

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
    for key_path in all_paths:
        config_dict = {}
        name_list = []
        for index, key, flags in zip(range(0,len(key_path)),key_path,flag_array):
            name_list.append(key)
            if '!directories' in flags:
                #TODO: fix weird error that happens here
                config_dict['write_directory'] = os.path.join(
                    config_dict.get('write_directory',''),
                    '_'.join(name_list)
                )
                name_list = []
            config_dict = helpers.merge_dicts(config_dict,list_of_dict_of_dicts[index][key])
        name = '_'.join([name_frag for name_frag in name_list if name_frag])
        config_dict['job_basename'] = name
        print(config_dict.get('!xyz_file','IF I HAD ONE'))
        if config_dict.get('!xyz_file',None):#should avoid a lot of issues this way
            config_dict['xyz_file'] = config_dict['!xyz_file']
            #can't think of any example when we wouldn't want to do this
        if not config_dict.get('write_directory',None):
            print("No write directory provided")
            config_dict['write_directory'] = ''#have to see how this is handled
        all_configs.append(config_dict)
    return all_configs


def write_input_array(_configs,root_directory,**kwargs):
    if type(_configs) is dict:
        configs = copy.deepcopy(_configs.values())
    else:
        configs = copy.deepcopy(_configs)
    #for modifying the ledger as needed    
    ledger_filename = kwargs.get('ledger','__ledger__.csv')
    ledger_path = os.path.join(root_directory,ledger_filename)
    ledger = None
    if os.path.exists(ledger_path):
        ledger = pd.read_csv(ledger_path,sep='|')
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
        elif config['program'].lower() == 'pyaroma':
            inp = input_files.pyAromaInputBuilder()
        else:
            raise ValueError('unsupported program')
        config['write_directory'] = os.path.join(root_directory,config['write_directory'],config['job_basename'])
        inp.change_params(config)
        job = inp.build()
        
        force_overwrite = config.get('!overwrite',False)
        
        if force_overwrite == 'not_succeeded' or force_overwrite is True: #really, failed and not started
            job_succeeded = False
            if ledger is not None:    
                identify_mask = (ledger['job_basename'] == config['job_basename']) & (ledger['job_directory'] == config['write_directory'])
                if identify_mask.sum() > 1:
                    raise ValueError("Multiple jobs found with the same name.")

                filtered_status = ledger.loc[identify_mask,'job_status']                    
                if not filtered_status.empty:
                    if ledger.loc[identify_mask,'job_status'].iloc[0] in ['succeeded','running','pending']:
                        print("JOB ALREADY SUCCEEDED or RUNNING or PENDING")
                        job_succeeded = True
                    else:
                        print("job failed")
                        job_succeeded = False
                else:
                    print("job not found")
                    job_succeeded = False
                
                    
                if not job_succeeded:
                    ledger.loc[identify_mask, 'job_id'] = f"{-1}"
                    ledger.loc[identify_mask, 'job_status'] = 'not_started'
                    ledger.loc[identify_mask, 'coords_from'] = config.get('!coords_from',None)
                    ledger.loc[identify_mask,'xyz_filename'] = config.get('!xyz_file',None)
             
            if not job_succeeded:
                job.create_directory(force=True)

        
        elif force_overwrite == 'all':
            job_succeeded = False
            if ledger is not None:    
                identify_mask = (ledger['job_basename'] == config['job_basename']) & (ledger['job_directory'] == config['write_directory'])
                
                if identify_mask.sum() > 1:
                    raise ValueError("Multiple jobs found with the same name.")
            
                ledger.loc[identify_mask, 'job_id'] = f"{-1}"
                ledger.loc[identify_mask, 'job_status'] = 'not_started'
                ledger.loc[identify_mask, 'coords_from'] = config.get('!coords_from',None)
                ledger.loc[identify_mask,'xyz_filename'] = config.get('!xyz_file',None)
                
            job.create_directory(force=True)
             
        else:
            try:
                job.create_directory(force=False)
            except:
                #print(f"Job Directory NOT WRITTEN at {job.directory}")
                #commenting this out; it was used for debugging but now just makes a lot of noise.
                pass
            
        del job
        del inp
    if ledger is not None:
        ledger.to_csv(ledger_path,sep='|',index=False)
    return
    
#TODO
#really need to overwrite ledger with not_started when doing this...


def write_batchfile(_configs,root_dir,filename):
    path = os.path.join(root_dir,filename)
    existed = os.path.exists(path)
    append_or_write = 'w'
    written_lines = {} #store every line as a key in a dict, True if written doesn't exist if not #we can just use a set for this, why do we use a dict?
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
