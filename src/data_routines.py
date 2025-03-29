import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import parse_tree
import parse_tree_builders
import json


class ComputationalDataProcessor:
    """
    A class for processing computational chemistry data across various theoretical methods.
    Handles reaction energies, benchmarking, and visualization of results.
    """
    
    def __init__(self, root_dir, debug=False):
        """
        Initialize the data processor with a root directory.
        
        Parameters:
        -----------
        root_dir : str
            Path to the root directory containing computational data
        debug : bool
            Whether to print debug information
        """
        self.root_dir = root_dir
        self.debug = debug
        
    def get_reaction_energy(self, reaction_name, reactants, products, theory):
        """
        Calculate reaction energy for a given reaction.
        
        Parameters:
        -----------
        reaction_name : str
            Name of the reaction
        reactants : dict
            Dictionary of reactants and their stoichiometric coefficients
        products : dict
            Dictionary of products and their stoichiometric coefficients
        theory : str
            Path to the theory level directory
            
        Returns:
        --------
        float
            Reaction energy in kJ/mol
        """
        params = {
            'products': products,
            'reactants': reactants, 
            'root_dir': self.root_dir,
            'root_basename': reaction_name,
            'singlepoint_dir': theory, 
            'debug': self.debug
        }
        
        tree = parse_tree_builders.SimpleETreeBuilder(params).build()
        tree.depth_first_parse()
        return tree.data['Delta_E_el_kj_mol-1']
    
    def get_reaction_free_energy(self, reaction_name, reactants, products, of_dir, sp_dir):
        """
        Calculate Gibbs free energy for a reaction.
        
        Parameters:
        -----------
        reaction_name : str
            Name of the reaction
        reactants : dict
            Dictionary of reactants and their stoichiometric coefficients
        products : dict
            Dictionary of products and their stoichiometric coefficients
        of_dir : str
            Path to the optimization/frequency calculations
        sp_dir : str
            Path to the single point calculations
            
        Returns:
        --------
        float
            Gibbs free energy in kcal/mol
        """
        params = {
            'products': products,
            'reactants': reactants,
            'root_dir': self.root_dir,
            'root_basename': reaction_name,
            'opt_freq_dir': of_dir,
            'singlepoint_dir': sp_dir,
            'debug': self.debug
        }
        
        tree = parse_tree_builders.SimpleThermoTreeBuilder(params).build()
        tree.depth_first_parse()
        return tree.data['Delta_G_kcal_mol-1']

    def get_reaction_data(self, reaction_name, reactants, products, of_dir, sp_dir):
        params = {
            'products': products,
            'reactants': reactants,
            'root_dir': self.root_dir,
            'root_basename': reaction_name,
            'opt_freq_dir': of_dir,
            'singlepoint_dir': sp_dir,
            'debug': self.debug
        }
        
        tree = parse_tree_builders.SimpleThermoTreeBuilder(params).build()
        tree.depth_first_parse()
        return tree.data


    
    def get_delta_E_vals(self, reactions, functional, basis_set):
        """
        Get reaction energies for multiple reactions at a specific level of theory.
        
        Parameters:
        -----------
        reactions : dict
            Dictionary of reactions with their reactants and products
        functional : str
            Computational functional to use
        basis_set : str
            Basis set to use
            
        Returns:
        --------
        pandas.DataFrame
            DataFrame containing reaction energies
        """
        list_rows = []
        reactions_list = [{'name': name, 'reactants': val['reactants'], 'products': val['products']} 
                          for name, val in reactions.items()]
        
        for reaction in reactions_list: 
            reaction_name = reaction['name']
            reactants = reaction['reactants']
            products = reaction['products']
            
            theory = f"singlepoints/{functional}_{basis_set}"
            
            try:
                reaction_energy = self.get_reaction_energy(reaction_name, reactants, products, theory)
                row = pd.DataFrame({
                    'reaction': [reaction_name],
                    'functional': [functional],
                    'basis_set': [basis_set],
                    'ΔE_el_rxn(kcal/mol-1)': [reaction_energy],
                })
                list_rows.append(row)
                      
            except Exception as e:
                if self.debug:
                    print(f"{reaction_name} could not be parsed: {str(e)}")
                row = pd.DataFrame({
                    'reaction': [reaction_name],
                    'functional': [functional],
                    'basis_set': [basis_set],
                    'ΔE_el_rxn(kcal/mol-1)': [np.nan],
                })
                list_rows.append(row)
        
        data = pd.concat(list_rows, axis=0, ignore_index=True)
        return data

    def calculate_deviations(self, functionals, basis_sets, reactions, reference_method='dlpno-ccsd_t', reference_basis='cbs'):
        """
        Calculate deviations of reaction energies from a reference method.
        
        Parameters:
        -----------
        functionals : list or dict
            List or dict of computational functionals
        basis_sets : list or dict
            List or dict of basis sets
        reactions : dict
            Dictionary of reactions with their reactants and products
        reference_method : str
            Reference method to compare against
        reference_basis : str
            Reference basis set
            
        Returns:
        --------
        pandas.DataFrame
            DataFrame containing MAD and RMSD values for each method
        """
        # If dictionaries are provided, extract the keys
        if isinstance(functionals, dict):
            functionals = list(functionals.keys())
        if isinstance(basis_sets, dict):
            basis_sets = list(basis_sets.keys())
            
        # Get reference data
        reference_path = f"../{reference_method}" if reference_method.startswith("dlpno") else reference_method
        cc_data = self.get_delta_E_vals(reactions, reference_path, reference_basis)
        list_rows = []
        
        for functional in functionals:
            for basis_set in basis_sets:
                data = self.get_delta_E_vals(reactions, functional, basis_set)
                data['ΔΔE_el_rxn(kcal/mol-1)'] = data['ΔE_el_rxn(kcal/mol-1)'] - cc_data['ΔE_el_rxn(kcal/mol-1)']
                
                # Filter out NaN values and extreme outliers
                deviations = data[(data['ΔΔE_el_rxn(kcal/mol-1)'].notna()) & 
                                 (data['ΔΔE_el_rxn(kcal/mol-1)'].abs() < 100)]['ΔΔE_el_rxn(kcal/mol-1)']
                
                # Calculate statistics
                mad = deviations.abs().mean()
                rmsd = (deviations**2).mean()**0.5
                
                if self.debug:
                    print(f"Results for {functional}_{basis_set}:")
                    print(f"MAD: {mad}")
                    print(f"RMSD: {rmsd}")
                    print(f"Sample size: {len(deviations)}")
                    print()
                
                if len(deviations) < 3 and self.debug:
                    print(f"Warning: Less than 3 data points for {functional}_{basis_set}")
                    print(data)
                
                row = pd.DataFrame({
                    'functional': [functional],
                    'basis_set': [basis_set],
                    'MAD': [mad],
                    'RMSD': [rmsd],
                    'sample_size': [len(deviations)]
                })
                list_rows.append(row)
        
        data = pd.concat(list_rows, axis=0, ignore_index=True)
        return data
    
    def visualize_benchmark(self, functionals, basis_sets, data, metric='RMSD', 
                            title="Error Magnitude for Different Methods", 
                            cmap="viridis_r", vmax=20, save_path=None):
        """
        Create a heatmap visualization of benchmark results.
        
        Parameters:
        -----------
        functionals : list
            List of functionals to include
        basis_sets : list
            List of basis sets to include
        data : pandas.DataFrame
            DataFrame containing benchmark results
        metric : str
            Metric to visualize (default: 'RMSD')
        title : str
            Plot title
        cmap : str
            Matplotlib colormap to use
        vmax : float
            Maximum value for color scale
        save_path : str
            Path to save the figure (if None, figure is not saved)
            
        Returns:
        --------
        matplotlib.figure.Figure
            The created figure
        """
        outer_list = []
        for functional in functionals:
            inner_list = []
            for basis_set in basis_sets:
                value = data[(data['functional'] == functional) & 
                             (data['basis_set'] == basis_set)][metric].iloc[0]
                inner_list.append(value)    
            outer_list.append(inner_list)
        
        errors = np.array(outer_list)
        
        # Create the heatmap
        plt.figure(figsize=(10, 8))
        im = plt.imshow(errors, cmap=cmap, aspect='equal')
        
        plt.clim(0, vmax)
        # Add color bar
        cbar = plt.colorbar(im)
        cbar.set_label(f"{metric} (kcal/mol)")
        
        # Customize axes
        plt.xticks(ticks=np.arange(len(basis_sets)), labels=basis_sets, rotation=90)
        plt.yticks(ticks=np.arange(len(functionals)), labels=functionals)
        plt.xlabel("Basis Sets")
        plt.ylabel("Functionals")
        plt.title(title)
        
        # Add annotations to each cell
        for i in range(errors.shape[0]):
            for j in range(errors.shape[1]):
                plt.text(j, i, f"{errors[i, j]:.1f}", 
                         ha="center", va="center", 
                         color="white" if errors[i, j] > vmax/3 else "black")
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            
        return plt.gcf()

    def analyze_bond_dissociation(self, bond_type, molecule_data, of_dir, sp_dir,
                                  solvent='water',title=None, 
                                  ylim=(0, 120), save_path=None,
                                 debug=False):
        """
        Analyze and visualize bond dissociation energies.
        
        Parameters:
        -----------
        bond_type : str
            Type of bond ('C-C' or 'C-F')
        molecule_data : list
            List of tuples with molecule information
        of_dir : str
            Optimization/frequency directory
        sp_dir : str
            Single point calculation directory
        title : str
            Plot title (if None, a default title is generated)
        ylim : tuple
            Y-axis limits
        save_path : str
            Path to save the figure (if None, figure is not saved)
            
        Returns:
        --------
        matplotlib.figure.Figure
            The created figure
        """
        if title is None:
            title = f"{bond_type} Bond Dissociation Energies | {sp_dir}//{of_dir}"
            
        plt.figure(figsize=(10, 6))

        if not solvent:
            solvent = 'gas'

        outer_molecule_list = []
        outer_df_list = []
        for data in molecule_data:
            df_list = []
            middle_molecule_list = []
            for i in range(0, 8):
                reaction_name = 'scratch'
                if i < 7:
                    if bond_type == 'C-C':
                        products = {
                            f"_{solvent}_{data[1]}_{data[0]}_CF2_{i}_CF2": 1,
                            f"_{solvent}_{data[2]}_CF3_CF2_{6-i}": 1,
                        }
                        reactants = {
                            f"_{solvent}_{data[3]}_{data[0]}_CF2_{7}_CF3": 1,
                        }
                    elif bond_type == 'C-F':
                        products = {
                            f"_{solvent}_{data[1]}_{data[0]}_CF2_{i}_CF_CF2_{6-i}_CF3": 1,
                            "_water_0_2_f": 1,
                        }
                        reactants = {
                            f"_{solvent}_{data[3]}_{data[0]}_CF2_{7}_CF3": 1,
                        }
                    else:
                        raise ValueError(f"Unsupported bond type: {bond_type}")
                elif i == 7:
                    if bond_type == 'C-C':
                        break
                    if bond_type == 'C-F':
                        products = {
                            f"_{solvent}_{data[1]}_{data[0]}_CF2_7_CF2": 1,
                            "_water_0_2_f": 1,
                        }
                        reactants = {
                            f"_{solvent}_{data[3]}_{data[0]}_CF2_7_CF3": 1,
                        }
                    else:
                        pass
                    
                molecule_energy_list = []
                for species in {**reactants, **products}.keys():
                    #parse energies
                    pnode = parse_tree.CompoundNode(species,of_dir,sp_dir,self.root_dir,recursive=True)
                    # pnode.debug = True
                    pnode.parse_data()
                    gibbs = pnode.data['G_au'] 
                    enthalpy = pnode.data['H_au']
                    energy = pnode.data['E_el_thermo_au']
                    sp_energy = pnode.data['E_el_au']
                    mol_df_temp = pd.DataFrame({
                        f'molecule': [species],
                        'G (au)' : [gibbs],
                        'G (kcal/mol)': [gibbs * 627.5],
                        'H (au)' : [enthalpy],
                        'H (kcal/mol)' : [enthalpy * 627.5],
                        'E (au)' : [energy],
                        'E (kcal/mol)' : [energy * 627.5],
                        'E (singlepoint) (au)' : [sp_energy],
                        'E (singlepoint) (kcal/mol)' : [sp_energy * 627.5]
                    })
                    molecule_energy_list.append(mol_df_temp)
                molecule_energy_df = pd.concat(molecule_energy_list)
                middle_molecule_list.append(molecule_energy_df)
                
          
                reaction_data = self.get_reaction_data(reaction_name, reactants, products, of_dir, sp_dir)
                delta_g = reaction_data['Delta_G_au']
                delta_h = reaction_data['Delta_H_au']
                delta_e = reaction_data['Delta_E_el_thermo_au']
                delta_e_sp = reaction_data['Delta_E_el_au']
                bond_index = i + 1
                df_temp = pd.DataFrame({
                    f'{bond_type.lower()}_bond': [bond_index],
                    'Delta G (au)' : [delta_g],
                    'Delta G (kcal/mol)': [delta_g * 627.5],
                    'Delta H (au)' : [delta_h],
                    'Delta H (kcal/mol)' : [delta_h * 627.5],
                    'Delta E (au)' : [delta_e],
                    'Delta E (kcal/mol)' : [delta_e * 627.5],
                    'Delta E (singlepoint) (au)' : [delta_e_sp],
                    'Delta E (singlepoint) (kcal/mol)' : [delta_e_sp * 627.5],
                    'head_frag': [f"{data[0]}_{data[3]}"]
                })
                df_list.append(df_temp)
                
            middle_molecule_df = pd.concat(middle_molecule_list)
            outer_molecule_list.append(middle_molecule_df)
            
            df = pd.concat(df_list)
            x = df[f'{bond_type.lower()}_bond']
            y = df['Delta G (kcal/mol)']
            outer_df_list.append(df)
            plt.plot(x, y, label=df['head_frag'].iloc[0].replace('_', ' '))

        outer_molecule_df = pd.concat(outer_molecule_list)
        outer_molecule_df = outer_molecule_df.drop_duplicates(subset=['molecule'])
        outer_molecule_df.index = range(0,len(outer_molecule_df))
        outer_df = pd.concat(outer_df_list)
        outer_df.index = range(0,len(outer_df))
        plt.title(title)
        plt.ylabel('Delta G (kcal/mol)')
        plt.xlabel('Bond index')
        plt.ylim(ylim)
        plt.legend()
        
        if save_path:
            if save_path.endswith('/'):
                # Create a filename based on the title
                filename = re.sub(r'[^+0-9A-Za-z]', '', title).lower()
                save_path = f"{save_path}{filename}.png"
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        return outer_df, outer_molecule_df

    def make_reactions(self, acid_heads, base_heads):
        """
        Generate a dictionary of reactions based on acid and base heads.
        
        Parameters:
        -----------
        acid_heads : list
            List of acid head groups
        base_heads : list
            List of base head groups
            
        Returns:
        --------
        dict
            Dictionary of generated reactions
        """
        reactions = {}
        
        # Generate acid reactions
        for acid_head in acid_heads:
            acid_reaction_set = {
                f"{acid_head}_anion_C2_F1_BDE_hf": {
                    'reactants': {f"-1_2_{acid_head}_CF2_CF3": 1},
                    'products': {f"0_2_{acid_head}_CF_CF3": 1, f"-1_1_f": 1},
                },
                f"{acid_head}_anion_C2_F2_BDE_hf": {
                    'reactants': {f"-1_2_{acid_head}_CF2_CF3": 1},
                    'products': {f"0_2_{acid_head}_CF2_CF2": 1, f"-1_1_f": 1},
                },
                f"{acid_head}_anion_C1_F1_BDE_hf": {
                    'reactants': {f"-1_2_{acid_head}_CF3": 1},
                    'products': {f"0_2_{acid_head}_CF2": 1, f"-1_1_f": 1},
                },
                f"{acid_head}_anion_C2_F1_BDE": {
                    'reactants': {f"-1_2_{acid_head}_CF2_CF3": 1},
                    'products': {f"-1_1_{acid_head}_CF_CF3": 1, f"0_2_f": 1},
                },
                f"{acid_head}_anion_C2_F2_BDE": {
                    'reactants': {f"-1_2_{acid_head}_CF2_CF3": 1},
                    'products': {f"-1_1_{acid_head}_CF2_CF2": 1, f"0_2_f": 1},
                },
                f"{acid_head}_anion_C1_F1_BDE": {
                    'reactants': {f"-1_2_{acid_head}_CF3": 1},
                    'products': {f"-1_1_{acid_head}_CF2": 1, f"0_2_f": 1},
                },
            }
            reactions.update(acid_reaction_set)

        # Generate base reactions (currently empty in your original code)
        for base_head in base_heads:
            base_reaction_set = {}  # You can add base reaction definitions here
            reactions.update(base_reaction_set)
            
        return reactions
    
    def get_molecule_data_for_bde_analysis(self):
        """
        Get predefined molecule data for bond dissociation energy analysis.
        
        Returns:
        --------
        list
            List of tuples with molecule information
        """
        return [
            ('HSO3', '0_2', '0_2', '0_1'),
            ('HSO3', '-1_1', '0_2', '-1_2'),
            ('SO3', '-1_2', '0_2', '-1_1'),
            ('SO3', '-2_1', '0_2', '-2_2')
        ]
    
    def get_method_data(self):
        """
        Get predefined computational method information.
        
        Returns:
        --------
        tuple
            Tuple containing functional sets and basis sets dictionaries
        """
        our_functionals = {
            'B3LYP': {'functional': 'B3LYP'},
            'B3LYP-D4': {'functional': 'B3LYP', 'dispersion_correction': 'D4'},
            'M062X': {'functional': 'm062x'},
            'M062X-D3ZERO': {'functional': 'm062x', 'dispersion_correction': 'D3ZERO'},
        }
        
        our_basis_sets = {
            '6-31+Gdp': {'basis': '6-31+G(d,p)'},
            '6-31++Gdp': {'basis': '6-31++G(d,p)'},
            '6-311+Gdp': {'basis': '6-311+G(d,p)'},
            '6-311++Gdp': {'basis': '6-311++G(d,p)'},
        }
        
        other_functionals = {
            'wB97X-D4': {'functional': 'wB97X-D4'},
            'wB97X-V': {'functional': 'wB97X-V'},
            'PW6B95-D4': {'functional': 'PW6B95', 'dispersion_correction': 'D4'},
            'B3LYP-D4': {'functional': 'B3LYP', 'dispersion_correction': 'D4'},
            'M062X-D3ZERO': {'functional': 'M062X', 'dispersion_correction': 'D3ZERO'},
            'B97-D4': {'functional': 'B97', 'dispersion_correction': 'D4'},
            'r2SCAN-D4': {'functional': 'r2SCAN', 'dispersion_correction': 'D4'},
            'revPBE-D4': {'functional': 'revPBE', 'dispersion_correction': 'D4'},
            'OLYP-B4': {'functional': 'OLYP', 'dispersion_correction': 'D4'}
        }
        
        other_basis_sets = {
            'ma-def2-SVp': {'basis': 'ma-def2-SV(P)'},
            'ma-def2-SVP': {'basis': 'ma-def2-SVP'},
            'ma-def2-TZVP': {'basis': 'ma-def2-TZVP'},
            'ma-def2-TZVPP': {'basis': 'ma-def2-TZVPP'},
            'ma-def2-QZVPP': {'basis': 'ma-def2-QZVPP'},
            'def2-SVPD': {'basis': 'def2-SVPD'},
            'def2-TZVPD': {'basis': 'def2-TZVPD'},
            'def2-TZVPPD': {'basis': 'def2-TZVPPD'},
            'def2-QZVPPD': {'basis': 'def2-QZVPPD'},
        }
        
        return (our_functionals, our_basis_sets, other_functionals, other_basis_sets)


