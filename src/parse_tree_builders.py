import parse_tree
import os

class SimpleETreeBuilder:
    def __init__(self,params=None):
        self.root_basename = ""
        self.root_dir = ""
        self.reactants = {}
        self.products = {}
        self.singlepoint_dir = ""
        self.debug = False
        self.change_params(params)

    def to_dict(self):
        new_dict = {
            'root_basename' : self.root_basename,
            'root_dir' : self.root_dir,
            'reactants' : self.reactants,
            'products' : self.products,
            'singlepoint_dir' : self.singlepoint_dir,
            'debug' : self.debug
        }
        return new_dict

    def from_dict(self,info):
        self.root_dir = info['root_basename']
        self.root_dir = info['root_dir']
        self.reactants = info['reactants']
        self.products = info['products']
        self.singlepoint_dir = info['singlepoint_dir']
        self.debug = info['debug']
        
        return self
        
    def change_params(self,new_params):
        self_dict = self.to_dict()
        self_dict.update(new_params)
        self.from_dict(self_dict)
        return self

    def build(self):
        root = parse_tree.ThermoNode(self.root_basename)
        
        reactant_nodes_and_coeffs = [(os.path.join(reactant,self.singlepoint_dir),coefficient) for reactant, coefficient in self.reactants.items()]
        root.set_reactants(reactant_nodes_and_coeffs)
        
        product_nodes_and_coeffs = [(os.path.join(product,self.singlepoint_dir),coefficient) for product, coefficient in self.products.items()]
        root.set_products(product_nodes_and_coeffs)
        root.energy_types = ['E_el_au']
        
        pt = parse_tree.ParseTree()
        pt.root_node = root
        pt.root_dir = self.root_dir


        pt.debug = self.debug
        
        return pt







class SimpleThermoTreeBuilder:
    '''
    Tree used for processing simple thermochemical data.
    '''
    def __init__(self,params=None):
        self.root_basename = ""
        self.root_dir = ""
        self.reactants = {}
        self.products = {}
        self.opt_freq_dir = ""
        self.singlepoint_dir = ""
        self.debug = False
        self.change_params(params)
    
    def to_dict(self):
        new_dict = {
            'root_basename' : self.root_basename,
            'root_dir' : self.root_dir,
            'reactants' : self.reactants,
            'products' : self.products,
            'opt_freq_dir' : self.opt_freq_dir,
            'singlepoint_dir' : self.singlepoint_dir,
            'debug' : self.debug,
        }
        return new_dict

    def from_dict(self,info):
        self.root_dir = info['root_basename']
        self.root_dir = info['root_dir']
        self.reactants = info['reactants']
        self.products = info['products']
        self.opt_freq_dir = info['opt_freq_dir']
        self.singlepoint_dir = info['singlepoint_dir']
        self.debug = info['debug']
        return self

#FOR ONLY SINGLEPOINTS:
#THIS IS HARDER... WE NEED delta G
    def build(self):
        root = parse_tree.ThermoNode(self.root_basename)
        
        reactant_nodes_and_coeffs = [(parse_tree.CompoundNode(reactant,self.opt_freq_dir,self.singlepoint_dir),coefficient) for reactant, coefficient in self.reactants.items()]
        root.set_reactants(reactant_nodes_and_coeffs)

        product_nodes_and_coeffs = [(parse_tree.CompoundNode(product,self.opt_freq_dir,self.singlepoint_dir),coefficient) for product, coefficient in self.products.items()]
        root.set_products(product_nodes_and_coeffs)
        
        pt = parse_tree.ParseTree()
        pt.root_node = root
        pt.root_dir = self.root_dir
        pt.debug = self.debug
        return pt

                    
    def change_params(self,new_params):
        self_dict = self.to_dict()
        self_dict.update(new_params)
        self.from_dict(self_dict)
        return self
        













