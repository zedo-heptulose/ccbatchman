import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import data_routines
import parse_tree_builders
import parse_tree

import progcheck
import os
import re
import file_parser
import json
import input_generator
import restart_jobs
import data_routines

#most of these import statements are unnecessary.

def get_molecule_data(root,
                      molecules,
                      theory,
                      exclude=[],
                      debug=False,
                      already_seen=None,
                      replace_theories=None,
                      check_fail_cause=True, #turning this off might make it run faster
                      silent=False,
                     ):
    if already_seen == None:
        already_seen = set()
    molecule_list = []
    theory_list = []
    status_list = []
    electronic_energy_list = []
    energy_list = []
    enthalpy_list = []
    gibbs_list = []
    fail_cause_list = []
    
    original_theory = theory
    
    for molecule in molecules:
        if molecule in exclude:
            continue
        if molecule in already_seen:
            continue
        if replace_theories and molecule in replace_theories.keys():
            new_theory = replace_theories[molecule]
            if type(new_theory) is list or type(new_theory) is tuple:
                if len(new_theory) == 1:
                    if debug: print('1')
                    theory = new_theory[0]
                    basename = theory
                elif len(new_theory) == 2:
                    if debug: print('2')
                    theory = new_theory[0]
                    basename = new_theory[1]
                else:
                    raise ValueError(f'too many items ({len(new_theory)}) in new_theory argument in get_molecule_data')

            elif type(new_theory) is str:
                print('str')
                theory = new_theory
                basename = theory
            else:
                raise ValueError(f'invalid type ({type(new_theory)})for new_theory argument in get_molecule data')
            
        else:
            theory = original_theory
            basename = theory
        
        # json_file_path = os.path.join(root,molecule,theory,json_filename)
        # if not os.path.exists(json_file_path):
        # print(f"json path not found:")
        # print(f"{json_file_path}") 
        try:
            parseleaf = parse_tree.ParseLeaf()
            parseleaf.directory = os.path.join(root,molecule,theory)
            parseleaf.basename = basename
            parseleaf.parse_data()
            data = parseleaf.data
        except:
            if not silent:
                print(f"parseleaf raised an error for molecule {molecule}, returning no data")
            data = {}
        
        if os.path.exists(os.path.join(root,molecule,theory,'run_info.json')):# brutal hotfix, pls change
            with open(os.path.join(root,molecule,theory,'run_info.json'),'r') as run_info_file:
                run_info_data = json.load(run_info_file)
            status = run_info_data['status']

        else:
            status = 'ambiguous' # less brutal.

        if status != 'success' and check_fail_cause:
            directory = os.path.join(root,molecule,theory)
            fail_cause = restart_jobs.check_cause(status,directory,theory)
            fail_cause_list.append(fail_cause)
        else:
            fail_cause_list.append(None)
        
        if data.get('E_au',None):
            energy_list.append(data['E_au'])
            enthalpy_list.append(data['H_au'])
            gibbs_list.append(data['G_au'])
        else:
            energy_list.append(np.nan)
            enthalpy_list.append(np.nan)
            gibbs_list.append(np.nan)
            
        molecule_list.append(molecule)
        theory_list.append(theory)
        status_list.append(status)
        
        electronic_energy_list.append(data.get('E_el_au',None))
    
        
        already_seen.add(molecule)
        
    data_df = pd.DataFrame({
        'molecule' : molecule_list,
        'theory' : theory_list,
        'status' : status_list,
        'fail_cause' : fail_cause_list,
        'E_el_au' : electronic_energy_list,
        'E_au' : energy_list,
        'H_au' : enthalpy_list,
        'G_au' : gibbs_list,
    })
    return data_df


def get_reaction_molecule_data(
    root,reactions,theory,exclude=[],
    show_structures=False,
    debug=False,
    replace_theories=None,
    silent=False,
                     ):
    df_list = []
    already_seen = set() # pass by reference into get_reaction_molecule data
    for name, reaction in reactions.items():
        if debug:
            print(f"{name} | {reaction}")
        if show_structures:
            show_reaction_structures(root,reaction,theory)
        molecules = {**reaction['reactants'],**reaction['products']}.keys()
        data_df = get_molecule_data(root,molecules,theory,exclude,debug=debug,already_seen=already_seen,
                                            replace_theories=replace_theories,silent=silent)
        df_list.append(data_df)
    
    cumulative_df = pd.concat(df_list)
    cumulative_df.drop_duplicates(subset=['molecule','theory'], keep='first', inplace=True, ignore_index=True)
    cumulative_df.index = range(len(cumulative_df))
    return cumulative_df



