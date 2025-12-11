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
    "noreftopo": False,
    "runtime": "0-12:00:00",
}

DEFAULT_ORCA_OPTFREQ_CONFIG = {
    "program": "ORCA",
    "integration_grid": "DefGrid3",
    "scf_tolerance": "VeryTightSCF",
    "run_type": "OPT FREQ",
    #TODO - FIGURE OUT AUTOAUX
}

DEFAULT_ORCA_SP_CONFIG = {
    "program": "ORCA",
    "integration_grid": "DefGrid3",
    "scf_tolerance": "VeryTightSCF",
}

DEFAULT_GAUSSIAN_OPTFREQ_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["Int=Ultrafine"],
    "run_type": "OPT FREQ",
}

DEFAULT_GAUSSIAN_SP_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["Int=Ultrafine"],
    "run_type": None,
}

DEFAULT_GAUSSIAN_NICS_PREPROCESSING_CONFIG = {
    'num_cores' : 1,
    'mem_per_cpu_GB' : 3,
    'runtime' : '0-00:05:00',
    'program'  : 'pyAroma',
    'cc_program' : 'Gaussian',
}

DEFAULT_GAUSSIAN_NICS_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["Int=Ultrafine"],
    "run_type": "NMR=GIAO",
}

DEFAULT_GAUSSIAN_AICD_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["int=Ultrafine"],
    "run_type": "scf=tight nmr=csgt iop(10/93=1)",
    "post_submit_lines": [
          "conda activate AICD",
          "AICD -m 2 -s -rot 0 0 0 -b -1 0 0 -p 200000 --scale 0.25 --resolution 4096 3072 --maxarrowlength 1.5 -runpov *log"
    ],
    "post_coords_line" : 'AICD_temp.txt' #new
}