class BSTreeBuilder:
    '''
    Builder used to create trees for processing data from singlet-triplet gap runs.
    '''
    def __init__(self,params=None): #these can be iterated through.
        self.root_dir = ""
        self.root_basename = ""
        self.singlet_dir = ""
        self.triplet_dir = ""
        self.is_compound = False
        self.opt_freq_dir = ""
        self.singlet_sp_dir = ""
        self.triplet_sp_dir = ""
        self.debug = False
        if params:
            self.from_dict(params)
        
    def to_dict(self):
        new_dict = {
            'root_dir' : self.root_dir,
            'root_basename' : self.root_basename,
            'singlet_dir' : self.singlet_dir,
            'triplet_dir' : self.triplet_dir,
            'is_compound' : self.is_compound,
            'opt_freq_dir' : self.opt_freq_dir,
            'singlet_sp_dir' : self.singlet_sp_dir,
            'triplet_sp_dir' : self.triplet_sp_dir,
            'debug' : self.debug,
        }
        return new_dict


    def from_dict(self,info):
        self.root_dir = info['root_dir']
        self.root_basename = info['root_basename']
        self.singlet_dir = info['singlet_dir']
        self.triplet_dir = info['triplet_dir']
        self.is_compound = info['is_compound']
        self.opt_freq_dir = info['opt_freq_dir']
        self.singlet_sp_dir = info['singlet_sp_dir']
        self.triplet_sp_dir = info['triplet_sp_dir']
        self.debug = info['debug']
        return self

    def change_params(self,new_params):
        self_dict = self.to_dict()
        self_dict.update(new_params)
        self.from_dict(self_dict)
        return self

    def build(self):
        root = parse_tree.ThermoNode(self.root_basename)
        if self.is_compound:
            root.set_reactants([
                (
                parse_tree.CompoundNode(
                    self.singlet_dir,
                    self.opt_freq_dir,
                    self.singlet_sp_dir
                    ),
                1
                )
            ])
            root.set_products([
                (
                parse_tree.CompoundNode(
                    self.triplet_dir,
                    self.opt_freq_dir,
                    self.triplet_sp_dir
                    ),
                1
                )
            ])
        else:
            root.set_reactants([
                (self.singlet_dir,1)
            ])
            root.set_products([
                (self.triplet_dir,1)
            ])
        root.percolate_keys[self.singlet_dir] = [
            'diradical_character_yamaguchi',
            'diradical_character_naive',
            'tetraradical_character_naive',
            'Delta_E_st_v_au', #'Delta_E_st_v_au'
        ]
        
        pt = parse_tree.ParseTree()
        pt.debug = self.debug
        pt.root_node = root
        pt.root_dir = self.root_dir
        return pt

















############################

# new data structure for parsing Gaussian jobs?


class DiradicalTreeBuilder:
    '''
    Builder used to create trees for processing data from singlet-triplet gap runs.
    '''
    def __init__(self,params=None): #these can be iterated through.
        self.root_dir = ""
        self.root_basename = ""
        self.singlet_dir = ""
        self.triplet_dir = ""
        self.is_compound = False
        self.opt_freq_dir = ""
        self.singlet_sp_dir = ""
        self.triplet_sp_dir = ""
        self.debug = False
        if params:
            self.from_dict(params)
        
    def to_dict(self):
        new_dict = {
            'root_dir' : self.root_dir,
            'root_basename' : self.root_basename,
            'singlet_dir' : self.singlet_dir,
            'triplet_dir' : self.triplet_dir,
            'is_compound' : self.is_compound,
            'opt_freq_dir' : self.opt_freq_dir,
            'singlet_sp_dir' : self.singlet_sp_dir,
            'triplet_sp_dir' : self.triplet_sp_dir,
            'debug' : self.debug,
        }
        return new_dict


    def from_dict(self,info):
        self.root_dir = info['root_dir']
        self.root_basename = info['root_basename']
        self.singlet_dir = info['singlet_dir']
        self.triplet_dir = info['triplet_dir']
        self.is_compound = info['is_compound']
        self.opt_freq_dir = info['opt_freq_dir']
        self.singlet_sp_dir = info['singlet_sp_dir']
        self.triplet_sp_dir = info['triplet_sp_dir']
        self.debug = info['debug']
        return self

    def change_params(self,new_params):
        self_dict = self.to_dict()
        self_dict.update(new_params)
        self.from_dict(self_dict)
        return self

    def build(self):
        root = parse_tree.ThermoNode(self.root_basename)
        root.energy_types = [
            'G_au',
            'H_au',
            'E_au',
            'E_el_au',
            'G_sc_au',
            'H_sc_au',
            'E_sc_au',
            'E_el_sc_au',
        ]
        if self.is_compound:
            # triplet minus singlet
            root.set_products([
                (
                    parse_tree.DiradicalNode(
                        self.triplet_dir,
                        self.opt_freq_dir,
                        self.singlet_sp_dir,
                        self.triplet_sp_dir,
                        'triplet',
                ),
                1
                )
            ])
            root.set_reactants([
                (
                    parse_tree.DiradicalNode(
                        self.singlet_dir,
                        self.opt_freq_dir,
                        self.singlet_sp_dir,
                        self.triplet_sp_dir,
                        'singlet',
                ),
                1
                )
            ])
        else:
            # triplet minus singlet
            root.set_products([
                (self.triplet_dir,1)
            ])
            root.set_reactants([
                (self.singlet_dir,1)
            ])
            
        #yeah, I think this is enough! let's try it
        root.percolate_keys[self.singlet_dir] = [
            'diradical_character_yamaguchi', # for now these are at singlet geom
            'diradical_character_naive',    # we can change that later
            'tetraradical_character_naive',
            'Delta_E_st_sc_v_singlet_au',
            'Delta_E_st_v_singlet_au',
        ]
        
        root.percolate_keys[self.triplet_dir] = [ # for now we don't get gamma from here
            'Delta_E_st_sc_v_triplet_au',
            'Delta_E_st_v_triplet_au',
        ]
        # products and reactants got flipped.
        # fix this and you can send it to michael and sleep
        pt = parse_tree.ParseTree()
        pt.debug = self.debug
        pt.root_node = root
        pt.root_dir = self.root_dir
        return pt




