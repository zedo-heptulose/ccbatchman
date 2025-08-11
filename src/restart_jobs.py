import cc_workflow_generator as ccwg
import subprocess
import progcheck
import os
import re
import file_parser
import json
import input_generator

def run_command(command, workdir):
    result = subprocess.run(command, shell=True, cwd=workdir,
                             capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode





def create_check_cause(old=False,debug=False):
    
    def check_cause(row):
        job_status = row['job_status']
        if job_status == 'succeeded':
            return None
            
        directory = row['job_directory']
        
        if old:
            directory += '_history_0' ## BAD HOTFIX, should really choose highest history no.
            if not os.path.exists(directory):
                return None
        
        dirs = os.listdir(directory)
        id = row['job_id']
        
        # Get latest SLURM output file
        slurm_outputs = [file for file in dirs if 'slurm' in file]
        slurm_numbers = [int(re.search(r'\d+', slurm_output).group(0)) for slurm_output in slurm_outputs]
        
        if old:
            id = max(slurm_numbers)
            if debug:
                print('--------')
                print(id)
                print('--------')
        
        if not id in slurm_numbers:
            outcome = 'NO_SLURM_OUTPUT'
        else:
            # Check SLURM job status
            result = subprocess.run(f'seff {id}', shell=True, capture_output=True, text=True)
            status_line = result.stdout.split('\n')[3] if len(result.stdout.split('\n')) > 3 else ""
            
            if 'COMPLETED' in status_line:
                outcome = 'FAILED' 
            elif 'NODE_FAIL' in status_line:
                outcome = 'NODE_FAIL'
            elif 'TIMEOUT' in status_line:
                outcome = 'TIMEOUT'
            elif 'OUT_OF_MEMORY' in status_line:
                outcome = 'OUT_OF_MEMORY'
            elif 'RUNNING' in status_line:
                outcome = None
                return outcome
            else:
                outcome = 'OTHER'
                if debug:
                    print(status_line)
    
        if outcome != 'FAILED':
            return outcome
    
        base_path = os.path.join(directory, row['theory'])
        
        # # Try to find and parse output file
        
        json_path = f"{base_path}.json"
        # if not os.path.exists(json_path):
        out_path = base_path + '.out'
        if os.path.exists(out_path):
            # ORCA output
            output = file_parser.extract_data(
                out_path,                 '/gpfs/home/gdb20/code/ccbatchman/config/file_parser_config/orca_rules.dat'
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
                outcome = 'could not parse'
                return outcome
        
        with open(json_path, 'w') as json_file:
            json.dump(output, json_file, indent=6)
            
        with open(json_path, 'r') as json_file:
            run_data = json.load(json_file)
        
        if run_data.get('normal_exit_opt_freq_2',None) is not None and not run_data.get('normal_exit_opt_freq_2',None):
            if debug:
                print('normal_exit opt freq...')
                print(run_data.get('normal_exit_opt_freq_2',True))
                print(row['molecule'])
                print(run_data)
        
        
        # Categorize specific error types
        if run_data.get('imaginary_frequencies', False):
            outcome = 'imaginary_freq'
        elif run_data.get('opt_fail', False):
            outcome = 'opt_maxcycle'
        elif run_data.get('scf_fail', False):
            outcome = 'scf_fail'
        elif run_data.get('bad_internals', False):
            outcome = 'bad_internals'
        elif not run_data.get('normal_exit_opt_freq_2',True):
            outcome = 'bad_stationary_point'
    
        return outcome
    
    return check_cause










def get_ledger(root,directory,ledger,debug=False):
    working_path = os.path.join(root,directory)
    ledger = progcheck.load_ledger(working_path,ledger)
    ledger = ledger.drop(['xyz_filename','coords_from','job_basename'],axis=1)
    # ledger['root_directory'] = ledger['job_directory'].apply(lambda x: os.path.dirname(os.path.dirname(x)))
    ledger['molecule'] = ledger['job_directory'].apply(lambda x: os.path.basename(os.path.dirname(x)))
    ledger['theory'] = ledger['job_directory'].apply(lambda x: os.path.basename(x))
    ledger['previous_fail_cause'] = ledger.apply(create_check_cause(old=True,debug=debug),axis=1)
    ledger['fail_cause'] = ledger.apply(create_check_cause(debug=debug),axis=1)
    ledger = ledger[['molecule','theory','program','job_status','fail_cause','previous_fail_cause','job_id','job_directory']]
    # ledger = ledger.drop(['job_directory'],axis=1)
    return ledger




def create_new_job(config,program): 
    # need to get the appropriate program input generator. ORCA is fine for now.
    # print('--------------------')
    # print('in create_new_job')
    # print('config:')
    # print(json.dumps(config,indent=6))
    # print('---------------------')
    if program.lower() == 'orca':
        gen = input_generator.ORCAInputBuilder()
        gen.change_params(config)
        # gen.debug=True
        inp = gen.build_input()
        inp.cleanup()
        inp.write_file()
        sh = gen.build_submit_script()
        sh.write_file()
    elif program.lower() == 'gaussian':
        gen = input_generator.GaussianInputBuilder()
        gen.change_params(config)
        # gen.debug=True
        inp = gen.build_input()
        inp.cleanup()
        inp.write_file()
        sh = gen.build_submit_script()
        sh.write_file()



def rewrite_job(row,new_settings,ledger_path):
    # making a copy of the directory for bookkeeping
    job_id = row['job_id']
    molecule_directory = os.path.dirname(row['job_directory'])
    dirs = [dir for dir in os.listdir(molecule_directory)]
    i = 0
    while f"{row['theory']}_history_{i}" in dirs:
        i += 1
    command = f"cp -r {row['theory']} {row['theory']}_history_{i}"
    print(command)
    run_command(command,molecule_directory)
    
    if row['program'].lower() == 'orca':
        input_extension = '.inp'
        output_extension = '.out'
    elif row['program'].lower() == 'gaussian':
        input_extension = '.gjf'
        output_extension = '.log'
    elif row['program'].lower() == 'crest':
        print(f"cannot restart {row['program']} job yet, continuing")
        return
    # else:
        # raise ValueError('only implemented for ORCA and Gaussian (and will pass for CREST)')
    base_path = os.path.join(row['job_directory'],row['theory'])
    os.remove(base_path+input_extension)
    os.remove(base_path+output_extension)
    os.remove(base_path+'.json')
    os.remove(base_path+'.sh')
    os.remove(os.path.join(row['job_directory'],'run_info.json'))
    for file in os.listdir(row['job_directory']):
        if file.startswith('slurm') and file.endswith('.out'):
            print(f'removing slurm output file: {file}')
            os.remove(os.path.join(row['job_directory'],file))
    
    
    json_path = os.path.join(row['job_directory'],'job_config.json')
    with open (json_path,'r') as json_file:
        config = json.load(json_file)
    
    config.update(new_settings)

    # 07-17-2025 bandaid fix for dict merging.
    for key,value in new_settings.items():
        if value is None:
            config[key] = None
            
    # add directory manipulation stuff to save a copy.
    create_new_job(config,row['program'])

    # add ledger updating stuff 
    # (just needs to find row with job id, and update it in place in the dataframe)
    # this code already lives in the batch manager. Steal it from there
    # but which ledger name to use?
    run_root = os.path.dirname(ledger_path)
    ledger_basename = os.path.basename(ledger_path)
    ledger = progcheck.load_ledger(run_root,ledger_basename)
    index_list = ledger[ledger['job_id'] == job_id].index.tolist()
    if len(index_list) != 1:
        raise ValueError('multiple or zero rows in ledger with same SLURM ID')
    ledger_index = index_list[0]
    ledger.loc[ledger_index,'job_status'] = 'not_started' #like it never even happened...
    ledger.loc[ledger_index,'job_id'] = -1 #like it never even happened...
    ledger.to_csv(ledger_path,sep='|',index=False)
    return


def create_handle_fail(ledger_path):
    print('creating handle_fail function')
    def handle_fail(row):
        # print('----------------------')
        # print('in handle_fail(row)')
        # print('row:')
        # print(row)
        # print('----------------------')
        
        is_orca = (row['program'].lower() == 'orca')
        is_gaussian = (row['program'].lower() == 'gaussian')
        is_crest = (row['program'].lower() == 'crest')
        is_imaginary_freq = (row['fail_cause'] == 'imaginary_freq')
        is_bad_stationary_point = (row['fail_cause'] == 'bad_stationary_point' )
        is_node_fail = (row['fail_cause'] == 'NODE_FAIL')
        is_timeout = (row['fail_cause'] == 'TIMEOUT')
        is_other = (row['fail_cause'] == 'OTHER')

        directory = row['job_directory']
        basename = row['theory']
        old_config_filename = os.path.join(directory,'job_config.json')
        with open(old_config_filename,'r') as old_config_file:
            old_config = json.load(old_config_file)
        
        # print('-------------------------------')
        # print(f"is_orca | {(row['program'].lower() == 'orca')}")
        # print(f"is_gaussian | {(row['program'].lower() == 'gaussian')}")
        # print(f"is_imaginary_freq = {(row['fail_cause'] == 'imaginary_freq')}")
        # print(f"is_bad_stationary_point = {(row['fail_cause'] == 'bad_stationary_point' )}")
        # print(f"is_node_fail = {(row['fail_cause'] == 'NODE_FAIL')}")
        # print(f"is_timeout = {(row['fail_cause'] == 'TIMEOUT')}")

        if is_crest:
            return row
        
        is_failed = (row['job_status'].lower() == 'failed') 
        if not is_failed:
            return row
            
        if is_orca and is_imaginary_freq:
            print('ORCA imaginary frequency')
            override_configs = {
            'xyz_file' : f"{row['theory']}.xyz",
            }
            # CHECK COORD REPLACEMENT ISSUE
            rewrite_job(row,override_configs,ledger_path)
        elif is_gaussian and is_imaginary_freq:
            print('Gaussian imaginary frequency')
            override_configs = {
            'xyz_file' : None,
            # CHECK COORD REPLACEMENT ISSUE
            'other_keywords' : [
                    'geom=checkpoint',
                    'int=ultrafine nosymm'
                ],
            }
            rewrite_job(row,override_configs,ledger_path)
        elif is_gaussian and is_bad_stationary_point: 
            print('Gaussian bad stationary point')
            override_configs = {
            'xyz_file' : None,
            'run_type' : old_config['run_type'].lower().replace('opt','opt=readfc'),
            'broken_symmetry' : False, # currently, this corresponds to GUESS=MIX in Gaussian, need to get rid of guess setting
            # CHECK COORD REPLACEMENT ISSUE
            'other_keywords' : [
                    'geom=allcheck guess=read',
                    'int=ultrafine nosymm',
                ],
            }
            rewrite_job(row,override_configs,ledger_path)
            
        # bad hack solution, should be getting old settings and using whatever's there
        # can't do this multiple times
        elif is_node_fail:
            print('NODE FAIL')
            override_configs = {
                'num_cores' : 10,    
            }
            rewrite_job(row,override_configs,ledger_path)
        elif is_timeout:
            print('TIMEOUT')
            override_configs = {
                'runtime' : '5-00:00:00',
            }
            rewrite_job(row,override_configs,ledger_path)
        
        return row
    return handle_fail



def cartesian_restart(ledger_path):
    print('creating handle_fail function')
    def handle_fail(row):
        print(row['job_directory'])
        is_orca = (row['program'].lower() == 'orca')
        is_gaussian = (row['program'].lower() == 'gaussian')
        is_failed = (row['job_status'] == 'failed')
        is_imaginary_freq = (row['fail_cause'] == 'imaginary_freq')
        is_bad_stationary_point = (row['fail_cause'] == 'bad_stationary_point' )
        
        directory = row['job_directory']
        basename = row['theory']
        old_config_filename = os.path.join(directory,'job_config.json')
        with open(old_config_filename,'r') as old_config_file:
            old_config = json.load(old_config_file)
    
        
        if is_orca and is_failed:
            print('ORCA imaginary frequency')
            override_configs = {
            'run_type': "COPT FREQ",
            }
            rewrite_job(row,override_configs,ledger_path)
            
        elif is_gaussian and is_failed and is_imaginary_freq:
            print('Gaussian imaginary frequency')
            override_configs = {
                'run_type': "OPT=Tight FREQ",
            }
            rewrite_job(row,override_configs,ledger_path)
        
        return row
    return handle_fail








def kill_running_job(row):
    job_id = row['job_id']
    command = f'scancel {job_id}'
    run_command(command,'.')
    print(command)
    return row



def restart_routine(ledger_path):
    root = os.path.dirname(os.path.dirname(ledger_path))
    directory = os.path.basename(os.path.dirname(ledger_path))
    ledger_filename = os.path.basename(ledger_path)
    ledger =get_ledger(root,directory,ledger_filename)
# ledger.to_csv('perfluoropropane_2_ledger0.csv')
    ledger.apply(create_handle_fail(ledger_path),axis=1)
    