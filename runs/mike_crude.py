import batch_runner

br = batch_runner.BatchRunner()
br.debug = True
br.scratch_directory = '/gpfs/research/alabuginlab/gage/michael/crude/'
br.batchfile = 'batchfile.csv'
br.max_jobs_running = 5
br.read_batchfile()
#br.try_parse_all_jobs()
#br.initialize_run() #here we make sure everything is overwritten properly
br.MainLoop()
