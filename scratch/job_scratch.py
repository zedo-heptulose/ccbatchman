#OH AND H2O2 TESTING
import input_files
import input_combi
import helpers

global_configs = {
        'write_directory' : '/gpfs/home/gdb20/code/temp',
        'xyz_directory' : '/gpfs/home/gdb20/code/temp',
        'charge' : 0
}

molecules = {'h2o2': {
                'xyz_file' : 'h2o2.xyz',
                'charge'   : 0,
                'spin_multiplicity' : 1,
                },
             'oh-radical': {
                'xyz_file' : 'oh.xyz',
                 'charge' : 0,
                'spin_multiplicity' : 2
                  },
            }

crest_settings = {'crest' : {
                    'program' : 'CREST',
                    'functional' : 'gfn2',
                    'quick' : False,
                    'reopt' : False,
                    'cluster' : True,
                    }
                 }

gaussian_settings = {
            'gau' : {
                'program' : 'Gaussian',
                '__coords_from__': 'crest', #this depends_on should write dependencies
                '__coords_file__': 'crest_best.xyz',
                },                      #where the whole name up to and including this phrase is included
           }


functionals = {'b3lyp' : {
                'functional' : 'b3lyp'
                },
            'm06-2x' : {
                'functional' : 'M062X' #ANOTHER flag for being the point at which directories are divided
                },
            'm08-hx' : {
                'functional' : 'M08HX'
                },
            'pbeo' : {
                'functional' : 'PBEPBE'
                },
            }
basis_sets = {'6-31+Gdp' : {
                'basis' : '6-31+G*'
                },
              '6-311+Gdp' : {
                'basis' : '6-311+G*'
                },
              '6-31++Gdp' : {
                'basis' : '6-31++G*'
                },
              '6-311++Gdp' : {
                'basis' : '6-311++G*'
                },
             }
solvents = {'gas' : {
                'solvent' : None
                },
            'water' : {
                'solvent' : 'water'
                },
           }

gaussian_inputs = input_combi.iterate_inputs([molecules,solvents,gaussian_settings,functionals,basis_sets])
crest_inputs = input_combi.iterate_inputs([molecules,solvents,crest_settings])