def show_reaction_structures(root,reaction,theory):
    reactants = reaction['reactants']
    products = reaction['products']
    print('---------------------')
    print('reactants')
    for reactant in reactants.keys():
        try:
            path = os.path.join(root,reactant,theory,f'{theory}.xyz')
            print(f'{reactant} | {theory}')
            mol.Molecule(path).show()
        except:
            print(f'could not show: {reactant}')
    print('products')
    for product in products.keys():
        try:
            path = os.path.join(root,product,theory,f'{theory}.xyz')
            print(f'{product} | {theory}')
            mol.Molecule(path).show()
        except:
            print(f'could not show" {product}')
    print('----------------------')



def merge_data(data_1,data_2,force_merge = []):
    df_1 = data_1.copy()
    df_2 = data_2.copy()
    for i,row in df_1.iterrows():
        molecule = row['molecule']
        theory = row['theory']
        status = row['status']
        if status != 'succeeded' or molecule in force_merge:
            print(status)
            for j,row in df_2.iterrows():
                molecule_2 = row['molecule']
                theory_2 = row['theory']
                status_2 = row['status']
                if molecule == molecule_2: # what do we do with theory though?
                    if status_2 == 'succeeded':
                        df_1.loc[i] = df_2.loc[j]
                    elif status == 'nonexistent':
                        df_1.loc[i] = df_2.loc[j]
                    else:
                        print(f"{molecule} | failed for both {theory} and {theory_2}")
    return df_1


def replace_data(normal_data,constrained_data):
    df_n = normal_data.copy()
    df_c = constrained_data.copy()
    for i, row in df_n.iterrows():
        molecule = row['molecule']
        for j, row_2 in df_c.iterrows():
            molecule_2 = row_2['molecule']
            if molecule == molecule_2:
                df_n.loc[i] = df_c.loc[j]
    return df_n



def get_reaction_data(molecule_df,reactions,debug=False,show_au=False,conversions={'kcal/mol':627.51},
                     energy_types = ['G_au','H_au','E_au','E_el_au']):
    df_list = []
    for reaction_name, reaction in reactions.items():
        good_data = True
        reactants = reaction['reactants']
        products = reaction['products']
        raw_data = {}
        energy_data = {}
        for energy_type in energy_types:
            raw_data[energy_type] = 0
            
            for reactant, coefficient in reactants.items():
                if debug: print(reactant)
                if (molecule_df['molecule']==reactant).sum() == 0:
                    print(reactant)
                    print('oh no!')
                if not molecule_df[molecule_df['molecule']==reactant].iloc[0]['status'] == 'succeeded':
                    good_data = False
                if debug: print(molecule_df[molecule_df['molecule']==reactant].iloc[0])
                raw_data[energy_type] -= molecule_df[molecule_df['molecule']==reactant].iloc[0][energy_type] * coefficient
            
            for product, coefficient in products.items():
                if debug: print(product)
                if (molecule_df['molecule']==product).sum() == 0:
                    print(product)
                    print('oh no!')
                if debug: print(molecule_df[molecule_df['molecule']==product].iloc[0])
                raw_data[energy_type] += molecule_df[molecule_df['molecule']==product].iloc[0][energy_type] * coefficient
                if not molecule_df[molecule_df['molecule']==product].iloc[0]['status'] == 'succeeded':
                    good_data = False

        energy_data['reaction_name'] = [reaction_name]
        energy_data['all_succeeded'] = [good_data]
        
        for energy_type in energy_types:
            for unit, proportion in conversions.items():
                energy_data[f"Delta_{energy_type[:-3]}_{unit}"] = [raw_data[energy_type] * proportion]
            if show_au:
                energy_data[f"Delta_{energy_type}"] = [raw_data[energy_type]]
            
        energy_df = pd.DataFrame(energy_data)
        df_list.append(energy_df)
    data = pd.concat(df_list)
    data.index = range(len(data))
    return data





