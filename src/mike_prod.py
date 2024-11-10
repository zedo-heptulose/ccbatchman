import batch_runner

br = batch_runner.BatchRunner()
br.debug = True
br.scratch_directory = '/gpfs/research/alabuginlab/gage/michael/quick/'
br.batchfile = 'batchfile.csv'
br.max_jobs_running = 20
br.read_batchfile()
#br.try_parse_all_jobs()
br.MainLoop()
