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

def get_reaction_energy(root,reaction_name,reactants,products,of_dir,sp_dir):
    params = {'products':products,'reactants':reactants,'root_dir':root,
              'root_basename':reaction_name,'opt_freq_dir':of_dir,
              'singlepoint_dir':sp_dir,'debug':False}
    tree = parse_tree_builders.SimpleThermoTreeBuilder(params).build()
    tree.depth_first_parse()
    return tree.data


def get_reaction_molecule_data(root,reactants,products,theory,exclude=[]):
    molecule_list = []
    theory_list = []
    status_list = []
    electronic_energy_list = []
    energy_list = []
    enthalpy_list = []
    gibbs_list = []
    for molecule in {**reactants,**products}.keys():    
        if not os.path.exists(os.path.join(root,molecule,theory,theory+'.out')):
            energy_list.append(np.nan)
            enthalpy_list.append(np.nan)
            gibbs_list.append(np.nan)
                
            molecule_list.append(molecule)
            theory_list.append(theory)
            status_list.append('nonexistent')
            electronic_energy_list.append(np.nan)
            # print(f'{molecule} does not exist')
            continue
            # raise ValueError('nonsense directory')
        if molecule in exclude:
            continue

        if os.path.exists(os.path.join(root,molecule,theory,'run_info.json')):# brutal hotfix, pls change
            with open(os.path.join(root,molecule,theory,'run_info.json'),'r') as run_info_file:
                run_info_data = json.load(run_info_file)
            status = run_info_data['status']
        else:
            status = 'succeeded' # brutal.
            
        parseleaf = parse_tree.ParseLeaf()
        parseleaf.directory = os.path.join(root,molecule,theory)
        parseleaf.basename = theory
        parseleaf.parse_data()
        data = parseleaf.data
        try:
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
            electronic_energy_list.append(data['E_el_au'])
        except:
            print(f"{molecule} | {theory}")
            print(data)
    data_df = pd.DataFrame({
        'molecule' : molecule_list,
        'theory' : theory_list,
        'status' : status_list,
        'E_el_au' : electronic_energy_list,
        'E_au' : energy_list,
        'H_au' : enthalpy_list,
        'G_au' : gibbs_list,
    })
    return data_df


def show_reaction_structures(root,reaction,theory):
    reactants = reaction[0]
    products = reaction[1]
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


def get_molecule_data(root,reactions,theory,exclude=[],show_structures=False):
    df_list = []
    for name, reaction in reactions.items():
        if show_structures:
            show_reaction_structures(root,reaction,theory)
        data_df = get_reaction_molecule_data(root,reaction[0],reaction[1],theory,exclude)
        df_list.append(data_df)
        
    cumulative_df = pd.concat(df_list)
    cumulative_df.drop_duplicates(subset=['molecule','theory'], keep='first', inplace=True, ignore_index=True)
    cumulative_df.index = range(len(cumulative_df))
    return cumulative_df

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


def get_reaction_data(molecule_df,reactions,debug=False):
    df_list = []
    energy_types = ['E_el_au','E_au','H_au','G_au']
    conversions = {'kcal/mol':627.51}
    for reaction_name, reaction in reactions.items():
        good_data = True
        reactants = reaction[0]
        products = reaction[1]
        energy_data = {}
        for energy_type in energy_types:
            energy_data[energy_type] = 0
            
            for reactant, coefficient in reactants.items():
                if debug: print(reactant)
                if (molecule_df['molecule']==reactant).sum() == 0:
                    print(reactant)
                    print('oh no!')
                if not molecule_df[molecule_df['molecule']==reactant].iloc[0]['status'] == 'succeeded':
                    good_data = False
                if debug: print(molecule_df[molecule_df['molecule']==reactant].iloc[0])
                energy_data[energy_type] -= molecule_df[molecule_df['molecule']==reactant].iloc[0][energy_type] * coefficient
            
            for product, coefficient in products.items():
                if debug: print(product)
                if (molecule_df['molecule']==product).sum() == 0:
                    print(product)
                    print('oh no!')
                if debug: print(molecule_df[molecule_df['molecule']==product].iloc[0])
                energy_data[energy_type] += molecule_df[molecule_df['molecule']==product].iloc[0][energy_type] * coefficient
                if not molecule_df[molecule_df['molecule']==product].iloc[0]['status'] == 'succeeded':
                    good_data = False
                    
            for unit, proportion in conversions.items():
                energy_data[f"{energy_type[:-3]}_{unit}"] = energy_data[energy_type] * proportion
                energy_data[f"{energy_type[:-3]}_{unit}"] = [energy_data[f"{energy_type[:-3]}_{unit}"]] # for making dataframe
            energy_data[energy_type] = [energy_data[energy_type]] # for making dataframe
            
        energy_df = pd.DataFrame(energy_data)
        energy_df['reaction_name'] = [reaction_name]
        energy_df['all_succeeded'] = good_data
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


