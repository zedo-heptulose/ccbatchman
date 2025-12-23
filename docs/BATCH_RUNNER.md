# Batch Runner Module Documentation

## Overview

`batch_runner.py` is the main workflow orchestration module for CCBatchMan. It manages batches of computational chemistry jobs, handling submission, status tracking, dependency resolution, and failure recovery.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BatchRunner                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Batchfile   │───►│    Ledger    │───►│ JobHarness   │       │
│  │  (CSV)       │    │  (DataFrame) │    │  (per job)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                │
│         ▼                   ▼                   ▼                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Job configs  │    │ __ledger__.csv│   │ run_info.json│       │
│  │ (on disk)    │    │  (on disk)   │    │  (per job)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### BatchRunner Class

Main orchestrator class that:
- Reads batchfile.csv to create a ledger of jobs
- Manages job submission via SLURM
- Tracks job status and dependencies
- Handles coordinate/orbital transfer between jobs
- Restarts failed jobs (with `-r` flag)

### Data Structures

#### Ledger (pandas DataFrame)
In-memory representation of all jobs. Columns:
- `job_id`: SLURM job ID (-1 if not submitted)
- `job_basename`: Name of job (matches input file basename)
- `job_directory`: Absolute path to job directory
- `job_status`: One of: `not_started`, `pending`, `running`, `succeeded`, `failed`, `broken_dependency`
- `program`: Gaussian, ORCA, CREST, xTB, pyAroma
- `coords_from`: Relative path to upstream job for geometry
- `xyz_filename`: Name of .xyz file to transfer
- `orbitals_from`: Relative path to upstream job for orbitals
- `gbw_filename`: Name of .gbw file to transfer

#### Batchfile (CSV)
Input file format:
```
run_root_directory=/path/to/calculations
job_basename|job_directory|program|pipe
job1|mol1/step1|Gaussian|
job2|mol1/step2|Gaussian|coords{../step1,}
job3|mol1/step3|ORCA|coords{../step2,};orbitals{../step2,step2.gbw}
```

## Job Status Flow

```
                    ┌──────────────┐
                    │  not_started │
                    └──────┬───────┘
                           │ submit_job()
                           ▼
                    ┌──────────────┐
                    │   pending    │
                    └──────┬───────┘
                           │ SLURM schedules
                           ▼
                    ┌──────────────┐
          ┌─────────│   running    │─────────┐
          │         └──────────────┘         │
          │ parse output                     │ parse output
          ▼                                  ▼
   ┌──────────────┐                   ┌──────────────┐
   │  succeeded   │                   │    failed    │
   └──────────────┘                   └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │broken_dependency│
                                      │(downstream jobs)│
                                      └──────────────┘
```

## Key Methods

### `initialize_run()`
**Current behavior (PROBLEMATIC):**
1. Reads batchfile → creates fresh ledger
2. If `self.restart=True` AND old ledger exists:
   - Merges old ledger with new ledger (keeps old status values)
   - Restarts job harnesses for running/pending jobs

**Problem:** Old ledger can have stale status values that override truth.

### `queue_new_jobs()`
For each `not_started` job with satisfied dependencies:
1. Creates JobHarness for the program type
2. Calls `job.update_status()` to check actual state
3. If truly not started: transfers coords/orbitals, submits job
4. Updates ledger with job_id and status

### `run_jobs_update_ledger()`
For each active JobHarness in `self.jobs`:
1. Calls `job.OneIter()` to check status
2. Updates ledger with current status
3. On failure: copies output to fail_output/, flags broken dependencies
4. On success: removes from active jobs list

### `check_status_all()`
Used with `-s` (status-only) flag:
- Iterates ALL jobs in ledger
- Creates JobHarness, calls `update_status()`
- Updates ledger with true status
- **This is the safe way to rebuild status** (but slow - N squeue calls)

### `dependencies_satisfied(row)`
Checks if upstream job has completed:
1. Checks if coords_from path exists
2. Checks if xyz file exists
3. Reads upstream `run_info.json`, checks `status == 'succeeded'`

### `flag_broken_dependencies()`
Marks all jobs whose dependencies failed as `broken_dependency`.

## Command Line Interface

```bash
python -m ccbatchman.src.batch_runner batchfile.csv [options]

Options:
  -v, --verbose         Enable debug output
  -j N, --num-jobs N    Max parallel jobs (default: 1)
  -s, --status-only     Update status without submitting
  -l FILE, --ledger-filename FILE
                        Custom ledger filename
  -r, --restart-failed  Auto-restart failed jobs
```

## Main Loop Flow

```python
def MainLoop():
    initialize_run()      # Read batchfile, (optionally merge old ledger)
    write_ledger()

    if status_only:
        check_status_all()  # Just update status, don't submit
        return

    while not check_finished():
        run_jobs_update_ledger()  # Check active jobs
        queue_new_jobs()          # Submit ready jobs
        if restart_failed:
            restart_failed_jobs() # Handle failures
        write_ledger()
        sleep(0.1)
```

## Performance Bottlenecks

### Current Issues
1. **N squeue calls**: Each `job.update_status()` calls `squeue --job {id}` (subprocess)
2. **Sequential file I/O**: run_info.json read sequentially per job
3. **Old ledger merge**: Can introduce stale status values

### Proposed Optimizations
1. **Batch squeue**: Single `squeue -u $USER` call, filter by known job IDs
2. **Parallel I/O**: ThreadPoolExecutor for reading run_info.json files
3. **JIT status detection**: Always rebuild status from filesystem, never trust old ledger

## File Locations

Each job directory contains:
- `{basename}.gjf/.inp` - Input file
- `{basename}.sh` - SLURM submission script
- `{basename}.log/.out` - Output file (after completion)
- `{basename}.json` - Parsed output data
- `job_config.json` - Job configuration
- `run_info.json` - Runtime state (job_id, status, etc.)
- `slurm-{id}.out` - SLURM output

## Dependencies

- `job_harness.py` - Individual job management
- `editor.py` - Coordinate/orbital transfer
- `restart_jobs.py` - Failure analysis and restart logic
- `pandas` - Ledger data structure
- `numpy` - NaN handling for missing pipe commands
