import batch_runner
import numpy as np

br = batch_runner.BatchRunner()
br.debug = True
br.scratch_directory = '/gpfs/research/alabuginlab/gage/kimberley/cc_test'
br.batchfile = 'batchfile.csv'
br.max_jobs_running = 10
br.read_batchfile()
#br.try_parse_all_jobs()
#br.initialize_run() #here we make sure everything is overwritten properly
br.MainLoop()
