import json
import os
import re
import numpy
import pandas
import file_parser

rule_relpath = '../config/file_parser_config/'
src_dir = os.path.dirname(os.path.abspath(__file__))
RULESDIR = os.path.join(src_dir,rule_relpath)
ORCARULES = 'orca_rules.dat'
GAUSSIANRULES = 'gaussian_rules.dat'


class OrcaPostProcessor:
    def __init__(self,dirname=None,basename=None,**kwargs):
        self.debug = kwargs.get('debug',False)
        #filepath stuff
        self.output_extension = '.out'
        self.basename = basename
        self.dirname = dirname
        self.parser_rules_path = os.path.join(RULESDIR,ORCARULES)

        #data
        self.data = {} #this goes with data
        self.frontier_uno_occupations = [] # should be separate from data
        #these are really stupid names, but eh.
        #use CCLIB for this stuff dummy
        self.HONOs = []
        self.LUNOs = []

        self.alpha_MO_energies = []
        self.alpha_MO_occs = []
        
    
    @property
    def output_path(self):
         return os.path.join(self.dirname,self.basename) + self.output_extension

    @property
    def json_path(self):
        return os.path.join(self.dirname,self.basename) + '.json'

    def read_json(self,filename = None):
        if filename is None: filename = self.json_path
        with open(filename,'r') as json_file:
            self.data = json.load(json_file)

    #check syntax
    def write_json(self,filename = None):
        if filename is None: filename = self.json_path
        with open(filename,'w') as json_file:
            json.dump(self.data,json_file,indent="")

    def read_raw_state(self):
        self.data = file_parser.extract_data(self.output_path,self.parser_rules_path)
        if not self.data['success']:
            if self.debug: print("warning: reading data from failed job!")
        return self

    def parse_frontier_UNO_occupations(self):
        '''
        here, we parse everything [2.00, 0.00]
        '''
        if self.debug: print(F"reading file at {self.output_path}")
        with open(self.output_path,'r') as output_file:
            lines = output_file.readlines()
        occupations = []
        search = False
        for line in lines:
            if re.match(r'\s*UHF\s+NATURAL\s+ORBITALS',line):
                search = True
                occupations = []
           
            elif re.match(r'\s*QR-MO\s+GENERATION',line):
                search = False

            if search:
                matches = re.findall(r'(?:N\[\s*\d+\]=\s+)(\d\.\d+)',line)
                occupations.extend(matches)
        occupations = [float(occ) for occ in occupations]
        try:
            last_2 = len(occupations) - 1 - occupations[::-1].index(2.000) 
        except:
            last_2 = 0 #just use the start of the list if none
        try:
            first_0 = occupations.index(0.000)
        except:
            first_0 = -1 #just use the end of the list if none

        if self.debug: print(last_2)
        if self.debug: print(first_0)
        if self.debug: print("OCCUPATIONS:")
        if self.debug: print(occupations)
        #find index of first one or last value larger than one
        one_found = False
        hono_end = -1
        for index, value in enumerate(occupations):
            # print(value)
            if value == 2.000:
                if self.debug: print('2.000 found')
                hono_end = index + 1
                if self.debug: print(hono_end)
                
            elif value == 1.000:
                if self.debug: print('1.000 found')
                hono_end = index + 1
                if self.debug: print('warning: last hono 1.000, check for edge case')
                if self.debug: print(hono_end)
                break
                
            elif value < 1.000:
                if self.debug: print('val less than 1')
                hono_end = index
                if self.debug: print(hono_end)
                break #this break statement fixed it
                
        if self.debug: print(f"hono_end: {hono_end}")

        self.HONOs = occupations[:hono_end]
        self.LUNOs = occupations[hono_end:]

        HONO = self.HONOs[-1]
        LUNO = self.LUNOs[0]
 
        T_HO = (HONO - LUNO) / 2
        gamma_0 = 1 - 2*T_HO/(1 + T_HO**2)
        # print(gamma_0)
        self.data['diradical_character_yamaguchi'] = gamma_0
        
        self.data['diradical_character_naive'] = self.LUNOs[0]
        if len(self.LUNOs) >= 2:
            self.data['tetraradical_character_naive'] = self.LUNOs[1]
        else:
            self.data['tetraradical_character_naive'] = 0

        return self
        
    def prune_data(self):
        '''
        should have a function to strip 
        misleading intermediate values from output files
        for now, get rid of anything with None as its value
        '''
        new_dict = {}
        for k,v in self.data.items():
            if v is not None:
                new_dict[k] = v
        self.data = new_dict
        return self


    
    def spin_corrected_bs_energies(self):
        '''
        using the convention of triplet minus singlet
        \Delta{}E^(st)_(sc) = <S^2>_(HS) * frac{E_HS-E_BS}{<S^2>_HS-<S^2>_BS}
        from ABE DIRADICALS REVIEW (2012)
        #TODO: include DOI here
        '''
        #THESE DON'T INCLUDE DISPERSION CORRECTION,
        #BUT ALL OTHER ENERGIES IN JSON DATA ALWAYS WILL.
        S_2_hs = self.data['<S^2>_HS']
        S_2_bs = self.data['<S^2>_BS'] 
        E_hs_au = self.data['E_high_spin_au']
        E_bs_au = self.data['E_broken_sym_au']

        E_gCP_au = self.data.get('E_gCP_au',0.000)
        E_dispersion_au = self.data.get('E_dispersion_au',0.000)
        
        Delta_E_st_sc = S_2_hs * (E_hs_au - E_bs_au)/(S_2_hs - S_2_bs)
        
        self.data['Delta_E_st_v_au'] = Delta_E_st_sc
        #d as in "dispersionAndGCP"
        self.data['E_el_au'] =\
            E_hs_au - Delta_E_st_sc + E_gCP_au + E_dispersion_au

        #for completeness
        self.data['E_el_triplet_au'] =\
            E_hs_au + E_gCP_au + E_dispersion_au

        self.data['NOTE'] = [
            "All energy values, except for purely thermal and",
            "triplet ones, are spin-corrected and derived from",
            "<S^2>_HS, <S^2>_BS, E_high_spin_au, E_broken_sym_au",
            "E_gCP_au, and E_dispersion_au",
            ]

        return self
        #TODO: refresh keys used in file parser rules, they are bad
        #TODO: write these keys down somewhere, make a list, or it will get annoying

    def thermal_energies(self):
        '''
        this is used to get X_minus_E_el,
        for every energy variable...
        This should calculate this for everything 
        with some certain characteristics.
        are there commonalities with all the energies to use?
        maybe we should change the way BS jobs are handled.
        we make the spin corrected value the default E_el_au,
        and we store the old value as "E_el_no_spin_corr_au"
        and we have "E_el_triplet_au"
        and we don't store the dispersion uncorrected values.
        and we include a "broken_symmetry" flag.
        '''
        E_el_au = self.data['E_el_au']
        try:
            G_au = self.data['G_au']
            H_au = self.data['H_au']
            # E_au = self.data['E_au']
            self.data['G_minus_E_el_au'] = G_au - E_el_au
            self.data['H_minus_E_el_au'] = H_au - E_el_au
            # self.data['E_minus_E_el_au'] = E_au - E_el_au
            self.data['thermochem'] = True
        except:
            self.data['thermochem'] = False
        return self
    
    def delta_E_homo_lumo(self):
        raise NotImplementedError()

    def orca_pp_routine(self):
        '''
        TODO: this should raise an exception if the job isn't
        orca. 
        '''
        unos_parsed = True
        bs_parsed = True        
        self.read_raw_state()
        self.prune_data()
        self.thermal_energies()
        
        try:
            self.parse_frontier_UNO_occupations()
        # self.delta_E_homo_lumo()
        except: 
            unos_parsed = False
            
        try:
            self.spin_corrected_bs_energies()
        except:
            bs_parsed = False
        
        self.data = delta_unit_conversions(self.data)
        self.write_json()
        if not unos_parsed or not bs_parsed:
            if self.debug: print("warning in run with")
            if self.debug: print(f"directory: {self.dirname}")
            if self.debug: print(f"basename: {self.basename}")
            if self.debug: print(f"ORCA JOB")
            if not unos_parsed and self.debug: print("Could not parse UNO occs")
            if not bs_parsed and self.debug: print("Could not parse BS spin-corrected energies")

