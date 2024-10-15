import batch_runner

br = batch_runner.BatchRunner()
br.debug = True
br.scratch_directory = '/gpfs/home/gdb20/computations/test/h2o2test/'
br.batchfile = 'batchfile.csv'
br.max_jobs_running = 10
br.MainLoop()