def merge_constrained_data(normal_data,constrained_data):
    df_n = normal_data.copy()
    df_c = constrained_data.copy()
    for i, row in df_n.iterrows():
        molecule = row['molecule']
        for j, row_2 in df_c.iterrows():
            molecule_2 = row_2['molecule']
            if molecule == molecule_2:
                df_n.loc[i] = df_c.loc[j]
    return df_n





def reaction_data_routine(reactions,root_dir,molecule_dirs,
                         backup_dirs=None,
                         replace_dirs=None,
                         replace_molecules=None,
                         force_merge=[],
                         replace_theories=None,
                         debug=False,
                         silent=False):
    '''
    general case for processing reaction data
    force_merge is a list of molecules in the backup directory that we
    treat as being in the replace directory
    '''
    reaction_names = reactions.keys()

    normal_dir = molecule_dirs[0]
    normal_theory = molecule_dirs[1]
    normal_root = os.path.join(root_dir,normal_dir)
    if debug:
        print('getting default molecule_data:')
    molecule_data = get_reaction_molecule_data(
        normal_root,
        reactions,
        normal_theory,
        debug=debug,
        replace_theories=replace_theories,
        silent=silent,
    )

    if backup_dirs:
        backup_dir = backup_dirs[0]
        backup_theory = backup_dirs[1]
        backup_root = os.path.join(root_dir,backup_dir)
        if debug:
            print('backup molecule_data:')
        backup_data = get_reaction_molecule_data(
            backup_root,
            reactions,
            backup_theory,
            debug=debug,
            silent=silent
        )
        molecule_data = merge_data(molecule_data,backup_data,force_merge)

    if replace_dirs:
        replace_dir = replace_dirs[0]
        replace_theory = replace_dirs[1]
        replace_root = os.path.join(root_dir,replace_dir)
        if debug:
            print('replacement molecule_data:')
        replacement_data = get_reaction_molecule_data(
            replace_root,
            reactions,
            replace_theory,
            debug=debug,
            silent=silent
        )
        replacement_data = replacement_data.dropna(thresh=4)
        molecule_data = replace_data(molecule_data,replacement_data)

    reaction_data = get_reaction_data(molecule_data,reactions)
    return reaction_data, molecule_data









def plot_enumerated_reactions(reaction_data,reactions=None,title='reactions',
                              ylim=None,
                              energy_type='Delta_G_kcal/mol', 
                              xlabel='',
                              ylabel='',
                              debug=False,
                              show=True,
                              filename=None,
                             ):
    # filter out common part without indexS
    name_roots = set()
    indices = set()
    if debug: print('iterating through reaction names, finding number')
    for name in reaction_data['reaction_name']:
        name_no_number= re.sub(r'\d+$','',name)
        name_roots.add(name_no_number)
        match = re.search(r'\d+$',name)
        if match:
            number = int(match.group(0))
            indices.add(number)
            # print(number)
        else:
            print('number not found?')
            print(name)
            print(name_no_number)
            
    indices = list(indices)
    indices.sort()
    name_roots = list(name_roots)
    
    fig, ax = plt.subplots()
    first = True
    
    for root in name_roots:
        failed_names = []
        failed_indices = []
        failed_energies = []
        enumerated_names = [root + str(i) for i in indices] 
        electronic_energies = []
        for j, name in enumerate(enumerated_names):
            if debug: print(f"{j} | {name}")
            row = find_row(reaction_data,name)
            if row is None:
                print(f"no row found by find_row()!")
                print(f"name: {name}")
                print(f"reaction_data:")
                print(reaction_data)
                print()
            energy = row[energy_type]
            electronic_energies.append(energy)
            if row['all_succeeded'] == False:
                failed_names.append(name)
                failed_energies.append(energy)
                failed_indices.append(indices[j])
        root = root.rstrip('_ \n')
        label = root
        if reactions:
            label = reactions.get(root,None)
            if not label:
                continue
        ax.plot(indices,electronic_energies,label=label)
        if len(failed_indices)  != 0:
            if first:
                failed_label = 'error in calculation'                
                ax.scatter(failed_indices,failed_energies,label=failed_label,color='red',s=75)
                first=False
            else: 
                ax.scatter(failed_indices,failed_energies,color='red',s=75)
               
            
    # ax.axvspan(xmin=0, xmax=4.5, facecolor='red', alpha=0.2)
    if debug: print(f"indices: {indices}")
    xmin = min(indices)
    xmax = max(indices)
    ax.set_xticks(range(xmin,xmax+1))
    ax.set_xlim(xmin-0.5,xmax +0.5)
    ax.tick_params(axis='x', labelsize=20) # Adjust x-axis tick label size
    ax.tick_params(axis='y', labelsize=20) # Adjust y-axis tick label size
    ax.set_title(title,fontsize=20)
    ax.set_xlabel(xlabel,fontsize=16)
    ax.set_ylabel(ylabel,fontsize=16)
    if ylim:
        ax.set_ylim(ylim[0],ylim[1])
    ax.axhspan(ymin=-120,ymax=0,facecolor='grey',alpha=0.2)
    ax.axhline(y=0, color='black', linestyle='-')
        # Move legend below plot
    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.3),
        ncol=2  # adjust number of columns as needed
    )
    
    fig.tight_layout()
    if show:
        fig.show()
    if filename:
        fig.savefig(filename, dpi=300, bbox_inches='tight')