# Modify parse_tree.py to handle electronic energy calculations more efficiently
def enhance_parse_tree():
    """
    Function to modify ParseTree class with enhanced energy handling capabilities.
    This would modify the actual ParseTree class if implemented.
    
    NOTE: This is a template for suggested modifications to parse_tree.py
    """
    # Add a new method to ThermoNode class
    def electronic_energy_only(self, data):
        """
        Calculate only electronic energies for reactions.
        
        Parameters:
        -----------
        data : dict
            Dictionary containing energy data
            
        Returns:
        --------
        dict
            Dictionary containing only electronic energy data
        """
        products_label = 'product'
        reactants_label = 'reactant'
        delta_label = 'Delta'
        reaction_data = {}
        
        # Only consider electronic energy
        energy_type = 'E_el_au'
        
        for key in self.coefficients:
            product_or_reactant = self.coefficients[key][0]
            reaction_coefficient = self.coefficients[key][1]
            new_key = f"{product_or_reactant}_{energy_type}"
            energy = self.children[key].data.get(energy_type, None)
            
            if energy and (reaction_data.get(new_key, 0) is not None):
                reaction_data[new_key] = reaction_data.get(new_key, 0) + reaction_coefficient * energy
            else:    
                reaction_data[new_key] = None
        
        product_energy = reaction_data[f"{products_label}_{energy_type}"]
        reactant_energy = reaction_data[f"{reactants_label}_{energy_type}"]
        
        if product_energy and reactant_energy:
            reaction_data[f"{delta_label}_{energy_type}"] = product_energy - reactant_energy
        else:
            reaction_data[f"{delta_label}_{energy_type}"] = np.nan
            
        return reaction_data