DEFAULT_XTB_OPTFREQ_CONFIG = {
    "program": "XTB",
    "functional": "gfn2",
    "run_type": "ohess",  # opt-freq
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
                     atoms: bool = False, group_name: str = None,
                     exclude: str = None) -> 'WorkflowGenerator':
        """
        Add molecules from a directory and associate them with a charge-multiplicity group.
        
        Parameters:
            directory (str): Directory containing XYZ files (relative to molecule_root)
            cm_states_group (str): Name of the CM states group to associate with these molecules
            atoms (bool): Whether these are atomic species (skips conformer search)
            group_name (str): Optional custom name for this group (defaults to directory name)
            exclude (str): Optional, ignore .xyz files containing this substring
            
        Returns:
            self: For method chaining
        """
        full_path = os.path.join(self.molecule_root, directory)
        molecules = input_combi.xyz_files_from_directory(full_path)
        if exclude:
            molecules = {key : value for key,value in molecules.items() if not exclude in key}
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
                mix_guess = config.get('mix_guess',False)
                settings = self._get_charge_multiplicity_settings(
                    charge, multiplicity, uks, broken_symmetry,mix_guess)
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
                            coords_source: str = "crest",
                            xyz_filename = None) -> 'WorkflowGenerator':
        """
        Add an ORCA geometry optimization and frequency calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            dispersion (str): Dispersion correction (e.g., 'D3', 'D4')
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            
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
            if xyz_filename:
                orca_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                orca_config["!xyz_file"] = f"crest_best.xyz"
            else:
                orca_config["!xyz_file"] = f"{coords_source}.xyz"
                
        
        # Override with any user settings
        if config_overrides:
            orca_config.update(config_overrides)
        
        self.workflow[name] = orca_config
        return self
    
    def add_orca_sp_step(self, name: str, functional: str, basis: str,
                       dispersion: str = None, config_overrides: Dict = None,
                       coords_source: str = None,xyz_filename=None) -> 'WorkflowGenerator':
        """
        Add an ORCA single point calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            dispersion (str): Dispersion correction (e.g., 'D3', 'D4')
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            
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
            if xyz_filename:
                orca_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                orca_config["!xyz_file"] = f"crest_best.xyz"
            else:
                orca_config["!xyz_file"] = f"{coords_source}.xyz"
                
        # Override with any user settings
        if config_overrides:
            orca_config.update(config_overrides)
        
        self.workflow[name] = orca_config
        return self
    
    def add_gaussian_optfreq_step(self, name: str, functional: str, basis: str,
                                config_overrides: Dict = None,
                                coords_source: str = "crest",xyz_filename=None) -> 'WorkflowGenerator':
        """
        Add a Gaussian geometry optimization and frequency calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            
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
            if xyz_filename:
                gaussian_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                gaussian_config["!xyz_file"] = f"crest_best.xyz"
            else:
                gaussian_config["!xyz_file"] = f"{coords_source}.xyz"
        
        # Override with any user settings
        if config_overrides:
            gaussian_config.update(config_overrides)
        
        self.workflow[name] = gaussian_config
        return self


    def add_gaussian_sp_step(self, name: str, functional: str, basis: str,
                       config_overrides: Dict = None,
                       coords_source: str = None,xyz_filename=None) -> 'WorkflowGenerator':
        """
        Add a Gaussian single point calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            
        Returns:
            self: For method chaining
        """
        gaussian_config = copy.deepcopy(DEFAULT_GAUSSIAN_SP_CONFIG)
        
        # Set the functional, basis, and dispersion
        gaussian_config["functional"] = functional
        gaussian_config["basis"] = basis
        
        # Set coordinate source if provided
        if coords_source:
            gaussian_config["!coords_from"] = f"../{coords_source}"
            if xyz_filename:
                gaussian_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                gaussian_config["!xyz_file"] = f"crest_best.xyz"
            else:
                gaussian_config["!xyz_file"] = f"{coords_source}.xyz"
                
        # Override with any user settings
        if config_overrides:
            gaussian_config.update(config_overrides)
        
        self.workflow[name] = gaussian_config
        return self

    
    
    def add_gaussian_nics_step(self, name: str, functional: str, basis: str,
                       dispersion: str = None, config_overrides: Dict = None,
                       coords_source: str = None,xyz_filename=None, preprocessing_name: str = None) -> 'WorkflowGenerator':
        """
        Add an Gaussian NICS calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            dispersion (str): Dispersion correction (e.g., 'D3', 'D4')
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            preprocessing_name (str): Name for preprocessing step 
            
        Returns:
            self: For method chaining
        """
        # set up preprocessing step
        nics_preprocessing_config = copy.deepcopy(DEFAULT_GAUSSIAN_NICS_PREPROCESSING_CONFIG)
    
        # coords actually have to go to this instead of the run itself
        # this adds the ghost atoms Gaussian will use to calculate NICS values
        if coords_source:
            nics_preprocessing_config["!coords_from"] = f"../{coords_source}"
            if xyz_filename:
                nics_preprocessing_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                nics_preprocessing_config["!xyz_file"] = f"crest_best.xyz"
            else:
                nics_preprocessing_config["!xyz_file"] = f"{coords_source}.xyz"
    
        # set name used for this run, also for xyz file it generates
        if not preprocessing_name:
            preprocessing_name = "gaussian_nics_preprocessing"
            
        self.workflow[preprocessing_name] = nics_preprocessing_config
        
        gaussian_config = copy.deepcopy(DEFAULT_GAUSSIAN_NICS_CONFIG)
        
        # Set the functional, basis, and dispersion
        gaussian_config["functional"] = functional
        gaussian_config["basis"] = basis
        
        if dispersion:
            gaussian_config["dispersion_correction"] = dispersion
        
        
        # Override with any user settings
        if config_overrides:
            gaussian_config.update(config_overrides)
    
        # set coordinate source for actual run to coords from preprocessing step
        gaussian_config["!coords_from"] = f"../{preprocessing_name}"
        # pretty sure this should work, will need testing
        gaussian_config["!xyz_file"] = f"{preprocessing_name}.xyz"
            
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


    def add_gaussian_aicd_step(self, name: str, functional: str, basis: str,
                       config_overrides: Dict = None,
                       coords_source: str = None,xyz_filename=None) -> 'WorkflowGenerator':
        """
        Add a Gaussian single point calculation step.
        
        Parameters:
            name (str): Name for this step
            functional (str): DFT functional name
            basis (str): Basis set name
            config_overrides (dict): Settings to override defaults
            coords_source (str): Source for coordinates
            xyz_filename (str): Filename of .xyz file for use with coords_source
            
        Returns:
            self: For method chaining
        """
        gaussian_config = copy.deepcopy(DEFAULT_GAUSSIAN_AICD_CONFIG)
        
        # Set the functional, basis, and dispersion
        gaussian_config["functional"] = functional
        gaussian_config["basis"] = basis
        
        # Set coordinate source if provided
        if coords_source:
            gaussian_config["!coords_from"] = f"../{coords_source}"
            if xyz_filename:
                gaussian_config["!xyz_file"] = f"{xyz_filename}.xyz"
            elif coords_source == 'crest':
                gaussian_config["!xyz_file"] = f"crest_best.xyz"
            else:
                gaussian_config["!xyz_file"] = f"{coords_source}.xyz"
                
        # Override with any user settings
        if config_overrides: # watch that we aren't overwriting the IOP keyword
            gaussian_config.update(config_overrides)
        
        self.workflow[name] = gaussian_config
        return self


    
    def create_multi_theory_workflow(self, 
                       optfreq_functionals: List[Union[str,tuple]] = None,
                       optfreq_basis_sets: List[Union[str,tuple]] = None,
                       sp_functionals: List[Union[str,tuple]] = None,
                       sp_basis_sets: List[Union[str,tuple]] = None,
                       nics_functionals: List[Union[str,tuple]] = None,
                       nics_basis_sets: List[Union[str,tuple]] = None,
                       program: str = "ORCA",
                       optfreq_program: str = None,
                       sp_program: str = "ORCA",
                       nics_program: str = "Gaussian",
                       do_crest: bool = True,
                       crest_overrides: Dict = None,
                       optfreq_overrides: Dict = None,
                       sp_overrides: Dict = None,
                       nics_overrides: Dict = None,
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
            optfreq_program: Program to use for optimization + frequency step
            sp_program: Program to use for singlepoint step
            nics_program: Program to use for NICS step
            do_crest (bool): Whether to include a CREST conformer search step
            crest_overrides (dict): Settings to override CREST defaults
            optfreq_overrides (dict): Settings to override optfreq defaults
            sp_overrides (dict): Settings to override single point defaults
            
        Returns:
            self: For method chaining
        """
        optfreq_program = optfreq_program if optfreq_program else program
        sp_program = sp_program if sp_program else program
        
        # Add CREST if requested
        
        if do_crest:
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
                
            if optfreq_program.upper() == "ORCA":
                self.add_orca_optfreq_step(
                    optfreq_name, functional,
                    basis=basis,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif optfreq_program.upper() == "GAUSSIAN":
                optfreq_name += '_gaussian'
                self.add_gaussian_optfreq_step(
                    optfreq_name, functional, 
                    basis=basis or "6-31G(d,p)",  # Default for Gaussian
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif optfreq_program.upper() == "XTB":
                self.add_xtb_optfreq_step(
                    optfreq_name,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            else:
                raise ValueError(f"Invalid program specified for opt/freq step: {optfreq_program}")
            
            # Add single point calculations for this geometry
            if sp_functionals and sp_basis_sets:
                for sp_func, sp_basis in itertools.product(sp_functionals, sp_basis_sets):
                    sp_func_name,sp_func = self.split_theory_name(sp_func)
                    sp_basis_name,sp_basis = self.split_theory_name(sp_basis)
                    sp_name = f"{sp_func_name}_{sp_basis_name}_sp_{functional_name}_{basis_name}"
                    
                    if name_suffix:
                        sp_name += f"_{name_suffix}"
                        #we use this verbose naming convention because ah... life easy
                        #we're fine just using ORCA for singlepoints at the moment, I don't
                        #mind that.
                    if sp_program.upper() == "ORCA":
                        self.add_orca_sp_step( 
                            sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                    elif sp_program.upper() == "GAUSSIAN":
                        sp_name += '_gaussian'
                        self.add_gaussian_sp_step(
                            sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                    else:
                        raise ValueError('singlepoint requested for program other than ORCA or Gaussian')
                        
            # add NICS calculations for this geometry
            if nics_functionals and nics_basis_sets:
                for nics_func, nics_basis in itertools.product(nics_functionals, nics_basis_sets):
                    nics_func_name,nics_func = self.split_theory_name(nics_func)
                    nics_basis_name,nics_basis = self.split_theory_name(nics_basis)
                    nics_name = f"{nics_func_name}_{nics_basis_name}_NICS_{functional_name}_{basis_name}"

                    if name_suffix:
                        nics_name += f"_{name_suffix}"

                    if nics_program.upper() == "GAUSSIAN":
                        self.add_gaussian_nics_step( 
                            nics_name, nics_func, nics_basis,
                            config_overrides=nics_overrides,
                            coords_source=optfreq_name
                        )
                    else:
                        raise ValueError('NICS calculation only available for Gaussian')
                    
        return self



###################################################333


    # bs function



################################################3





    def create_diradical_workflow(self, 
                       optfreq_functionals: List[Union[str,tuple]] = None,
                       optfreq_basis_sets: List[Union[str,tuple]] = None,
                       sp_functionals: List[Union[str,tuple]] = None,
                       sp_basis_sets: List[Union[str,tuple]] = None,
                       nics_functionals: List[Union[str,tuple]] = None,
                       nics_basis_sets: List[Union[str,tuple]] = None,
                       aicd_functionals: List[Union[str,tuple]] = None,
                       aicd_basis_sets: List[Union[str,tuple]] = None,
                       program: str = "ORCA",
                       optfreq_program: str = None,
                       sp_program: str = "ORCA",
                       nics_program: str = "Gaussian",
                       aicd_program: str = "Gaussian",
                       do_crest: bool = True,
                       crest_overrides: Dict = None,
                       optfreq_overrides: Dict = None,
                       sp_overrides: Dict = None,
                       nics_overrides: Dict = None,
                       aicd_overrides: Dict = None,
                       name_suffix: str = None,
                        ) -> 'WorkflowGenerator':
        """
        Create multiple workflows using cartesian product of functionals/basis sets.
        
        Parameters:
            optfreq_functionals (list): List of functionals for geometry optimization
            optfreq_basis_sets (list): List of basis sets for geometry optimization
            sp_functionals (list): List of functionals for single point energy 
            sp_basis_sets (list): List of basis sets for single point energy
            nics_functionals (list): List of functionals for NICS
            nics_basis_sets (list): List of basis sets for NICS
            aicd_functionals (list): List of functionals for AICD
            aicd_basis_sets (list): List of basis sets for AICD
            
            all of functional/basis sets can be given as tuple (name,functional)
                or as str "functional" within list
            program (str): Program to use ('ORCA', 'Gaussian', or 'XTB')
            optfreq_program: Program to use for optimization + frequency step
            sp_program: Program to use for singlepoint step
            nics_program: Program to use for NICS step
            aicd_program: Program to use for AICD step
            
            do_crest (bool): Whether to include a CREST conformer search step
            crest_overrides (dict): Settings to override CREST defaults
            optfreq_overrides (dict): Settings to override optfreq defaults
            sp_overrides (dict): Settings to override single point defaults
            nics_overrides (dict): Settings to override NICS defaults
            aicd_overrides (dict) Settings to override AICD defaults
        Returns:
            self: For method chaining
        """
        optfreq_program = optfreq_program if optfreq_program else program
        sp_program = sp_program if sp_program else program
        
        # Add CREST if requested
        
        if do_crest:
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
                
            if optfreq_program.upper() == "ORCA":
                self.add_orca_optfreq_step(
                    optfreq_name, functional,
                    basis=basis,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif optfreq_program.upper() == "GAUSSIAN":
                optfreq_name += '_gaussian'
                self.add_gaussian_optfreq_step(
                    optfreq_name, functional, 
                    basis=basis or "6-31G(d,p)",  # Default for Gaussian
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            elif optfreq_program.upper() == "XTB":
                self.add_xtb_optfreq_step(
                    optfreq_name,
                    config_overrides=optfreq_overrides,
                    coords_source=coords_source
                )
            else:
                raise ValueError(f"Invalid program specified for opt/freq step: {optfreq_program}")
            
            # Add single point calculations for this geometry
            if sp_functionals and sp_basis_sets:
                for sp_func, sp_basis in itertools.product(sp_functionals, sp_basis_sets):
                    sp_func_name,sp_func = self.split_theory_name(sp_func)
                    sp_basis_name,sp_basis = self.split_theory_name(sp_basis)
                    sp_name = f"{sp_func_name}_{sp_basis_name}_sp_{functional_name}_{basis_name}"
                    
                    if name_suffix:
                        sp_name += f"_{name_suffix}"
                        #we use this verbose naming convention because ah... life easy
                        #we're fine just using ORCA for singlepoints at the moment, I don't
                        #mind that.
                    if sp_program.upper() == "ORCA":
                        ####singlet sp
                        overrides = {
                            'charge': 0,
                            'spin_multiplicity' : 3,
                            'broken_symmetry' : True,
                        }
                        sp_overrides.update(overrides)
                        singlet_sp_name = sp_name+'_singlet'
                        self.add_orca_sp_step( 
                            singlet_sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                        ####triplet sp
                        overrides = {
                            'charge': 0,
                            'spin_multiplicity' : 3,
                            'broken_symmetry' : False,
                        }
                        sp_overrides.update(overrides)
                        triplet_sp_name = sp_name+'_triplet'
                        self.add_orca_sp_step( 
                            triplet_sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                        
                    elif sp_program.upper() == "GAUSSIAN":
                        ####singlet sp
                        overrides = {
                            'charge': 0,
                            'spin_multiplicity' : 1,
                            'broken_symmetry' : False,
                            'mix_guess' : True,
                        }
                        sp_overrides.update(overrides)
                        singlet_sp_name = sp_name+'_singlet'
                        singlet_sp_name += '_gaussian'
                        self.add_gaussian_sp_step(
                            singlet_sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                        ####triplet sp
                        overrides = {
                            'charge': 0,
                            'spin_multiplicity' : 3,
                            'broken_symmetry' : False,
                            'mix_guess' : False,
                        }
                        sp_overrides.update(overrides)
                        triplet_sp_name = sp_name+'_triplet'
                        triplet_sp_name += '_gaussian'
                        self.add_gaussian_sp_step(
                            triplet_sp_name, sp_func, sp_basis,
                            config_overrides=sp_overrides,
                            coords_source=optfreq_name
                        )
                    
                    else:
                        raise ValueError('singlepoint requested for program other than ORCA or Gaussian')
                        
            # add NICS calculations for this geometry
            if nics_functionals and nics_basis_sets:
                for nics_func, nics_basis in itertools.product(nics_functionals, nics_basis_sets):
                    nics_func_name,nics_func = self.split_theory_name(nics_func)
                    nics_basis_name,nics_basis = self.split_theory_name(nics_basis)
                    nics_name = f"{nics_func_name}_{nics_basis_name}_NICS_{functional_name}_{basis_name}"

                    if name_suffix:
                        nics_name += f"_{name_suffix}"

                    if nics_program.upper() == "GAUSSIAN":
                        self.add_gaussian_nics_step( 
                            nics_name, nics_func, nics_basis,
                            config_overrides=nics_overrides,
                            coords_source=optfreq_name
                        )
                    else:
                        raise ValueError('NICS calculation only available for Gaussian')

            if aicd_functionals and aicd_basis_sets:
                for aicd_func, aicd_basis in itertools.product(aicd_functionals,aicd_basis_sets):
                    aicd_func_name, aicd_func = self.split_theory_name(aicd_func)
                    aicd_basis_name,aicd_basis = self.split_theory_name(aicd_basis)
                    aicd_name = f"{aicd_func_name}_{aicd_basis_name}_AICD_{functional_name}_{basis_name}"

                    if name_suffix:
                        aicd_name += f"_{name_suffix}"
                        
                    if aicd_program.upper() == "GAUSSIAN":
                        self.add_gaussian_aicd_step( 
                            aicd_name, aicd_func, aicd_basis,
                            config_overrides=aicd_overrides,
                            coords_source=optfreq_name
                        )
                    else:
                        raise ValueError('AICD calculation only available for Gaussian')
                    
        return self
    


    ###############################################

    #    HIDDEN FUNCTIONS


    ###############################################











    
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
            if "run_type" in config:
                print('--------------------------')
                print('in _modify_workflow_for_atoms()')
                words = config["run_type"].lower().strip().split(' ')
                words = [word for word in words if not word.lower() == 'opt']
                run_type = " ".join(words)
                print('removing OPT from run_type')
                print('before')
                print(config["run_type"])
                print('after')
                print(run_type)
                config["run_type"] = run_type
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
                print('--------------------------')
                print('hotfix 2025-06-07')
                print('check this')
                print(mol_group)
                print('if we\'re here, this is an atom')
                print('--------------------------')
                workflow = self._modify_workflow_for_atoms(workflow)
            
            # Create the input list
            input_list = [self.global_config, self.solvents, cm_states, molecules, workflow]
            
            # Run the workflow for this combination
            input_combi.do_everything(
                self.root_dir,
                self.batch_runner_config,
                input_list
            )
    
    def _get_charge_multiplicity_settings(self, charge=0, multiplicity=1, uks=None,broken_symmetry=False,mix_guess = False):
        """
        Generate charge and multiplicity settings.
        
        Parameters:
            charge (int): Molecular charge
            multiplicity (int): Spin multiplicity (2S+1)
            uks (bool): Whether to use unrestricted Kohn-Sham (UKS)
            
        Returns:
            dict: Dictionary with charge and multiplicity settings
        """
        if mix_guess and broken_symmetry:
            raise ValueError('cannot simultaneously use broken symmetry and mix guess')
        # Determine UKS setting if not specified
        if uks is None:
            uks = multiplicity > 1
            
        return {
            "charge": charge,
            "spin_multiplicity": multiplicity,
            "uks": uks,
            "broken_symmetry" : broken_symmetry,
            "mix_guess" :mix_guess,
        }