# ----------

def find_row(reaction_data,reaction_name):
    condition = (reaction_data['reaction_name'] == reaction_name)
    if condition.sum() == 0:
        return None
    elif condition.sum() == 1:
        return reaction_data[condition].iloc[0]
    else:
        raise ValueError('reaction data contains multiple reactions with the same name')










#//////////////////////////////////////////// DEPRECATED

def plot_energy_vs_chain_length(reaction_name,figure_data,validation_data):
    fig, ax = plt.subplots()
    ax.plot(figure_data['chain_length'],figure_data[reaction_name],color='black')
    
    success_condition = (validation_data[reaction_name]==True)
    valid_chain_lengths = figure_data['chain_length'][success_condition]
    valid_energies = figure_data[reaction_name][success_condition]
    ax.scatter(valid_chain_lengths,valid_energies,color='lime',s=200)
    
    error_condition = (validation_data[reaction_name]==False)
    error_chain_lengths = figure_data['chain_length'][error_condition]
    error_energies = figure_data[reaction_name][error_condition]
    ax.scatter(error_chain_lengths,error_energies,color='red',s=200)

    # y = np.full(5,5)
    # plt.fill_betweenx(y, 0, 5, facecolor='lightblue', alpha=0.5)
    ax.axvspan(xmin=2.5, xmax=4.5, facecolor='red', alpha=0.5)
    ax.set_xticks(range(3,9))
    ax.set_xlim(2.5,8.5)
    ax.tick_params(axis='x', labelsize=20) # Adjust x-axis tick label size
    ax.tick_params(axis='y', labelsize=20) # Adjust y-axis tick label size
    ax.set_title(reaction_name.replace('_',' '),fontsize=20)
    ax.set_xlabel('Chain Length (no. carbons)',fontsize=16)
    ax.set_ylabel('$\Delta{}E_0$ (kcal/mol)',fontsize=16)
    ax.set_ylim(-120,120)
    ax.axhspan(ymin=-120,ymax=0,facecolor='grey',alpha=0.5)
    fig.savefig(f'chemdraw_figure_images/{reaction_name}.png',bbox_inches='tight') 
    fig.show()
    # plt.close

