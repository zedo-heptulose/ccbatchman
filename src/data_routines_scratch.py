import sys
path1 = '/gpfs/home/gdb20/code/ccbatchman/src/'
path2 = '/gpfs/home/gdb20/code/mol-maker/src/'
paths = [path1,path2]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)
import input_combi
import os
import parse_tree_builders
import molecule
import utilities
import pandas as pd
import numpy as np

###########################################################
# General routines

###########################################################

def get_reaction_energy(root_directory: str, reaction_name:str,reactants: dict[str,int], 
                          products: dict[str,int], theory:str, 
                          singlepoint_theory:str = None,energy_type:list[str] = ['E_elec','H','G'],
                         debug:bool =False) -> dict:
    """
    Get reaction energy of a given type.

    Args:
        root_directory: str - directory jobs are in
        reaction_name: str -> name of reaction for collection in dataframes and such
        reactants: dict[str,int] dict mapping directory name for given molecule, within root_directory to integer representing reaction coefficient
        products: same as reactants
        theory: str - directory identifying level of theory for given molecule, within each directory identifying molecule
        singlepoint_theory: str - optional, for if we use a different level of theory for electronic energy than for optimization and frequency, default None
        energy_type: str -> optional, for if we want electronic only, energy, enthalpy, gibbs, etc, default all
        debug: bool -> optional, pass debug flag to parse tree builder for verbose output, default False

    Output:
        dictionary containing reaction energy data
    """
    
    params = {
        'root_dir':root_directory,
        'root_basename' : reaction_name, #will need to change implementation of parse tree for this
        'products':products,
        'reactants':reactants,
        'singlepoint_dir' : singlepoint_theory if singlepoint_theory else theory,
        'of_dir' : theory,
        'debug' : debug,
        'energy_types' : energy_types
    }
    tree = parse_tree_builders.ReactionTreeBuilder(params)
    tree.depth_first_parse()
    return tree.data

def get_many_reaction_energies(root,reactions:list[tuple[dict[str,int],dict[str,int]]],levels_of_theory:list[tuple[str,str]]) -> pd.DataFrame:
    #implementation is up to Claude here, should iterate through all reaction
    #which are list of tuple(reactants,products) in the format defined above
    #at all levels of theory, which are lists of tuples (theory,singlepoint_theory (or None))   
    #shown below is an implementation of a similar function, which is NOT the proper
    #implementation of what this is meant to be
    #also feel free to rename this function to something more appropriate if necessary
    list_rows = []
    reactions = [{'name' : name, 'reactants': val['reactants'],'products':val['products']} for name,val in reactions.items()]
    for reaction in reactions: 
        reaction_name = reaction['name']
        reactants = reaction['reactants']
        products = reaction['products']
        
        theory = f"singlepoints/{functional}_{basis_set}"
        
        try:
            # print('in get_delta_E_vals, entering try block')
            # print('calling get_reaction_energy')
            reaction_energy = get_reaction_energy(benchmark_root,reaction_name,reactants,products,theory)
            row = pd.DataFrame({
                'reaction': [reaction_name],
                'functional' : [functional],
                'basis_set' : [basis_set],
                'ΔE_el_rxn(kcal/mol-1)' : [reaction_energy],
            })
            list_rows.append(row)
            # print('done calling get_reaction_energy successfully')
                    
        except:
            # print(f"{reaction_name} could not be parsed")
            row = pd.DataFrame({
                'reaction': [reaction_name],
                'functional' : [functional],
                'basis_set' : [basis_set],
                'ΔE_el_rxn(kcal/mol-1)' : [np.nan],
            })
            list_rows.append(row)
    
    data = pd.concat(list_rows,axis=0,ignore_index=True)
    return data



######################################
# benchmark specific routines
######################################

def get_benchmark_error_data(theory_data: pd.DataFrame,benchmark_theory:str) -> pd.DataFrame:
    #this function should accept as input a dataframe of the type that might be output
    #by the previous function.
    #we should be able to tell it that one of the levels of theory from the last one was
    #a benchmark that everything else should be compared to.
    #and it should return a DataFrame with the columns where energies would be
    #replaced instead with differences in energy from the benchmark.

def summarize_benchmark_error_metrics(error_data:pd.DataFrame) -> pd.DataFrame:
    #this function should accept as input a dataframe output by the previous function,
    #and condense it to a single row for each level of theory;
    #the columns should be error statistics like RMSE MAD MSE STDEV etc

#we would also like some plotting functions here.
# I would like to be able specifically to make a 2d heatmap of errors for varying functionals
# and basis sets


