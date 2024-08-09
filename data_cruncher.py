import directory_scrounger as ds
import file_peruser as fr
import pandas as pd
import os
import re

def df_from_dicts(dict_chemical_dicts):
     data = {}
     first_pass = True
     list_of_labels = []
     for outer_key in dict_chemical_dicts:
         list_of_labels.append(outer_key)
         chemical_dict = dict_chemical_dicts[outer_key]
         for in_key in chemical_dict:
             if first_pass:
                 data[in_key] = []
             data[in_key].append(chemical_dict[in_key])
         first_pass = False
     df = pd.DataFrame(data, index=list_of_labels)
     return df

def df_from_directory(directory, ruleset, file_substrings = None, not_substrings=None, recursive=True):

    filenames = ds.find_filenames_substring_list(directory,file_substrings, not_substrings, recursive)
    data_dict = {}
    print('looking for filenames')
    for filename in filenames:
        base_filename = os.path.basename(filename)
        chem_name = os.path.splitext(base_filename)[0]
        print(f'reading from {filename}')
        data_dict[chem_name] = fr.extract_data(filename, ruleset)
    return df_from_dicts(data_dict)


def make_subframe(old_dataframe, keywords):
    
    copy_dataframe = old_dataframe.copy()
    if type(keywords) is list:
        for substring in keywords:
            mask = copy_dataframe.index.str.contains(substring)
            copy_dataframe = copy_dataframe[mask]
    else:
        mask = copy_dataframe.index.str.contains(keywords)
        copy_dataframe = copy_dataframe[mask]
    return copy_dataframe



def valid_frame(dataframe, key, expectation = True):
    '''
    UNTESTED, MAY GIVE ISSUES
    '''
    return dataframe[key].all() is expectation


def frames_operation(frame_1, frame_2, operation):
    '''
    
    '''
    pass

def add_column(dataframe, key, value_array):
    '''
    adds column to dataframe, returns by value.
    if want to add by reference,
    just use the native dataframe function.
    UNTESTED
    '''
    copy_df = dataframe.copy()
    if len(value_array) == len(dataframe):
        copy_df[key] = value_array
        return copy_df
    else:
        raise ValueError("mismatched dataframe / array length.")


def add_accumulated_sum_row(dataframe, row_index = 'sum'):
    '''
    UNTESTED
    adds row with sums of columns for each column
    labeled 'sum' by default
    '''
    new_row = dataframe.sum(axis=0) #sum along columns
    #convert series to dataframe and transpose to match original dataframe shape
    new_row_df = pd.DataFrame([new_row], columns=dataframe.columns)
    new_row_df.index = [row_index]
    df_with_sum = dataframe.append(new_row_df)
    return df_with_sum
    
def add_difference_row(dataframe, row_ind_1, row_ind_2, dif_row_ind = 'difference'):
    '''
    UNTESTED
    adds row as difference of two rows, with index as desired
    '''
    difference = dataframe.loc[row_ind_1] - dataframe.loc[row_ind_2]
    difference_df = pd.DataFrame([difference], columns=dataframe.columns)
    difference_df.index = [dif_row_ind]
    df_with_difference = dataframe.append(difference_df)
    return df_with_difference
    
def frame_from_rows(dataframe, row_indices):
    '''
    UNTESTED
    makes new frame containing only desired row
    '''
    #print('in frame_from_rows')
    return dataframe.iloc[row_indices]

def frame_from_cols(dataframe, col_keys):
    '''
    UNTESTED
    makes new frame containing only desired cols
    this is just a native pandas function
    still useful for me to give these
    my own names, so that I have them
    '''
    return dataframe.loc[col_keys]

def rename_columns(dataframe, old_name_re, replacement):
    '''
    UNTESTED
    renames columns based on regex
    '''
    return dataframe.rename(columns=lambda x: re.sub(old_name_re, replacement, x))

#TO DO- FIX SUCCESSFUL COMPLETION BUG WITH ORCA

def calculate_reaction_energies(df, reaction_name, reactants, products, energy_types):
    """
    Calculate the reaction energies for specified energy types.

    df: DataFrame with chemicals as indices and energies as columns.
    reactants: Dictionary with reactant names as keys and stoichiometric coefficients as values.
    products: Dictionary with product names as keys and stoichiometric coefficients as values.
    energy_types: List of column names to calculate reaction energies for.
    """
    reaction_energies = {}
    for energy_type in energy_types:
        if energy_type in df.columns:
            reactant_energy = sum(df.loc[reactant][energy_type] * coeff for reactant, coeff in reactants)
            product_energy = sum(df.loc[product][energy_type] * coeff for product, coeff in products)
            reaction_energies[energy_type] = product_energy - reactant_energy
        else:
            reaction_energies[energy_type] = None
    return pd.Series(reaction_energies, name=reaction_name)

#WANT: SEARCH INDICES AND COLUMNS FOR MATCHING KEYS AND USE ALL MATCHES

