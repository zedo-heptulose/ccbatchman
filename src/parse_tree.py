import os
import re
import json
import numpy as np
import pandas as pd
import copy
from . import postprocessing
from . import file_parser

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
        current_node = node if node else self.root_node
        dirpath = dirpath if dirpath else self.root_dir
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
        
        
        if self.debug: # JUST ADDED THIS (5/14/2025)
            current_node.debug = self.debug #appears to obviate the need for debug statements in parsetree itself.
        current_node.parse_data()
        # if self.debug:
        #     print(f"root dir: {self.root_dir}")
        #     print(f"DIRECTORY: {current_node.directory}")
        #     print(f"BASENAME: {current_node.basename}")
        #     print(f"DIRPATH: {dirpath}")
        #     print(f"DATA: {current_node.data}")
        if current_node.data:
            current_node.write_json() #consider putting this in a conditional, like if data: 
        if not current_node.data:
            raise RuntimeError(f'Parsing failed!\ndumping data:\n{json.dumps(current_node.data,indent=2)}')
    






class ParseNode:
    def __init__(self,basename ="",**kwargs):
        self.debug = kwargs.get('debug',False)
        self.children = {} #dict of child nodes. Key is node.basename
        self.data = {} #
        self.directory = "" #full path to the directory this uses
        self.basename = basename
        self.lazy = kwargs.get('lazy',False) 

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

        if os.path.exists(self.json_path) and self.lazy:
            if self.debug:
                print('-------------------------')
                print('using new lazy evaluation')
                print('note - no postprocessing this way')
                print('-------------------------')
            with open(self.json_path,'r') as json_file:
                self.data = json.load(json_file)
            return self
            
        #TODO: fix this bad code
        if not os.path.exists(self.directory):
            raise ValueError(f"ParseLeaf attemped to access non-existent directory: {self.directory}")

        
        run_info_path = os.path.join(self.directory,'run_info.json')
        if os.path.exists(run_info_path):
            if self.debug:
                print('run_info.json exists, reading ruleset')
            with open(run_info_path,'r') as json_file:
                data = json.load(json_file)
            ruleset = data['ruleset']
            ruleset = os.path.basename(ruleset)
            config_dir = os.path.join(os.path.dirname(__file__),'../config/file_parser_config',ruleset)
            ruleset = os.path.normpath(config_dir)
            if self.debug : print(f'found ruleset in run_info.json: {ruleset}')

        # handle case where there is no run_info.json. 
        # For our purposes, output files with the .out extension are ORCA, and those with the .log extension are Gaussian.
        # Should have some kind of flag where we can decide not to do this with strict settings, to avoid bugs.
        # And this should never happen silently, even if self.debug == False.
        else:
            if self.debug:
                print('NO run_info.json - inferring program from file extension.')
            orca_output_file = self.json_path[:-5] + '.out'
            gaussian_output_file = self.json_path[:-5] + '.log'

            
            if os.path.exists(orca_output_file):
                ruleset = os.path.basename(ORCARULES)
                
                if self.debug:    
                    print('inferring ORCA - .out extension found') 
                    print(orca_output_file)
            
            elif os.path.exists(gaussian_output_file):
                ruleset = os.path.basename(GAUSSIANRULES)
                if self.debug:
                    print('inferring Gaussian - .log extension found')
                    print(gaussian_output_file)

                
                config_dir = os.path.join(os.path.dirname(__file__),'../config/file_parser_config',ruleset)
                ruleset = os.path.normpath(config_dir)
                if self.debug : print(f'found ruleset in run_info.json: {ruleset}')
            
            else:
                raise ValueError(f'no file at json path ({self.json_path}) and unknown file type')
        
        # Okay, it might be good to be able to handle there not being a run info path.
        # we can check whether the job basename .log exists or job basename .out exists and infer ORCA or Gaussian by default.

        
        
        if not os.path.exists(self.json_path) and ruleset:
            if os.path.basename(GAUSSIANRULES) == os.path.basename(ruleset):
                output_file = self.json_path[:-5] + '.log'
            
            else:
                output_file = self.json_path[:-5] + '.out'
                
            data = file_parser.extract_data(output_file,ruleset) #this will cause errors sometimes probably. idk. TODO: change this before others use it.
            with open (self.json_path,'w') as json_file:
                json.dump(data,json_file,indent=2) #okay no time like the present!
                
            self.data = data
        
        elif os.path.exists(self.json_path) and ruleset:
            with open(self.json_path, 'r') as json_file:
                #TODO: remove or formalize this
                if os.path.basename(GAUSSIANRULES) == os.path.basename(ruleset):
                    output_file = self.json_path[:-5] + '.log'
                
                else:
                    output_file = self.json_path[:-5] + '.out'
                if self.debug: print(f'parsing output at {output_file}')

                
                if os.path.exists(output_file): #okay why are we doing this twice
                    # TODO: fix this
                    data = file_parser.extract_data(output_file,ruleset)
                
                elif not os.path.exists(output_file): #what. why didn't this work.
                    with open(self.json_path,'r') as json_data:
                        self.data = json.load(json_data)
                    return self  #???? why do we return? oh, postprocessing would break w/ no output. that's a lesson in touching stuff I don't understand
                    #TODO: SHOULD FLAG AN ERROR HERE

                else:
                    raise RuntimeError('the implications are profound')
                
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
            ('E_au','E_minus_E_el_au'), # old : 'E_el_thermo_au'
        ]
        data = sp_data.copy()
        for energy_type in thermal_energies:
            conversion_key = energy_type[0]
            thermal_key = energy_type[1]
            data[thermal_key] = of_data.get(thermal_key,None)
            if not data[thermal_key]:
                # TODO: remove this when no longer necessary
                if not of_data.get(conversion_key,None) and conversion_key == 'E_au':

                    if self.debug:
                        print('---------------------')
                        print('resetting conversion key.')
                        print(f'old conversion key: {conversion_key}')
                    
                    conversion_key = 'E_el_thermo_au'      

                    if self.debug:
                        print(f'new conversion key: {conversion_key}')
                        print('---------------------')
                
                if not of_data.get(conversion_key,None):
                    if self.debug:
                        print('---------------------')
                        print('oh no! No thermochem!')
                        print(f'conversion_key: {conversion_key}')
                        print(f'data: {of_data.get(conversion_key,None)}')
                        print('dumping data:')
                        print(json.dumps(self.children[self.opt_freq_key].data,indent=2))
                        print('---------------------')
                    raise ValueError(f'Missing expected thermochemistry data. Path: {self.children[self.opt_freq_key].directory}')
                data[thermal_key] = of_data[conversion_key] - of_data['E_el_au']
                
            electronic_energy = data.get('E_el_au',None)

            # undo this temporary change
            if conversion_key == 'E_el_thermo_au':
                conversion_key = 'E_au'
                if self.debug:
                    print('---------------------')
                    print('CHANGING CONVERSION KEY')
                    print(f'new conversion_key: {conversion_key}')
                    print('---------------------')
            
            if data[thermal_key] and electronic_energy:
                data[conversion_key] = electronic_energy + data[thermal_key] 
                
                if self.debug and conversion_key == 'E_el_thermo_au':
                    print('---------------------')
                    print('IN LAST PART OF FUNCTION:')
                    print(f'conversion_key: {conversion_key}')
                    print(f'thermal_key: {thermal_key}')
                    print('---------------------')
                elif self.debug and conversion_key == 'E_au':
                    print('---------------------')
                    print(f'conversion_key: {conversion_key}')
                    print('---------------------')
            
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
            'E_au',
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

        

        self.debug = True # fix this!!!
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
        # of_node.debug = self.debug
        if self.directory: #this will cause a problem. we'll fix it when it does
            # print(setting directory of of node)
            of_node.directory = os.path.join(self.directory,self.basename,basename)
        self.opt_freq_key = basename
        self.children[basename] = of_node
        return self


