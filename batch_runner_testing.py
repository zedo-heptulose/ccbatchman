import batch_runner

br = batch_runner.BatchRunner()
br.scratch_directory = '/gpfs/home/gdb20/code/input_macros/temp/'
br.batchfile = 'batchfile.csv'
br.max_jobs_running = 15
br.MainLoop()