def frame_mult_reaction_energies(df,list_of_reactions, energy_types):
    """
    Calculate the reaction energies for specified energy types for multiple reactions.

    df: DataFrame with chemicals as indices and energies as columns.
    list_of_reactions: List of dictionaries with reaction names as keys and reactants and products as values.
    energy_types: List of column names to calculate reaction energies for.
    """
    reaction_energies = []
    for reaction in list_of_reactions:
        name = reaction[0]
        reactants = reaction[1]
        products = reaction[2]
        reaction_energies.append(calculate_reaction_energies(df, name, reactants, products, energy_types))
    return pd.DataFrame(reaction_energies)

def convert_units(df, energy_types, old_unit, new_unit, conversion_factor):
    '''
    
    '''
    
    dfc = df.copy()
    
    if isinstance(dfc, pd.Series):
        dfc = dfc.to_frame()

    if energy_types == '__all__':
        for column in dfc.columns:
            if re.search(old_unit, column):
                dfc[column] *= conversion_factor
                new_name = re.sub(old_unit, new_unit, column)
                dfc = dfc.rename(columns={column: new_name})
    else:
        for energy_type in energy_types:
            dfc[energy_type] *= conversion_factor
            new_name = re.sub(old_unit, new_unit, energy_type)
            dfc = dfc.rename(columns={energy_type: new_name})
    return rename_columns(dfc, old_unit, new_unit)
    
    
import pandas as pd
import re

def compare_re(df, cols, regex1, regex2, operation=lambda x, y : x - y):
    '''
    accepts a dataframe, first regex, second regex, and an operation (function)
    filters indices by regex, accepts cols as args
    O(N^2), can probably be made better
    for now-
    this assumes that the dataframe can be evenly divided
    into two halves, one with regex1 and one with regex2
    '''
    if type(cols) is not list:
        cols = [cols]
    
    # Create two new DataFrames by filtering the original DataFrame using the regular expressions
    df1 = df[cols].filter(regex=regex1, axis=0)
    df2 = df[cols].filter(regex=regex2, axis=0)
    # 
    df1 = df1.rename(index=lambda x: re.sub(regex1, '', x))
    df2 = df2.rename(index=lambda x: re.sub(regex2, '',x))
    
    df1 = df1.sort_index()
    df2 = df2.sort_index()
    
    new_df = operation(df1,df2)
    
    return new_df


def st_gaps_routine(directory, functionals):
    '''
    routine for working up lots of st gaps.
    assumes that singlets have the string 'singlet' in their keys,
    and that triplets have the string 'triplet' in their keys.
    also assumes orca .out files and no slurm files.
    '''
    
    df = df_from_directory(directory,ruleset='data/rules/ORCA.rules',file_substrings='.out')

    frames = {}
    for functional in functionals:
        #issue- make_subframe doesn't seem to properly filter these.
        frames[functional] = make_subframe(df,functional)
        frames[functional] = compare_re(frames[functional],'SP_energy_au','triplet','singlet')
        
    for key in frames:
        frames[key] = convert_units(frames[key],'__all__','au','kcal/mol',627.51)
        frames[key] = filter_indices_keys(frames[key],r'structure_[0-9]+')
        frames[key] = order_indices_by_digit(frames[key])
        
    erase = '_opt_freq_'
    frames2 = {}
    for key in frames:
        new_key = re.sub(erase,'_',key)
        if new_key.endswith('_'):
            new_key = new_key[:-1]
        frames2[new_key] = frames[key]
    frames = frames2
    del frames2
    
    #plot function needs work as well   
    # for key in frames:
    #     print(key) 
    plot_dataframes(frames,'SP_energy_kcal/mol')    
    
    return frames

#still to do-
#new to do- filter indices by regex

def filter_indices_keys(df, regex):
    '''
    UNTESTED
    filters indices by regex
    '''
    def keep_keys (x):
        match = re.search(regex,x)
        if match:
            return match.group(0)
    dfc = df.copy()
    dfc.rename(index=keep_keys,inplace=True)

    return dfc

def order_indices_by_digit(_df):
    # Extract digits from indices
    df = _df.copy()
    
    df['index_num'] = df.index.str.extract(r'(\d+)', expand=False).astype(int)

    # Sort by extracted digits
    df = df.sort_values('index_num')

    # Drop the temporary column
    df.drop('index_num', axis=1, inplace=True)

    return df
#graphing routine
#problem: would rather data points were just missing
#instead of only showing jobs that all worked...




import matplotlib.pyplot as plt

def plot_dataframes(frames,col):
    '''
    accepts either a dataframe or a dict of dataframes
    prints a plot with all of the data shared on the same axes
    needs the dataframes to have indices and cols in common
    '''
        # Create a new figure and axes
    if type(frames) is not dict:
        frames = {'key1' : frames}
        
    fig, ax = plt.subplots()

    # Add each DataFrame to the plot
    for key, frame in frames.items():
        # Convert Series to DataFrame if necessary
        if isinstance(frame, pd.Series):
            frame = frame.to_frame()
            
        ax.plot(frame.index, frame[col], label=f'{key}')
    
    all_indices = pd.concat(frames.values()).index.unique()
    plt.xticks(ticks=range(len(all_indices)),labels=all_indices,rotation='vertical')

    ax.set_ylabel('Energy (kcal/mol)')
    ax.legend()
    # Show the plot
    plt.show()
    
'''
to do now-
 work on plotting functions
 work on getting list of failed trials
'''