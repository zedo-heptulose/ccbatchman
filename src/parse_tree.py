import os
import re
import json
import numpy as np
import pandas as pd
import copy
import postprocessing
import file_parser

ORCARULES = '../config/file_parser_config/orca_rules.dat'
GAUSSIANRULES = "../config/file_parser_config/gaussian_rules.dat"

class ParseTree:
    #FUNCTIONS THIS NEEDS
    #depth first parsing
    def __init__(self,root=None):
        self.root_node = None
        self.root_dir = None
        self.display_function = None
        self.debug = False

    @property
    def data(self):
        return self.root_node.data
    
    def write_json(self):
        with open(self.root_node.json_path,'w') as json_file:
            json.dump(self.data,json_file,indent=2)
    
    def depth_first_parse(self,node=None,dirpath=None):
        if self.debug: print(f"root dir: {self.root_dir}")
        current_node = node if node else self.root_node
        dirpath = dirpath if dirpath else self.root_dir
        if self.debug: print(f"DIRPATH: {dirpath}")
        #this should do nothing if there is no node
        for key, node in current_node.children.items():
            new_dir = os.path.join(dirpath,node.basename) #an assumption is being made here...
            self.depth_first_parse(node,new_dir)
            xyz_path = os.path.join(new_dir,node.basename) + '.xyz'
            if self.display_function is not None and os.path.exists(xyz_path):
               self.display_function(xyz_path)
        current_node.directory = dirpath #now we needn't specify directories within nodes when making them

        #hotfix for if we set a basename with multiple directories, which occasionally happens
        #this is the intended behavior
        current_node.basename = os.path.basename(current_node.basename) 
        
        if self.debug : print(f"DIRECTORY: {current_node.directory}")
        if self.debug : print(f"BASENAME: {current_node.basename}")
        current_node.parse_data()
        if self.debug : print(f"DATA: {current_node.data}")
        current_node.write_json()







class ParseNode:
    def __init__(self,basename ="",**kwargs):
        self.debug = kwargs.get('debug',False)
        self.children = {} #dict of child nodes. Key is node.basename
        self.data = {} #
        self.directory = "" #full path to the directory this uses
        self.basename = basename

    @property
    def json_path(self):
        return os.path.join(self.directory,self.basename) + '.json'
    
    def write_json(self):
        with open(self.json_path, 'w') as json_file:
            json.dump(self.data,json_file,indent = "")

    def parse_data():
        raise NotImplementedError('ParseNode is a virtual class')
        #how does this thing even work

class ParseLeaf(ParseNode):
    def parse_data(self):
        if self.debug: print(f"in directory: {self.directory}")
        if self.debug: print(f"opening file: {self.json_path}")
        ruleset = None
        #TODO: fix this bad code
        if not os.path.exists(self.directory):
            raise ValueError(f"ParseLeaf attemped to access non-existent directory: {self.directory}")
        
        if os.path.exists(run_info_path := os.path.join(self.directory,'run_info.json')):
            with open(run_info_path,'r') as json_file:
                data = json.load(json_file)
            ruleset = data['ruleset']
            ruleset = os.path.basename(ruleset)
            config_dir = os.path.join(os.path.dirname(__file__),'../config/file_parser_config',ruleset)
            ruleset = os.path.normpath(config_dir)
            if self.debug : print(f'found ruleset in run_info.json: {ruleset}')
        if os.path.exists(self.json_path) and ruleset:
            with open(self.json_path, 'r') as json_file:
                #TODO: remove or formalize this
                if os.path.basename(GAUSSIANRULES) == os.path.basename(ruleset):
                    output_file = self.json_path[:-5] + '.log'
                
                else:
                    output_file = self.json_path[:-5] + '.out'
                if self.debug: print(f'parsing output at {output_file}')

                if os.path.exists(output_file):
                    data = file_parser.extract_data(output_file,ruleset)
                
                else:
                    with open(self.json_path,'r') as json_data:
                        self.data = json.load(json_data)
                    return self 
                    #TODO: SHOULD FLAG AN ERROR HERE
                
                
            
                self.data = data
                
                # print("data before postprocessing")
                # print(self.data)
                
                if os.path.basename(ruleset) == os.path.basename(ORCARULES) and os.path.exists(output_file):
                    pp = postprocessing.OrcaPostProcessor(debug=self.debug)
                    pp.data = self.data
                    pp.thermal_energies()
                    self.data = pp.data
                
                    pp.basename = self.basename
                    pp.dirname = self.directory
                    pp.orca_pp_routine()
                    self.data = pp.data 

                ###########################################
                #### recently added, look here for errors
                elif os.path.basename(ruleset) == os.path.basename(GAUSSIANRULES) and os.path.exists(output_file):
                    pp = postprocessing.GaussianPostProcessor(debug=self.debug)
                    pp.data = self.data
                    pp.thermal_energies()
                    self.data = pp.data
                
                    pp.basename = self.basename
                    pp.dirname = self.directory
                    pp.pp_routine()
                    self.data = pp.data
                ##########################################

                
                else:
                    if self.debug: print('file not compatible w/ orca or gaussian pp routine')
        return self
                  










