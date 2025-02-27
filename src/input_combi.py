import helpers
import input_generator
import job_harness
import itertools
import os
import re
import copy
import pandas as pd
import json


FLAGS = ['!directories']

def delete_old_tmp_files(root_directory):
    ledger_path = os.path.join(root_directory,'__ledger__.csv')
    if not os.path.exists(ledger_path):
        raise ValueError('tried to delete old .tmp files without ledger')
    ledger = pd.read_csv(ledger_path,sep='|')
    failed_mask = ledger['job_status'] == 'failed'
    for i, row in ledger.loc[failed_mask].iterrows():
        job_dir = row['job_directory']
        files = os.listdir(job_dir)
        for file in files:
            path = os.path.join(job_dir,file)
            basename = os.path.basename(file)
            if re.search(r'\.tmp',basename):
                os.remove(path)
            if re.search(r'\.rwf',basename):
                os.remove(path)
                
                

def do_everything(root_directory,run_settings,*args,**kwargs):
    """
    accepts any number of lists of dicts of settings to combine
    """
    for config_list in args:
        configs,flags = sort_flags(config_list)
        paths = iterate_inputs(configs,flags)
        ledger_filename = run_settings.get('ledger_filename','__ledger__.csv')
        write_input_array(paths,root_directory,ledger=ledger_filename,**kwargs)
        print('editing batchfile')
        batchfile_name = run_settings.get('input_file','batchfile.csv')
        write_batchfile(paths,root_directory,batchfile_name)
    if run_settings is not None:
        print('creating script for run')
        write_own_script(run_settings,root_directory)

def write_own_script(run_settings,root_dir):
    br_builder = input_generator.BatchRunnerInputBuilder()
    br_builder.change_params({
        **run_settings,
        'write_directory' : root_dir,
        })
    #TODO: clean this up some
    job = br_builder.build()
    job.sh.directory = job.directory
    #print(f'writing file to {job.sh.directory}')
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

def iterate_inputs(list_of_dict_of_dicts,flag_array,**kwargs):
    '''
    Given the list of nested dicts we use to define settings,
    traces every path through this list of dicts and returns an array of these paths.
    Also configures write directories and basenames.
    Use kwarg use_names = True to avoid this behavior and use the paths from config.
    '''
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
            current_config = list_of_dict_of_dicts[index][key].copy()
            if current_config.get('write_directory',None):
                del current_config['write_directory']
                #this prevents mishaps with accidentally including this parameter in dicts used by do_everything
                #do not delete this, make a new keyword arg if we 
                #need to change this behavior
            config_dict = helpers.merge_dicts(config_dict,current_config)
        name = '_'.join([name_frag for name_frag in name_list if name_frag])
        config_dict['write_directory'] = os.path.join(config_dict.get('write_directory',''),name)
        #this should fix the logic? 
        #we don't add to config_dict unless there's the !directories flag...
        if '/' in name:
            print('new thing I added')
            print(name)
            basename = os.path.basename(name)
            config_dict['job_basename'] = basename
            print(config_dict['job_basename'])
        else:
            config_dict['job_basename'] = name
        #print(config_dict.get('!xyz_file','IF I HAD ONE'))
        if config_dict.get('!xyz_file',None):#should avoid a lot of issues this way
            config_dict['xyz_file'] = config_dict['!xyz_file']
            #can't think of any example when we wouldn't want to do this
        if not config_dict.get('write_directory',None):
            #print("No write directory provided")
            config_dict['write_directory'] = '' #have to see how this is handled
        all_configs.append(config_dict)
    return all_configs