def plot_energy_vs_chain_length_multiple(reactions,figure_data,validation_data,title):  
    fig, ax = plt.subplots()
    first = True
    for reaction_name, reaction_label in reactions:  
        error_condition = (validation_data[reaction_name]==False)
        error_chain_lengths = figure_data['chain_length'][error_condition]
        error_energies = figure_data[reaction_name][error_condition]
        if first:
            ax.scatter(error_chain_lengths,error_energies,color='red',label='calculation error',s=100,alpha=0.5)
            first = False
        else:
            ax.scatter(error_chain_lengths,error_energies,color='red',s=100,alpha=0.5)

        
        if 'upconversion' in reaction_name:
            ax.plot(figure_data['chain_length'],figure_data[reaction_name],
                    label=reaction_label,color='black',lw=3)
        else:
            ax.plot(figure_data['chain_length'],figure_data[reaction_name],
                    label=reaction_label,lw=2)
        
        # success_condition = (validation_data[reaction_name]==True)
        # valid_chain_lengths = figure_data['chain_length'][success_condition]
        # valid_energies = figure_data[reaction_name][success_condition]
        # ax.scatter(valid_chain_lengths,valid_energies,color='lime',)
        
        # y = np.full(5,5)
        # plt.fill_betweenx(y, 0, 5, facecolor='lightblue', alpha=0.5)
    ax.axvspan(xmin=2.5, xmax=4.5, facecolor='red', alpha=0.2)
    ax.set_xticks(range(3,9))
    ax.set_xlim(2.5,8.5)
    ax.tick_params(axis='x', labelsize=20) # Adjust x-axis tick label size
    ax.tick_params(axis='y', labelsize=20) # Adjust y-axis tick label size
    ax.set_title(title,fontsize=20)
    ax.set_xlabel('Chain Length (no. carbons)',fontsize=16)
    ax.set_ylabel('$\Delta{}E_0$ (kcal/mol)',fontsize=16)
    ax.set_ylim(-90,30)
    ax.axhspan(ymin=-120,ymax=0,facecolor='grey',alpha=0.2)
    ax.axhline(y=0, color='black', linestyle='-')
    ax.legend()
    fig.show()
        # plt.close



def get_data_chains(start_index,end_index,meta_reactions,
                    root_dir,normal_dir,normal_theory,
                    backup_dir=None, backup_theory=None,
                    constrained_dir=None,constrained_theory=None,
                    force_merge = [],
                    
                   ):
    '''
    specific case of processing data for the alcohol cycle data set
    '''
    energy_dfs = []
    status_dfs = []
    for i in range(start_index,end_index+1):
        key = f"chain_{i}"
        reactions = meta_reactions[key]
        reaction_names = reactions.keys()
        
        normal_root = os.path.join(root_dir,normal_dir)
        data = get_reaction_molecule_data(normal_root,reactions,normal_theory)

        if backup_dir and backup_theory:
            backup_root = os.path.join(root_dir,backup_dir)
            backup_data = get_reaction_molecule_data(backup_root,reactions,backup_theory)
            data = merge_data(data,backup_data,force_merge)

        if constrained_dir and constrained_theory:
            constrained_root = os.path.join(root_dir,constrained_dir)
            constrained_data = get_reaction_molecule_data(constrained_root,reactions,constrained_theory)
            constrained_data = constrained_data.dropna(thresh=4)
        
            data = replace_data(data,constrained_data)
        
        single_chain_df = get_reaction_data(data,reactions)
        keys = single_chain_df['reaction_name']
        
        single_chain_df = single_chain_df.set_index(single_chain_df['reaction_name'])
        single_energy_df = single_chain_df[['E_el_kcal/mol']].T
        single_energy_df['chain_length'] = i

        single_status_df = single_chain_df[['all_succeeded']].T
        single_status_df['chain_length'] = i
        
        energy_dfs.append(single_energy_df)
        status_dfs.append(single_status_df)
        
    all_energy_data = pd.concat(energy_dfs)
    all_energy_data.index = range(len(all_energy_data))

    all_status_data = pd.concat(status_dfs)
    all_status_data.index = range(len(all_status_data))
    
    return all_energy_data, all_status_data




def get_reaction_energy(root,reaction_name,reactants,products,of_dir,sp_dir):
    params = {'products':products,'reactants':reactants,'root_dir':root,
              'root_basename':reaction_name,'opt_freq_dir':of_dir,
              'singlepoint_dir':sp_dir,'debug':False}
    tree = parse_tree_builders.SimpleThermoTreeBuilder(params).build()
    tree.depth_first_parse()
    return tree.data