class CompoundNode(ParseNode):
    #use concrete case for this:
    #an optimization/frequency calculation,
    #followed by a singlepoint (at a higher LOT)
    #use postprocessing here
    def __init__(self,basename="",of_basename="",sp_basename="",directory=None,recursive=False):
        ParseNode.__init__(self,basename)
        self.opt_freq_key = of_basename
        self.singlepoint_key = sp_basename
        self.debug = False
        self.directory = directory
        self.recursive = recursive
        if of_basename and sp_basename:
            self.set_opt_freq_node(of_basename)
            self.set_singlepoint_node(sp_basename)

    #this massively expedites process of making these.
    def set_opt_freq_node(self,basename):
        of_node = ParseLeaf(basename)
        of_node.debug = self.debug
        if self.directory: #this will cause a problem. we'll fix it when it does
            # print(setting directory of of node)
            of_node.directory = os.path.join(self.directory,self.basename,basename)
        self.opt_freq_key = basename
        self.children[basename] = of_node
        return self

    def set_singlepoint_node(self,basename):
        sp_node = ParseLeaf(basename)
        sp_node.debug = self.debug
        if self.directory: #this will cause a problem. we'll fix it when it does
            sp_node.directory = os.path.join(self.directory,self.basename,basename)
            # print('set directory!')
        self.singlepoint_key = basename
        self.children[basename] = sp_node
        return self
    
    def parse_data(self):
        if self.recursive:
            self.children[self.opt_freq_key].parse_data()
            self.children[self.singlepoint_key].parse_data()
        of_data = copy.deepcopy(self.children[self.opt_freq_key].data)
        sp_data = copy.deepcopy(self.children[self.singlepoint_key].data)
        #let's look at a data object and see what we would need to use here
        #actually this one is pretty easy
        thermal_energies = [
            ('G_au','G_minus_E_el_au'),
            ('H_au','H_minus_E_el_au'),
            ('E_el_thermo_au','E_minus_E_el_au'),
        ]
        data = sp_data.copy()
        for energy_type in thermal_energies:
            conversion_key = energy_type[0]
            thermal_key = energy_type[1]
            data[thermal_key] = of_data.get(thermal_key,None)
            if not data[thermal_key]:
                data[thermal_key] = of_data[conversion_key] - of_data['E_el_au']
            electronic_energy = data.get('E_el_au',None) 
            
            if data[thermal_key] and electronic_energy:
                data[conversion_key] = electronic_energy + data[thermal_key] 
            elif not data[thermal_key]:
                child_dir = self.children[self.opt_freq_key].directory
                if self.debug: print(f"No key {thermal_key} for {child_dir}, setting energy to np.nan")
            elif not electronic_energy:
                data[conversion_key] = None
                child_dir = self.children[self.singlepoint_key].directory
                if self.debug: print(f"No key E_el_au for {child_dir}, setting energy to np.nan")
            
        self.data = data