def write_input_array(_configs,root_directory,**kwargs):
    if type(_configs) is dict:
        configs = copy.deepcopy(_configs.values())
    else:
        configs = copy.deepcopy(_configs)
    
    for config in configs:
        config['write_directory'] = os.path.join(root_directory,config['write_directory'])
        inp = helpers.create_input_builder(config['program'])
        inp.change_params(config)
        job = inp.build()
        config_path = os.path.join(job.directory,'job_config.json')
        force_overwrite = config.get('!overwrite',False)
        overwrite_directory = False
        overwrite_input = False
        job_succeeded = True

        #check for status of job
        job_reader = helpers.create_job_harness(config['program'])
        job_reader.directory = config['write_directory'] 
        job_reader.job_name = config['job_basename'] 

        
        if not os.path.exists(config['write_directory']):
            job_succeeded = False #not that it should matter in this case
        else:
            job_reader.restart = True  #does this matter?
            job_reader.update_status()
            job_reader.write_json()
    
            if job_reader.status in ['succeeded','running','pending']:
                job_succeeded = True
            else:
                job_succeeded = False

        # determine whether to overwrite directory
        if force_overwrite == True or force_overwrite == 'not_succeeded':
            if job_succeeded:
                overwrite_directory = False
            else:
                overwrite_directory = True
            
        elif force_overwrite == 'all':
            overwrite_directory = True

        elif force_overwrite == 'input_files_only':
            if job_succeeded:
                overwrite_input = False
            else:
                overwrite_input = True

        #act on overwriting directory or inputs
        if overwrite_directory:
            job.create_directory(overwrite_directory=True)
            with open (config_path,'w') as json_file:
                json.dump(config,json_file,indent=6)
    

        elif overwrite_input:
            job.create_directory(overwrite_input=True)
            with open (config_path,'w') as json_file:
                json.dump(config,json_file,indent=6)
            out_fn = job_reader.job_name + '.out'
            new_out_fn = job_reader.job_name + '_old.out'
            out_path = os.path.join(job_reader.directory,out_fn)
            new_out_path = os.path.join(job_reader.directory,new_out_fn)
            if os.path.exists(out_path):
                os.rename(out_path,new_out_path)
                
            log_fn = job_reader.job_name + '.log'
            new_log_fn = job_reader.job_name + '_old.log'
            log_path = os.path.join(job_reader.directory,log_fn)
            new_log_path = os.path.join(job_reader.directory,new_log_fn)
            if os.path.exists(log_path):
                os.rename(log_path,new_log_path)
     
        else:
            try:
                job.create_directory()
                with open (config_path,'w') as json_file:
                    json.dump(config,json_file,indent=6)
            except:
                pass

        #check if we have a ledger before the next part
        ledger_filename = kwargs.get('ledger','__ledger__.csv')
        ledger_path = os.path.join(root_directory,ledger_filename)
        ledger = None

        if os.path.exists(ledger_path):
            ledger = pd.read_csv(ledger_path,sep='|')
            print(f'ledger exists: {ledger_path}')
        #if we have a ledger, update it
        if (overwrite_directory or overwrite_input) and ledger is not None:
            identify_mask = (ledger['job_basename'] == config['job_basename']) &\
                            (ledger['job_directory'] == config['write_directory'])   
            
            if identify_mask.sum() > 1:
                raise ValueError("Multiple jobs found with the same name.")
            elif identify_mask.sum() == 0:
                print('nothing satisfies parameters')
                print(f"write/ directory: {config['write_directory']} | {ledger['job_basename']}")
                print(f"basename: {config['job_basename']} | {ledger['job_directory']}")
            else:
                ledger.loc[identify_mask, 'job_id'] = f"{-1}"
                ledger.loc[identify_mask, 'job_status'] = 'not_started'
                ledger.loc[identify_mask, 'coords_from'] = config.get('!coords_from',None)
                ledger.loc[identify_mask,'xyz_filename'] = config.get('!xyz_file',None)


            ledger.to_csv(ledger_path,sep='|',index=False)


        if kwargs.get('force_write_config',False):
            with open (config_path,'w') as json_file:
                json.dump(config,json_file,indent=6)

    return

        




def write_batchfile(_configs,root_dir,filename):
    path = os.path.join(root_dir,filename)
    existed = os.path.exists(path)
    append_or_write = 'w'
    written_lines = {} 
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
            print("in write_batchfile()")
            print(config['write_directory'])
            print(config['job_basename'])
            job_directory = config['write_directory']
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
