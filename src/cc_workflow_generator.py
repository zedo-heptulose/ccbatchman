"""
CCBatchMan Workflow Generator

This module provides a class-based interface for generating common computational chemistry workflows.
It wraps the input generation functionality of CCBatchMan to make setting up calculations easier.
"""
import input_combi
import os
import sys
import copy
import re
import itertools
from typing import Dict, List, Union, Optional, Tuple, Any, Iterable


# Default configuration templates
DEFAULT_GLOBAL_CONFIG = {
    "num_cores": 8,
    "mem_per_cpu_GB": 4,
    "runtime": "2-00:00:00",
}

DEFAULT_CREST_CONFIG = {
    "program": "CREST",
    "functional": "gfn2",
    "noreftopo": True,
    "runtime": "0-12:00:00",
}

DEFAULT_ORCA_OPTFREQ_CONFIG = {
    "program": "ORCA",
    "integration_grid": "DefGrid3",
    "scf_tolerance": "VeryTightSCF",
    "run_type": "OPT FREQ",
    "!coords_from": "../crest",
    "!xyz_file": "crest_best.xyz",
}

DEFAULT_ORCA_SP_CONFIG = {
    "program": "ORCA",
    "integration_grid": "DefGrid3",
    "scf_tolerance": "VeryTightSCF",
}

DEFAULT_GAUSSIAN_OPTFREQ_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["NoSymm", "Int=Ultrafine"],
    "run_type": "OPT FREQ",
    "!coords_from": "../crest",
    "!xyz_file": "crest_best.xyz",
}

DEFAULT_XTB_OPTFREQ_CONFIG = {
    "program": "XTB",
    "functional": "gfn2",
    "run_type": "ohess",  # opt-freq
    "!coords_from": "../crest",
    "!xyz_file": "crest_best.xyz",
}