def get_data_chains(start_index,end_index,meta_reactions,
                    root_dir,normal_dir,normal_theory,
                    backup_dir=None, backup_theory=None,
                    constrained_dir=None,constrained_theory=None,
                    force_merge = []
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
        data = get_molecule_data(normal_root,reactions,normal_theory)

        if backup_dir and backup_theory:
            backup_root = os.path.join(root_dir,backup_dir)
            backup_data = get_molecule_data(backup_root,reactions,backup_theory)
            data = merge_data(data,backup_data,force_merge)

        if constrained_dir and constrained_theory:
            constrained_root = os.path.join(root_dir,constrained_dir)
            constrained_data = get_molecule_data(constrained_root,reactions,constrained_theory)
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



def reaction_data_routine(reactions,root_dir,molecule_dirs,
                         backup_dirs=None,
                         replace_dirs=None,
                         force_merge=[]):
    '''
    general case for processing reaction data
    force_merge is a list of molecules in the backup directory that we
    treat as being in the replace directory
    '''
    reaction_names = reactions.keys()

    normal_dir = molecule_dirs[0]
    normal_theory = molecule_dirs[1]
    normal_root = os.path.join(root_dir,normal_dir)
    data = get_molecule_data(normal_root,reactions,normal_theory)

    if backup_dirs:
        backup_dir = backup_dirs[0]
        backup_theory = backup_dirs[1]
        backup_root = os.path.join(root_dir,backup_dir)
        backup_data = get_molecule_data(backup_root,reactions,backup_theory)
        data = merge_data(data,backup_data,force_merge)

    if replace_dirs:
        replace_dir = replace_dirs[0]
        replace_theory = replace_dirs[1]
        replace_root = os.path.join(root_dir,replace_dir)
        replacement_data = get_molecule_data(replace_root,reactions,replace_theory)
        replacement_data = replacement_data.dropna(thresh=4)
    
        data = replace_data(data,replacement_data)
    
    return get_reaction_data(data,reactions)



def plot_enumerated_reactions(reactions,reaction_data,title):
    reaction_names = reactions.keys()
    # filter out common part without index
    name_roots = set()
    indices = set()
    print('iterating through reaction names, finding number')
    for name in reaction_names:
        name_no_number= re.sub(r'\d+','',name)
        name_roots.add(name_no_number)
        match = re.search(r'\d+',name)
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
    # print(indices,sep='\n')
    name_roots = list(name_roots)
    # print(name_roots,sep='\n')
    
    fig, ax = plt.subplots()
    first = True
    for root in name_roots:
        print('found root:')
        print(root)
        enumerated_names = [ root + str(i) for i in indices] 
        print('enumerated names:')
        # print(enumerated_names,sep='\n')
        electronic_energies = []
        for name in enumerated_names:
            row = find_row(reaction_data,name)
            electronic_energies.append(row['E_el_kcal/mol'])
        ax.plot(indices,electronic_energies,label=root)
    
    # ax.axvspan(xmin=0, xmax=4.5, facecolor='red', alpha=0.2)
    xmin = min(indices)
    xmax = max(indices)
    ax.set_xticks(range(xmin,xmax+1))
    ax.set_xlim(xmin-0.5,xmax +0.5)
    ax.tick_params(axis='x', labelsize=20) # Adjust x-axis tick label size
    ax.tick_params(axis='y', labelsize=20) # Adjust y-axis tick label size
    ax.set_title(title,fontsize=20)
    ax.set_xlabel('Chain Length (no. carbons)',fontsize=16)
    ax.set_ylabel('$\Delta{}E_0$ (kcal/mol)',fontsize=16)
    # ax.set_ylim(-100,100)
    ax.axhspan(ymin=-120,ymax=0,facecolor='grey',alpha=0.2)
    ax.axhline(y=0, color='black', linestyle='-')
        # fig.savefig(f'chemdraw_figure_images/{reaction_name}.png',bbox_inches='tight') 
    ax.legend()
    fig.show()
# ----------

def find_row(reaction_data,reaction_name):
    condition = (reaction_data['reaction_name'] == reaction_name)
    if condition.sum() == 0:
        return None
    elif condition.sum() == 1:
        return reaction_data[condition].iloc[0]
    else:
        raise ValueError('reaction data contains multiple reactions with the same name')


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
    fig.axhline(y=0, color='black', linestyle='-')
        # fig.savefig(f'chemdraw_figure_images/{reaction_name}.png',bbox_inches='tight') 
    ax.legend()
    fig.show()
        # plt.close







