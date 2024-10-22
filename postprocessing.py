import json
import os
import re
import numpy
import pandas
import file_parser


RULESDIR = 'rules/'
ORCARULES = 'orca_rules.dat'


class OrcaPostProcessor:
    def __init__(self,dirname=None,basename=None):
        #filepath stuff
        self.output_extension = '.out'
        self.basename = basename
        self.dirname = dirname
        self.parser_rules_path = os.path.join(RULESDIR,ORCARULES)

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
            json.dump(self.data,json_file)

    def read_raw_state(self):
        self.data = file_parser.extract_data(self.output_path,self.parser_rules_path)
        if not self.data['success']:
            print("warning: reading data from failed job!")
        return self

    def parse_frontier_UNO_occupations(self):
        '''
        here, we parse everything [2.00, 0.00]
        '''
        with open(self.output_path,'r') as output_file:
            lines = output_file.readlines()
        occupations = []
        search = False
        for line in lines:
            if re.match(r'\s*UHF\s+NATURAL\s+ORBITALS',line):
                search = True
           
            elif re.match(r'\s*QR-MO\s+GENERATION',line):
                break

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
            first_0 = -1 #just use the end of th list if none

        print(last_2)
        print(first_0)
        self.frontier_uno_occupations = occupations[last_2:first_0]
        #find index of first one or last value larger than one
        one_found = False
        hono_end = -1
        for index, value in enumerate(self.frontier_uno_occupations):
            if value == 1.000:
                hono_end = index + 1
                print('warning: last hono 1.000, check for edge case')
                break
            elif value < 1.000:
                hono_end = index
        
        self.HONOs = self.frontier_uno_occupations[0:hono_end]
        self.LUNOs = self.frontier_uno_occupations[hono_end:-1]

        #calculating diradical characters and storing in data
        
        T_HO = (self.HONOs[-1] - self.LUNOs[0]) / 2
        gamma_0 = 1 - 2*T_HO/(1 + T_HO**2)
        self.data['diradical_character_yamaguchi'] = gamma_0
        
        self.data['diradical_character_naive'] = self.LUNOs[0]
        self.data['tetraradical_character_naive'] = self.LUNOs[1]

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

    def delta_unit_conversions(self):
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
        for key,value in self.data.items():
            if match := re.match(r'(Delta\w+)(?:au)',key):
                for unit_conversion in ucs:
                    new_key = match.group(1) + unit_conversion[0]
                    new_value = value * unit_conversion[1]
                    new_dict[new_key] = new_value
            new_dict[key] = value
            
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
        
        self.data['Delta_E_st_spin_corrected_au'] = Delta_E_st_sc
        #d as in "dispersionAndGCP"
        self.data['E_singlet_d_spin_corrected_au'] =\
            E_hs_au - Delta_E_st_sc + E_gCP_au + E_dispersion_au

        #for completeness
        self.data['E_triplet_d_corrected_au'] =\
            E_hs_au + E_gCP_au + E_dispersion_au

        return self
        #TODO: refresh keys used in file parser rules, they are bad
        #TODO: write these keys down somewhere, make a list, or it will get annoying
        
    def delta_E_homo_lumo(self):
        raise NotImplementedError()

    def pp_routine(self):
        unos_parsed = True
        bs_parsed = True        
        self.read_raw_state()
        self.prune_data()
        try:
            self.parse_frontier_UNO_occupations()
        #self.delta_E_homo_lumo()
        except: 
            unos_parsed = False
            
        try:
            self.spin_corrected_bs_energies()
        except:
            bs_parsed = False
        
        self.delta_unit_conversions()
        self.write_json()
        if not unos_parsed or not bs_parsed:
            print("warning in run with")
            print(f"directory: {self.dirname}")
            print(f"basename: {self.basename}")
            print(f"ORCA JOB")
            if not unos_parsed: print("Could not parse UNO occs")
            if not bs_parsed: print("Could not parse BS spin-corrected energies")