class WorkflowGenerator:
    """
    Class for generating and managing computational chemistry workflows.
    """
    
    def __init__(self, root_dir: str = None):
        """
        Initialize the workflow generator.
        
        Parameters:
            root_dir (str): Directory where calculations will be run
        """
        self.root_dir = root_dir
        self.molecule_root = ""
        self.global_config = {"": DEFAULT_GLOBAL_CONFIG.copy()}
        self.batch_runner_config = {"max_jobs": 10, "job_basename": "cc_workflow"}
        self.molecules = {}
        self.cm_states = {}
        self.solvents = {"gas": {"solvent": None}, "!directories": False}
        self.workflow = {}
        # New storage for molecule-CM state associations
        self.molecule_cm_associations = []
        # New flag for tracking atom species (no conformer search)
        self.atom_groups = set()
    
    def set_root_dir(self, root_dir: str) -> 'WorkflowGenerator':
        """
        Set the root directory for calculations.
        
        Parameters:
            root_dir (str): Directory where calculations will be run
            
        Returns:
            self: For method chaining
        """
        self.root_dir = root_dir
        return self
    
    def set_molecule_root(self, molecule_root: str) -> 'WorkflowGenerator':
        """
        Set the base directory for all molecule files.
        
        Parameters:
            molecule_root (str): Base directory containing all molecule subdirectories
            
        Returns:
            self: For method chaining
        """
        self.molecule_root = molecule_root
        return self
    
    def set_global_config(self, config: Dict) -> 'WorkflowGenerator':
        """
        Set global configuration settings.
        
        Parameters:
            config (dict): Global configuration settings
            
        Returns:
            self: For method chaining
        """
        self.global_config = {"": config} if "" not in config else config
        return self
    
    def set_batch_runner_config(self, config: Dict) -> 'WorkflowGenerator':
        """
        Set batch runner configuration.
        
        Parameters:
            config (dict): Batch runner configuration
            
        Returns:
            self: For method chaining
        """
        self.batch_runner_config = config
        return self
    
    def add_molecules_from_directory(self, directory: str, group_name: str = None) -> 'WorkflowGenerator':
        """
        Add molecules from a directory.
        
        Parameters:
            directory (str): Directory containing XYZ files
            group_name (str): Optional name for this group of molecules
            
        Returns:
            self: For method chaining
        """
        molecules = input_combi.xyz_files_from_directory(directory)
        molecules['!directories'] = True
        
        if group_name:
            self.molecules[group_name] = molecules
        else:
            self.molecules.update(molecules)
        
        return self
    
    def add_molecules(self, directory: str, cm_states_group: str, 
                     atoms: bool = False, group_name: str = None) -> 'WorkflowGenerator':
        """
        Add molecules from a directory and associate them with a charge-multiplicity group.
        
        Parameters:
            directory (str): Directory containing XYZ files (relative to molecule_root)
            cm_states_group (str): Name of the CM states group to associate with these molecules
            atoms (bool): Whether these are atomic species (skips conformer search)
            group_name (str): Optional custom name for this group (defaults to directory name)
            
        Returns:
            self: For method chaining
        """
        full_path = os.path.join(self.molecule_root, directory)
        molecules = input_combi.xyz_files_from_directory(full_path)
        molecules['!directories'] = True
        
        # Use directory name as group name if not provided
        if not group_name:
            group_name = os.path.basename(directory)
        
        # Store the molecules
        self.molecules[group_name] = molecules
        
        # Add to molecule-CM associations
        self.molecule_cm_associations.append((group_name, cm_states_group))
        
        # Track if these are atoms (no conformer search needed)
        if atoms:
            self.atom_groups.add(group_name)
        
        return self
    
    def add_cm_states(self, cm_state_configs, group_name=None):
        """
        Add charge-multiplicity states with additional configuration options.
        
        Parameters:
            cm_state_configs (list): List of configurations in one of these formats:
                - (charge, multiplicity) tuple
                - (charge, multiplicity, alias) tuple
                - dict with keys for 'charge', 'multiplicity', 'alias' (optional),
                  'uks' (optional), 'broken_symmetry' (optional)
            group_name (str): Optional name for this group of CM states
                
        Returns:
            self: For method chaining
        """
        cm_states = {}
        
        for config in cm_state_configs:
            if isinstance(config, tuple):
                if len(config) == 2:
                    charge, multiplicity = config
                    alias = f"{charge}_{multiplicity}"
                    settings = self._get_charge_multiplicity_settings(charge, multiplicity)
                elif len(config) == 3:
                    charge, multiplicity, alias = config
                    settings = self._get_charge_multiplicity_settings(charge, multiplicity)
                else:
                    raise ValueError(f"Invalid CM state tuple format: {config}")
            elif isinstance(config, dict):
                charge = config['charge']
                multiplicity = config['multiplicity']
                alias = config.get('alias', f"{charge}_{multiplicity}")
                uks = config.get('uks', None)
                # uhf = config.get('uhf', None) #implement this when we get a chance...
                broken_symmetry = config.get('broken_symmetry', False)
                settings = self._get_charge_multiplicity_settings(
                    charge, multiplicity, uks, broken_symmetry)
            else:
                raise ValueError(f"Invalid CM state format: {config}")
            
            cm_states[alias] = settings
        
        if group_name:
            self.cm_states[group_name] = cm_states
        else:
            self.cm_states.update(cm_states)
        
        return self
        
    def set_solvents(self, solvent_names: List[str] = None,split_directories=False) -> 'WorkflowGenerator':
        """
        Set solvents.
        
        Parameters:
            solvent_names (list): List of solvent names
            
        Returns:
            self: For method chaining
        """
        solvents = {}
        
        # Add requested solvents
        if solvent_names:
            for name in solvent_names:
                if name == "gas":
                    solvents["gas"] = {"solvent": None}
                else:
                    solvents[name] = {"solvent": name}
        
        solvents["!directories"] = split_directories #maybe add a kwarg for this later
        self.solvents = solvents
        
        return self
    
    def add_crest_step(self, name: str = "crest", 
                     config_overrides: Dict = None) -> 'WorkflowGenerator':
        """
        Add a CREST conformer search step to the workflow.
        
        Parameters:
            name (str): Name for this step
            config_overrides (dict): Settings to override defaults
            
        Returns:
            self: For method chaining
        """
        crest_config = copy.deepcopy(DEFAULT_CREST_CONFIG)
        
        if config_overrides:
            crest_config.update(config_overrides)
        
        self.workflow[name] = crest_config
        return self
    
    def add_xtb_optfreq_step(self, name: str = "xtb_gfn2_opt_freq", 
                           config_overrides: Dict = None,
                           coords_source: str = "crest") -> 'WorkflowGenerator':
        """
        Add an xTB geometry optimization and frequency calculation step.
        
        Parameters:
            name (str): Name for this step
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            
        Returns:
            self: For method chaining
        """
        xtb_config = copy.deepcopy(DEFAULT_XTB_OPTFREQ_CONFIG)
        
        if coords_source:
            xtb_config["!coords_from"] = f"../{coords_source}"
        
        if config_overrides:
            xtb_config.update(config_overrides)
        
        self.workflow[name] = xtb_config
        return self
    
    def add_orca_optfreq_step(self, name: str, functional: str,
                            basis: str = None, dispersion: str = None,
                            config_overrides: Dict = None,
                            coords_source: str = "crest") -> 'WorkflowGenerator':
        """
        Add an ORCA geometry optimization and frequency calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            dispersion (str): Dispersion correction (e.g., 'D3', 'D4')
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            
        Returns:
            self: For method chaining
        """
        orca_config = copy.deepcopy(DEFAULT_ORCA_OPTFREQ_CONFIG)
        
        # Set the functional, basis, and dispersion
        orca_config["functional"] = functional
        
        if basis:
            orca_config["basis"] = basis
        
        if dispersion:
            orca_config["dispersion_correction"] = dispersion
        
        # Set coordinate source if provided
        if coords_source:
            orca_config["!coords_from"] = f"../{coords_source}"
            orca_config["!xyz_file"] = f"{coords_source}.xyz"
        
        # Override with any user settings
        if config_overrides:
            orca_config.update(config_overrides)
        
        self.workflow[name] = orca_config
        return self
    
    def add_orca_sp_step(self, name: str, functional: str, basis: str,
                       dispersion: str = None, config_overrides: Dict = None,
                       coords_source: str = None) -> 'WorkflowGenerator':
        """
        Add an ORCA single point calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            dispersion (str): Dispersion correction (e.g., 'D3', 'D4')
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            
        Returns:
            self: For method chaining
        """
        orca_config = copy.deepcopy(DEFAULT_ORCA_SP_CONFIG)
        
        # Set the functional, basis, and dispersion
        orca_config["functional"] = functional
        orca_config["basis"] = basis
        
        if dispersion:
            orca_config["dispersion_correction"] = dispersion
        
        # Set coordinate source if provided
        if coords_source:
            orca_config["!coords_from"] = f"../{coords_source}"
            orca_config["!xyz_file"] = f"{coords_source}.xyz"
        
        # Override with any user settings
        if config_overrides:
            orca_config.update(config_overrides)
        
        self.workflow[name] = orca_config
        return self
    
    def add_gaussian_optfreq_step(self, name: str, functional: str, basis: str,
                                config_overrides: Dict = None,
                                coords_source: str = "crest") -> 'WorkflowGenerator':
        """
        Add a Gaussian geometry optimization and frequency calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            
        Returns:
            self: For method chaining
        """
        gaussian_config = copy.deepcopy(DEFAULT_GAUSSIAN_OPTFREQ_CONFIG)
        
        # Set the functional and basis
        gaussian_config["functional"] = functional
        gaussian_config["basis"] = basis
        
        # Set coordinate source if provided
        if coords_source:
            gaussian_config["!coords_from"] = f"../{coords_source}"
            gaussian_config["!xyz_file"] = f"{coords_source}.xyz"
        
        # Override with any user settings
        if config_overrides:
            gaussian_config.update(config_overrides)
        
        self.workflow[name] = gaussian_config
        return self

                
    def split_theory_name(self,theory):
        """
        Function used for processing str or tuple level of theory specifications
        """
        if theory is None:
            return None, None
            
        if isinstance(theory,tuple):
            theory_name = theory[0]
            theory = theory[1]
        elif isinstance(theory,str):
            theory_name = theory.lower()
        else:
            raise ValueError("Invalid data type for theory")
    
        if theory_name:
            theory_name = re.sub(r'[)(,]','',theory_name)

        return theory_name, theory
    
    def create_multi_theory_workflow(self, 
                                   optfreq_functionals: List[Union[str,tuple]] = None,
                                   optfreq_basis_sets: List[Union[str,tuple]] = None,
                                   sp_functionals: List[Union[str,tuple]] = None,
                                   sp_basis_sets: List[Union[str,tuple]] = None,
                                   program: str = "ORCA",
                                   include_crest: bool = True,
                                   crest_overrides: Dict = None,
                                   optfreq_overrides: Dict = None,
                                   sp_overrides: Dict = None,
                                   name_suffix: str = None,
                                    ) -> 'WorkflowGenerator':
        """
        Create multiple workflows using cartesian product of functionals/basis sets.
        
        Parameters:
            optfreq_functionals (list): List of functionals for geometry optimization
            optfreq_basis_sets (list): List of basis sets for geometry optimization
            sp_functionals (list): List of functionals for single point energy 
            sp_basis_sets (list): List of basis sets for single point energy
                all of functional/basis sets can be given as tuple (name,functional)
                or as str "functional" within list
            program (str): Program to use ('ORCA', 'Gaussian', or 'XTB')
            include_crest (bool): Whether to include a CREST conformer search step
            crest_overrides (dict): Settings to override CREST defaults
            optfreq_overrides (dict): Settings to override optfreq defaults
            sp_overrides (dict): Settings to override single point defaults
            
        Returns:
            self: For method chaining
        """
        # Add CREST if requested
        if include_crest:
            self.add_crest_step("crest", crest_overrides)
            coords_source = "crest"
        else:
            coords_source = None
        
        # Default to lists with one element if not provided
        if not optfreq_functionals:
            optfreq_functionals = ["r2SCAN-3c"]
        
        if not optfreq_basis_sets:
            optfreq_basis_sets = [None]  # None for compound methods like r2SCAN-3c
        
        # Add geometry optimization and frequency calculations
        for functional, basis in itertools.product(optfreq_functionals, optfreq_basis_sets):
            # Skip None basis for functionals that require a basis
            if basis is None and not (functional.endswith("-3c") or functional.endswith("-2c")):
                continue

            functional_name,functional = self.split_theory_name(functional)
            basis_name, basis = self.split_theory_name(basis)

            optfreq_name = f"{functional_name}"
            if basis:
                optfreq_name += f"_{basis_name}"
            optfreq_name += "_opt_freq"

            if name_suffix:
                optfreq_name += f"_{name_suffix}"
            if program.upper() == "ORCA":
                self.add_orca_optfreq_step(
                    optfreq_name, functional,
                    basis=basis,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif program.upper() == "GAUSSIAN":
                optfreq_name += '_gaussian'
                self.add_gaussian_optfreq_step(
                    optfreq_name, functional, 
                    basis=basis or "6-31G(d,p)",  # Default for Gaussian
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif program.upper() == "XTB":
                self.add_xtb_optfreq_step(
                    optfreq_name,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            
            # Add single point calculations for this geometry
            if sp_functionals and sp_basis_sets:
                for sp_func, sp_basis in itertools.product(sp_functionals, sp_basis_sets):
                    sp_func_name,sp_func = self.split_theory_name(sp_func)
                    sp_basis_name,sp_basis = self.split_theory_name(sp_basis)
                    sp_name = f"{sp_func_name}_{sp_basis_name}_sp_{functional_name}_{basis_name}"
                    
                if name_suffix:
                    sp_name += f"_{name_suffix}"
                    #we use this verbose naming convention because ah... life easy
                    self.add_orca_sp_step(
                        sp_name, sp_func, sp_basis,
                        config_overrides=sp_overrides,
                        coords_source=optfreq_name
                    )
        
        return self
    
    def _modify_workflow_for_atoms(self, workflow):
        """
        Modify workflow steps to remove CREST for atoms.
        
        Parameters:
            workflow (dict): The workflow to modify
            
        Returns:
            dict: Modified workflow
        """
        # Create a copy to avoid modifying the original
        modified_workflow = copy.deepcopy(workflow)
        
        # Remove CREST step if it exists
        for key in list(modified_workflow.keys()):
            if key.startswith("crest"):
                del modified_workflow[key]
        
        # Modify other steps to not depend on CREST
        for key, config in modified_workflow.items():
            if "!coords_from" in config:
                config["!coords_from"] = None
            if "!xyz_file" in config:
                config["!xyz_file"] = None  # Use the original XYZ file
            config['num_cores'] = 1 #pretty much always necessary for atom jobs.
            #might turn out to be an edge case for heavy atoms but we don't really use those
        return modified_workflow
    
    def run(self,overwrite=False) -> None:
        """
        Run the workflow using the molecule-CM state associations.

        Args:
            overwrite - one of True, "all", "input_files_only"
                True overwrites only failed or not started jobs
                "all" overwrites all jobs
                "input_files_only" overwrites input files without deleting contents of directory
                (useful for restarting failed jobs)
        Returns:
            None
        """
        self.global_config[""].update({'!overwrite':overwrite})
        if not self.root_dir:
            raise ValueError("Root directory not set")
        
        if not self.workflow:
            raise ValueError("No workflow defined")
        
        # If no associations were created, use all molecules with all CM states
        if not self.molecule_cm_associations:
            input_list = [self.global_config, self.solvents, self.cm_states, self.molecules, self.workflow]
            input_combi.do_everything(self.root_dir, self.batch_runner_config, input_list)
            return
        
        # Process each molecule-CM association separately
        for mol_group, cm_group in self.molecule_cm_associations:
            # Get the molecules for this group
            if mol_group in self.molecules:
                molecules = self.molecules[mol_group]
                molecules = {re.sub('[)(-]','_',key) : value for key,value in molecules.items()}
            else:
                raise ValueError(f"Molecule group '{mol_group}' not found")
            
            # Get the CM states for this group
            if cm_group in self.cm_states:
                cm_states = self.cm_states[cm_group]
            else:
                raise ValueError(f"CM states group '{cm_group}' not found")
            
            # Check if this is an atom group (skip CREST)
            workflow = self.workflow
            if mol_group in self.atom_groups:
                workflow = self._modify_workflow_for_atoms(workflow)
            
            # Create the input list
            input_list = [self.global_config, self.solvents, cm_states, molecules, workflow]
            
            # Run the workflow for this combination
            input_combi.do_everything(
                self.root_dir,
                self.batch_runner_config,
                input_list
            )
    
    def _get_charge_multiplicity_settings(self, charge=0, multiplicity=1, uks=None,broken_symmetry=False):
        """
        Generate charge and multiplicity settings.
        
        Parameters:
            charge (int): Molecular charge
            multiplicity (int): Spin multiplicity (2S+1)
            uks (bool): Whether to use unrestricted Kohn-Sham (UKS)
            
        Returns:
            dict: Dictionary with charge and multiplicity settings
        """
        # Determine UKS setting if not specified
        if uks is None:
            uks = multiplicity > 1
            
        return {
            "charge": charge,
            "spin_multiplicity": multiplicity,
            "uks": uks,
            "broken_symmetry" : broken_symmetry,
        }



    
    # def create_standard_workflow(self, optfreq_functional: str,
    #                            sp_functional: str = None, sp_basis: str = None,
    #                            program: str = "ORCA", name: str = "",
    #                            optfreq_basis: str = None, optfreq_dispersion: str = None,
    #                            sp_dispersion: str = None,
    #                            include_crest: bool = True,
    #                            crest_overrides: Dict = None,
    #                            optfreq_overrides: Dict = None,
    #                            sp_overrides: Dict = None) -> 'WorkflowGenerator':
    #     """
    #     Create a standard computational chemistry workflow: CREST → OptFreq → SinglePoint.
        
    #     Parameters:
    #         optfreq_functional (str): Functional for geometry optimization and frequencies
    #         sp_functional (str): Functional for single point energy (optional)
    #         sp_basis (str): Basis set for single point energy (optional, required if sp_functional provided)
    #         program (str): Program to use ('ORCA', 'Gaussian', or 'XTB')
    #         name (str): Base name for the method steps
    #         optfreq_basis (str): Basis set for geometry optimization (for some methods)
    #         optfreq_dispersion (str): Dispersion correction for geometry optimization
    #         sp_dispersion (str): Dispersion correction for single point
    #         include_crest (bool): Whether to include a CREST conformer search step
    #         crest_overrides (dict): Settings to override CREST defaults
    #         optfreq_overrides (dict): Settings to override optfreq defaults
    #         sp_overrides (dict): Settings to override single point defaults
            
    #     Returns:
    #         self: For method chaining
    #     """
    #     # Add CREST if requested
    #     if include_crest:
    #         crest_name = f"crest_{name}" if name else "crest"
    #         self.add_crest_step(crest_name, crest_overrides)
    #         coords_source = crest_name
    #     else:
    #         coords_source = None
        
    #     # Add geometry optimization and frequency calculation
    #     optfreq_name = f"{optfreq_functional.lower().replace('-', '_')}_{name}_opt_freq" if name else f"{optfreq_functional.lower().replace('-', '_')}_opt_freq"
        
    #     if program.upper() == "ORCA":
    #         self.add_orca_optfreq_step(
    #             optfreq_name, optfreq_functional,
    #             basis=optfreq_basis, dispersion=optfreq_dispersion,
    #             config_overrides=optfreq_overrides,
    #             coords_source=coords_source
    #         )
    #     elif program.upper() == "GAUSSIAN":
    #         # optfreq_name += '_gaussian'
    #         self.add_gaussian_optfreq_step(
    #             optfreq_name, optfreq_functional, 
    #             basis=sp_basis if optfreq_basis is None else optfreq_basis,
    #             config_overrides=optfreq_overrides,
    #             coords_source=coords_source
    #         )
    #     elif program.upper() == "XTB":
    #         self.add_xtb_optfreq_step(
    #             optfreq_name,
    #             config_overrides=optfreq_overrides,
    #             coords_source=coords_source
    #         )
    #     else:
    #         raise ValueError(f"Unsupported program: {program}")
        
    #     # Add single point calculation if requested
    #     if sp_functional and sp_basis:
    #         sp_name = f"{sp_functional.lower().replace('-', '_')}_{sp_basis.lower().replace('-', '_')}_{name}_sp" if name else f"{sp_functional.lower().replace('-', '_')}_{sp_basis.lower().replace('-', '_')}_sp"
            
    #         self.add_orca_sp_step(
    #             sp_name, sp_functional, sp_basis,
    #             dispersion=sp_dispersion,
    #             config_overrides=sp_overrides,
    #             coords_source=optfreq_name
    #         )
        
    #     return self