class ThermoNode(ParseNode):
    #this type of node is used to calculate thermochemistry
    #we keep a dict of tuples, (reactant_or_product,coefficient)
    #usually this is the topmost node
    def __init__(self,basename="",**kwargs):
        ParseNode.__init__(self,basename)
        self.coefficients = {} #name : tuple (reactant or product, coeff)
        self.percolate_keys = {} #name : list keys to percolate
        self.energy_types = kwargs.get('energy_types',[
            'G_au',
            'H_au',
            'E_el_thermo_au',
            'E_el_au'
        ])
        #TODO: pick a better name for this?
        #set by user at generation time

    def set_reactants(self,reactant_list):
        '''
        expects a list of tuples, 'node', 'coefficient'
        node can be string for a parseleaf or another node
        coefficient is a number, the reaction coefficient
        '''
        for reactant in reactant_list:
            node = reactant[0]
            if type(node) is str:
                node = ParseLeaf(node)
            coefficient = reactant[1]
            basename = node.basename
            self.children[basename] = node
            self.coefficients[basename] = ('reactant',coefficient)
        return self

    def set_products(self,product_list):
        for product in product_list:
            node = product[0]
            if type(node) is str:
                node = ParseLeaf(node)
            coefficient = product[1]
            basename = node.basename
            self.children[basename] = node
            self.coefficients[basename] = ('product',coefficient)
        return self
    
    def parse_data(self):
        #check these literals if we run into bugs
        #TODO: give user more control over these energy types!
        products_label = 'product'
        reactants_label = 'reactant'
        delta_label = 'Delta'
        reaction_data = {}
        for energy_type in self.energy_types:    
            for key in self.coefficients:
            #this loop is inside, we want to be able to break from this
            #edge case if energy is zero, but that would never happen...
                product_or_reactant = self.coefficients[key][0]
                reaction_coefficient = self.coefficients[key][1]
                new_key = f"{product_or_reactant}_{energy_type}"
                energy = self.children[key].data.get(energy_type,None)
                if energy is None and self.debug:
                    print(f"Read failed.")
                    print(f"key: {key} | energy type: {energy_type}")
                    print(f"Data of broken node:")
                    print(self.children[key].data)
                    print(f"Children of thermo node:")
                    print(self.children)
                if energy and (reaction_data.get(new_key,0) is not None):
                    reaction_data[new_key] =\
                        reaction_data.get(new_key,0) +\
                        reaction_coefficient * energy
                else:    
                    reaction_data[new_key] = None 
                    

        for energy_type in self.energy_types:
            product_energy = reaction_data[f"{products_label}_{energy_type}"]
            reactant_energy = reaction_data[f"{reactants_label}_{energy_type}"]
            if product_energy and reactant_energy:
                reaction_data[f"{delta_label}_{energy_type}"] = product_energy - reactant_energy
            else:
                reaction_data[f"{delta_label}_{energy_type}"] = np.nan
                if self.debug: print(f"{delta_label}_{energy_type} could not be calculated")
                

        self.data = reaction_data
        
        for child_key, data_keys in self.percolate_keys.items():
            for p_key in data_keys:
                try:
                    self.data[p_key] = self.children[child_key].data[p_key]
                except:
                    if self.debug: print(f'could not percolate key {p_key}')
            
        self.data = postprocessing.delta_unit_conversions(self.data)
        return self



















#############################################################

# NEW STUFF, JUST FOR PROCESSING THESE THE WAY WE GOTTA WITH GAUSSIAN

class DiradicalNode(ParseNode):
    '''
    As implemented, will only work with Gaussian 
    '''
    def __init__(self,
        basename="",
        of_basename="",
        
        singlet_sp_basename="",
        triplet_sp_basename="",

        multiplicity="",

        directory=None,
        recursive=False
    ):
        ParseNode.__init__(self,basename)
        self.opt_freq_key = of_basename


        ########################################
        self.singlet_sp_key = singlet_sp_basename
        self.triplet_sp_key = triplet_sp_basename
        
        self.multiplicity = multiplicity
        
        #########################################

        

        self.debug = False
        self.directory = directory
        self.recursive = recursive
        if of_basename and singlet_sp_basename and triplet_sp_basename:
            self.set_opt_freq_node(of_basename)

            ####################################
            self.set_singlepoint_node(singlet_sp_basename,'singlet')
            self.set_singlepoint_node(triplet_sp_basename,'triplet')
            #####################################


    #this massively expedites process of making these.
    def set_opt_freq_node(self,basename):
        of_node = ParseLeaf(basename)
        of_node.debug = self.debug
        if self.directory: #this will cause a problem. we'll fix it when it does
            # print(setting directory of of node)
            of_node.directory = os.path.join(self.directory,self.basename,basename)
        self.opt_freq_key = basename
        self.children[basename] = of_node
        return self


########################################################

    def set_singlepoint_node(self,basename,multiplicity):
        sp_node = ParseLeaf(basename)
        sp_node.debug = self.debug
        if self.directory: #this will cause a problem. we'll fix it when it does
            sp_node.directory = os.path.join(self.directory,self.basename,basename)
            # print('set directory!')

        #################################
        if multiplicity.lower() == 'singlet':
            self.singlet_sp_key = basename
        elif multiplicity.lower() == 'triplet':
            self.triplet_sp_key = basename
        ###################################
        
        self.children[basename] = sp_node
        return self



