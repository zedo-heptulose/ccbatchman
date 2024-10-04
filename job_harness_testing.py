if __name__ == "__main__":
    import job_harness
    
    jh = job_harness.JobHarness()
    jh.job_name = 'aceticacid_singlet_hf_3c_opt_'
    #use absolute paths whenever possible
    jh.directory = '/gpfs/home/gdb20/test/queue_test/aceticacid_singlet_hf_3c_opt_/'
    
    jh.manage_job()