##################################################

# Gaussian runs

##################################################

class GaussianPostProcessor:
    def __init__(self,dirname=None,basename=None,**kwargs):
        self.debug = kwargs.get('debug',False)
        #filepath stuff
        self.output_extension = '.log'
        self.basename = basename
        self.dirname = dirname
        self.parser_rules_path = os.path.join(RULESDIR,GAUSSIANRULES)

        #data
        self.data = {} #this goes with data
        self.frontier_uno_occupations = [] #probably should be separate from data
        #these are really stupid names, but eh.
        #use CCLIB for this stuff dummy
        self.HONOs = []
        self.LUNOs = []

        self.alpha_MO_energies = []
        self.alpha_MO_occs = []
        
    
    @property
    def output_path(self):
         return os.path.join(self.dirname,self.basename) + self.output_extension

    @property
    def json_path(self):
        return os.path.join(self.dirname,self.basename) + '.json'

    def read_json(self,filename = None):
        if filename is None: filename = self.json_path
        with open(filename,'r') as json_file:
            self.data = json.load(json_file)

    #check syntax
    def write_json(self,filename = None):
        if filename is None: filename = self.json_path
        with open(filename,'w') as json_file:
            json.dump(self.data,json_file,indent="")

    def read_raw_state(self):
        self.data = file_parser.extract_data(self.output_path,self.parser_rules_path)
        if not self.data['success']:
            if self.debug: print("warning: reading data from failed job!")
        return self

    def parse_frontier_UNO_occupations(self):
        '''
        here, we parse everything [2.00, 0.00]
        '''
        if self.debug: print(F"reading file at {self.output_path}")
        with open(self.output_path,'r') as output_file:
            lines = output_file.readlines()
        occupations = []
        search = False
        for line in lines:
            if re.search(r'Natural Orbital Coefficients',line):
                search = True
                occupations = []
           
            elif re.search(r'Condensed to atoms',line):
         
                search = False

            if search and re.search(r'Eigenvalues',line):
                if self.debug: print(line)
                matches = re.findall(r'(\d\.\d+)',line)
                if self.debug: print(matches)
                occupations.extend(matches)
        occupations = [float(occ) for occ in occupations]

        if self.debug: print("OCCUPATIONS BEFORE FILTERING")
        if self.debug: print(occupations)
        
        try:
            last_2 = len(occupations) - 1 - occupations[::-1].index(2.000) 
        except:
            last_2 = 0 #just use the start of the list if none
        try:
            first_0 = occupations.index(0.000)
        except:
            first_0 = -1 #just use the end of the list if none

        if self.debug: print(last_2)
        if self.debug: print(first_0)
        if self.debug: print("OCCUPATIONS:")
        if self.debug: print(occupations)
        #find index of first one or last value larger than one
        one_found = False
        hono_end = -1
        for index, value in enumerate(occupations):
            # print(value)
            if value == 2.000:
                if self.debug: print('2.000 found')
                hono_end = index + 1
                if self.debug: print(hono_end)
                
            elif value == 1.000:
                if self.debug: print('1.000 found')
                hono_end = index + 1
                if self.debug: print('warning: last hono 1.000, check for edge case')
                if self.debug: print(hono_end)
                break
                
            elif value < 1.000:
                if self.debug: print('val less than 1')
                hono_end = index
                if self.debug: print(hono_end)
                break #this break statement fixed it
                
        if self.debug: print(f"hono_end: {hono_end}")

        self.HONOs = occupations[:hono_end]
        self.LUNOs = occupations[hono_end:]

        HONO = self.HONOs[-1]
        LUNO = self.LUNOs[0]
 
        T_HO = (HONO - LUNO) / 2
        gamma_0 = 1 - 2*T_HO/(1 + T_HO**2)
        # print(gamma_0)
        self.data['diradical_character_yamaguchi'] = gamma_0
        
        self.data['diradical_character_naive'] = self.LUNOs[0]
        if len(self.LUNOs) >= 2:
            self.data['tetraradical_character_naive'] = self.LUNOs[1]
        else:
            self.data['tetraradical_character_naive'] = 0

        return self
        
    def prune_data(self):
        '''
        should have a function to strip 
        misleading intermediate values from output files
        for now, get rid of anything with None as its value
        '''
        new_dict = {}
        for k,v in self.data.items():
            if v is not None:
                new_dict[k] = v
        self.data = new_dict
        return self


    def thermal_energies(self):
        '''
        '''
        E_el_au = self.data['E_el_au']
        try:
            G_au = self.data['G_au']
            H_au = self.data['H_au']
            # E_au = self.data['E_au']
            self.data['G_minus_E_el_au'] = G_au - E_el_au
            self.data['H_minus_E_el_au'] = H_au - E_el_au
            # self.data['E_minus_E_el_au'] = E_au - E_el_au
            self.data['thermochem'] = True
        except:
            self.data['thermochem'] = False
        return self
    
    def delta_E_homo_lumo(self):
        raise NotImplementedError()


    def parse_spin_squared(self):
        if self.debug: print(F"reading file at {self.output_path}")
        with open(self.output_path,'r') as output_file:
            lines = output_file.readlines()
        occupations = []
        search = False
        for line in lines:
            search_string = r'(?:<S\*\*2>=\s*)(-?\d\.\d+)' 
            match = re.search(search_string,line)
            if match:
                s_squared = float(match.group(1))
                if s_squared == -0.0:
                    s_squared = 0.0
                if s_squared < 0:
                    raise ValueError('negative <S**2>!')
                self.data['<S**2>'] = s_squared 
                # print(line)
                # print(s_squared)
    
    def pp_routine(self):
        '''
        TODO: this should raise an exception if the job isn't
        orca. 
        '''
        unos_parsed = True
        bs_parsed = True        
        self.read_raw_state()
        self.prune_data()
        self.thermal_energies()
        
        try:
            self.parse_frontier_UNO_occupations()
        except: 
            unos_parsed = False
      
        self.parse_spin_squared()
            
        self.data = delta_unit_conversions(self.data)
        
        self.write_json()
        if not unos_parsed or not bs_parsed:
            if self.debug: print("warning in run with")
            if self.debug: print(f"directory: {self.dirname}")
            if self.debug: print(f"basename: {self.basename}")
            if self.debug: print(f"GAUSSIAN JOB")
            if not unos_parsed and self.debug: print("Could not parse UNO occs")
            if not bs_parsed and self.debug: print("Could not parse BS spin-corrected energies")













##################################################

# OTHER FUNCTIONS

##################################################



def delta_unit_conversions(data):
    '''
    '''
    #put these in a json blob somewhere
    #find a database and get citations for these UCs
    #these values from http://www.yorku.ca/renef/constants.pdf
    ucs = [
        ('kcal_mol-1',627.5),
        ('kj_mol-1',2625),
        ('eV' , 27.211),
    ]
    new_dict = {}
    for key,value in data.items():
        if match := re.match(r'(Delta\w+)(?:au)',key):
            for unit_conversion in ucs:
                new_key = match.group(1) + unit_conversion[0]
                new_value = value * unit_conversion[1]
                new_dict[new_key] = new_value
        new_dict[key] = value
        
    return new_dict