#########################################################    

    def parse_data(self):
        if self.recursive:
            self.children[self.opt_freq_key].parse_data()
            self.children[self.singlet_sp_key].parse_data()
            self.children[self.triplet_sp_key].parse_data()
            
        of_data = copy.deepcopy(self.children[self.opt_freq_key].data)
        singlet_sp_data = copy.deepcopy(self.children[self.singlet_sp_key].data)
        triplet_sp_data = copy.deepcopy(self.children[self.triplet_sp_key].data)

        ####################################################
        if self.multiplicity.lower() == 'singlet':
            data = singlet_sp_data.copy() # okay, this part is a problem
        
        elif self.multiplicity.lower() == 'triplet':
            data = triplet_sp_data.copy() # okay, this part is a problem

        else:
            raise ValueError(f'"{self.multiplicity}" is not a valid multiplicity')
        ####################################################

        #######################################
        S_2_triplet = triplet_sp_data['<S**2>']
        S_2_singlet = singlet_sp_data['<S**2>'] 
        
        E_sp_triplet = triplet_sp_data['E_el_au']
        E_sp_singlet = singlet_sp_data['E_el_au']
        

        data[f'Delta_E_st_v_{self.multiplicity.lower()}_au'] = E_sp_triplet - E_sp_singlet
        
        Delta_E_st_sc = S_2_triplet * (E_sp_triplet - E_sp_singlet)\
                                    /(S_2_triplet - S_2_singlet)

        data[f'Delta_E_st_sc_v_{self.multiplicity.lower()}_au'] = Delta_E_st_sc # OK, THIS IS WHAT WE NEEDED

        # ########################################
        # print('in parse_tree.py')
        # print(f'multiplicity: {self.multiplicity}')
        # print(json.dumps(data,indent=2))
        # ######################################
        
        
        self.data['NOTE'] = "Delta_E_st_v_au is triplet - singlet here"

      
        data['E_el_singlet_au'] = E_sp_singlet
        #sc means spin corrected
        data['E_el_sc_singlet_au'] = E_sp_triplet - Delta_E_st_sc

        data['E_el_triplet_au'] = E_sp_triplet
    
        if self.multiplicity.lower() == 'singlet':
            data['E_el_au']    = data['E_el_singlet_au']
            data['E_el_sc_au'] = data['E_el_sc_singlet_au']

        elif self.multiplicity.lower() == 'triplet':
            data['E_el_au']    = data['E_el_triplet_au']
            data['E_el_sc_au'] = data['E_el_triplet_au']

    
        ###########################################

    
        raw_thermal_energies = [
            ('G_au','G_minus_E_el_au','G_au'),
            ('H_au','H_minus_E_el_au','H_au'),
            ('E_el_thermo_au','E_minus_E_el_au','E_au'),
        ]
        sc_thermal_energies = [
            ('G_au','G_minus_E_el_au','G_sc_au'),
            ('H_au','H_minus_E_el_au','H_sc_au'),
            ('E_el_thermo_au','E_minus_E_el_au','E_sc_au'),
        ]
        thermo_keys = (raw_thermal_energies,sc_thermal_energies)
        
        sp_energy_types = ['E_el_au','E_el_sc_au']
        for i, sp_energy_type in enumerate(sp_energy_types):
            for energy_type in thermo_keys[i]:
            
                conversion_key = energy_type[0] # eg. G_au
                thermal_key = energy_type[1] # eg. G_minus_E_el_au
                final_key_name = energy_type[2]
                
                data[thermal_key] = of_data.get(thermal_key,None) # get this if we got it
                
                if not data[thermal_key]: # make it if we don't
                    data[thermal_key] = of_data[conversion_key] - of_data['E_el_au']
    
                ###########################################
                electronic_energy = data[sp_energy_type] # this was a .get(),
                # but we've already long raised an exception by now if
                # we don't have this
                ###########################################
    
                if data[thermal_key] and electronic_energy: #make new thermal keys
    
                    #multiplicity should match, potentials used for frequencies
                    #are using the multiplicity the optimization was done with
                    ###########################################
                    data[final_key_name] = electronic_energy + data[thermal_key] 
                    ##########################################
    
                elif not data[thermal_key]:
                
                    child_dir = self.children[self.opt_freq_key].directory
                    if self.debug: print(f"No key {thermal_key} for {child_dir}, setting energy to np.nan")
                    
                elif not electronic_energy:
                
                    data[final_key_name] = None
                    
                    child_dir = self.children[self.singlepoint_key].directory
                    if self.debug: print(f"No key E_el_au for {child_dir}, setting energy to np.nan")
                
        self.data = data #right, the final step.

########################################################################