########################################################

    def set_singlepoint_node(self,basename,multiplicity):
        sp_node = ParseLeaf(basename)
        # sp_node.debug = self.debug
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

        print('--------------------------------')
        print('expectation values of <S**2>')
        print(f'triplet: {S_2_triplet}')
        print(f"singlet: {S_2_singlet}")
        

        data[f'Delta_E_st_v_{self.multiplicity.lower()}_au'] = E_sp_triplet - E_sp_singlet

        if self.debug:
            print(f"E_sp_triplet: {E_sp_triplet}")
            print(f"E_sp_singlet: {E_sp_singlet}")
            print(f"difference: {E_sp_triplet - E_sp_singlet}")
            print(f"S_2_triplet: {S_2_triplet}")
            print(f"S_2_singlet: {S_2_singlet}")
        Delta_E_st_sc = 2 * (E_sp_triplet - E_sp_singlet) # temporary test using Noodleman's method... see if this fixes weirdness?
        # Delta_E_st_sc = 2 * (E_sp_triplet - E_sp_singlet)\
        #                    /(S_2_triplet - S_2_singlet) ## UPDATED 2025-09-13
                                                        ## UPDATED: 2 INSTEAD OF S_2_triplet
                                                        # as cited in https://pubs.rsc.org/en/content/articlelanding/2015/cp/c4cp05531d?
        data[f'Delta_E_st_sc_v_{self.multiplicity.lower()}_au'] = Delta_E_st_sc # OK, THIS IS WHAT WE NEEDED

        if self.debug:
            print(f"data[f'Delta_E_st_sc_v_{self.multiplicity.lower()}_au'] = {Delta_E_st_sc}")
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
            ('E_au','E_minus_E_el_au','E_au'),
        ]
        sc_thermal_energies = [
            ('G_au','G_minus_E_el_au','G_sc_au'),
            ('H_au','H_minus_E_el_au','H_sc_au'),
            ('E_au','E_minus_E_el_au','E_sc_au'),
        ]
        thermo_keys = (raw_thermal_energies,sc_thermal_energies)
        
        sp_energy_types = ['E_el_au','E_el_sc_au']
        if self.debug:
            print('---------------------------------------------------')
            print('entering the part where we add ZPVE and thermal corrections to SC electronic energy')
        for i, sp_energy_type in enumerate(sp_energy_types):
            if self.debug:
                print('----------------------------------------')
                print(f"sp_energy_type: {sp_energy_type}")
            
            for energy_type in thermo_keys[i]:
                conversion_key = energy_type[0] # eg. G_au
                thermal_key = energy_type[1] # eg. G_minus_E_el_au
                final_key_name = energy_type[2]

                
                if self.debug:
                    print('-----------------------------')
                    print(f"conversion_key: {conversion_key}")
                    print(f"thermal_key: {thermal_key}")
                    print(f"final_key_name = {final_key_name}")
                
                data[thermal_key] = of_data.get(thermal_key,None) # get this if we got it
                
                if not data[thermal_key]: # make it if we don't
                    data[thermal_key] = of_data[conversion_key] - of_data['E_el_au']

                if self.debug:
                    print(f"value for data['thermal_key']: {thermal_key}")
                    
                ###########################################
                
                electronic_energy = data[sp_energy_type] # this was a .get(),

                if self.debug:
                    print(f"sp_energy_type: {sp_energy_type}")
                    print(f"electronic_energy: {electronic_energy}")
                
                # but we've already long raised an exception by now if
                # we don't have this
                ###########################################
    
                if data[thermal_key] and electronic_energy: #make new thermal keys
    
                    #multiplicity should match, potentials used for frequencies
                    #are using the multiplicity the optimization was done with
                    ###########################################
                    data[final_key_name] = electronic_energy + data[thermal_key] 
                    ##########################################

                    if self.debug:
                        print(f"final_key_name: {final_key_name}")
                        print(f"value for data['final_key_name']: {data[final_key_name]}")
                        
                elif not data[thermal_key]:
                
                    child_dir = self.children[self.opt_freq_key].directory
                    if self.debug: print(f"No key {thermal_key} for {child_dir}, setting energy to np.nan")
                    
                elif not electronic_energy:
                
                    data[final_key_name] = None
                    
                    child_dir = self.children[self.singlepoint_key].directory
                    if self.debug: print(f"No key E_el_au for {child_dir}, setting energy to np.nan")
                
        self.data = data #right, the final step.

########################################################################







