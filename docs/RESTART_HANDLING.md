# Restart Handling System

This document describes CCBatchMan's automatic job restart system, which detects and recovers from common calculation failures.

## Overview

The restart system (`restart_jobs.py`) is invoked by `batch_runner.py` when using the `-r` flag. It:
1. Analyzes failed jobs to determine the cause of failure
2. Creates a backup of the failed job directory (`{theory}_history_N`)
3. Modifies job configuration based on failure type
4. Regenerates input files with updated settings
5. Resets the job status to `not_started` so it can be resubmitted

## Usage

Enable restart handling by running batch_runner with the `-r` flag:

```bash
python3 -m ccbatchman.src.batch_runner batchfile.csv -j 30 -r
```

The `-r` flag should always be used unless you want failed jobs to remain failed.

## Failure Detection

### Failure Cause Categories

The `check_cause()` function analyzes failed jobs and returns one of:

| Cause | Description | Source |
|-------|-------------|--------|
| `imaginary_freq` | Optimization converged to a transition state | Output file parsing |
| `bad_stationary_point` | Frequency calculation didn't complete normally | Output file parsing |
| `opt_maxcycle` | Optimization hit maximum cycles | Output file parsing |
| `scf_fail` | SCF did not converge | Output file parsing |
| `bad_internals` | Internal coordinate issues | Output file parsing |
| `NODE_FAIL` | Compute node crashed | SLURM `seff` |
| `TIMEOUT` | Job exceeded time limit | SLURM `seff` |
| `OUT_OF_MEMORY` | Job exceeded memory limit | SLURM `seff` |
| `NO_SLURM_OUTPUT` | SLURM output file not found | File check |

### Detection Flow

1. Check if SLURM output files exist
2. Run `seff {job_id}` to get SLURM job status
3. If SLURM reports COMPLETED but job failed, parse output file
4. Use `file_parser` with program-specific rules to extract error information
5. Categorize based on parsed flags

## Restart Strategies

### Gaussian Imaginary Frequencies

**Strategy:** Read geometry from checkpoint (which has been perturbed along imaginary mode by the freq calculation), reoptimize.

**Config changes:**
```python
{
    'xyz_file': None,  # Use checkpoint instead
    'other_keywords': merged_keywords + ['geom=allcheck'],
}
```

Notes:
- Original `other_keywords` (e.g., `emp=gd3`) are preserved
- Conflicting `geom=` keywords are filtered
- `mix_guess` setting is preserved (singlets need it)

### Gaussian Bad Stationary Point

**Strategy:** Read geometry and force constants from checkpoint, re-optimize with `opt=readfc`.

**Config changes:**
```python
{
    'xyz_file': None,
    'run_type': 'opt=readfc freq',  # Modified from original
    'other_keywords': merged_keywords + ['geom=allcheck'],
}
```

### ORCA Imaginary Frequencies

**Strategy:** Use the final xyz geometry from the failed calculation.

**Config changes:**
```python
{
    'xyz_file': f"{theory}.xyz",  # Use output geometry
}
```

### NODE_FAIL

**Strategy:** Reduce core count (may avoid problematic nodes).

**Config changes:**
```python
{
    'num_cores': 10,
}
```

### TIMEOUT

**Strategy:** Increase walltime.

**Config changes:**
```python
{
    'runtime': '5-00:00:00',
}
```

## Keyword Merging

The `merge_keywords()` function prevents loss of important keywords during restart:

```python
def merge_keywords(original, restart_keywords, conflicts):
    """Merge original keywords with restart keywords, filtering conflicts.
    
    Args:
        original: Original other_keywords list from job_config.json
        restart_keywords: Keywords to add for restart
        conflicts: Keyword prefixes to filter from original (e.g., ['geom='])
    
    Returns:
        tuple: (merged_keywords, filtered_keywords)
    """
```

Example:
```python
original = ['emp=gd3', 'pop=NO', 'geom=modredundant']
merged, filtered = merge_keywords(original, ['geom=allcheck'], ['geom='])
# merged = ['emp=gd3', 'pop=NO', 'geom=allcheck']
# filtered = ['geom=modredundant']
```

When keywords are filtered, a `RESTART_WARNING.txt` file is created in the job directory documenting what changed.

## Directory Structure After Restart

```
_gas_0_1_alkene_linker/
  cam-b3lyp_6-31gdp_opt_freq_gaussian/     # Current (restarted) job
    job_config.json                         # Updated config
    cam-b3lyp_6-31gdp_opt_freq_gaussian.gjf # New input
    RESTART_WARNING.txt                     # If keywords were filtered
  cam-b3lyp_6-31gdp_opt_freq_gaussian_history_0/  # First failed attempt
    job_config.json                         # Original config
    cam-b3lyp_6-31gdp_opt_freq_gaussian.gjf # Original input
    cam-b3lyp_6-31gdp_opt_freq_gaussian.log # Failed output
    cam-b3lyp_6-31gdp_opt_freq_gaussian.json # Parsed data
    run_info.json                           # Original run metadata
  cam-b3lyp_6-31gdp_opt_freq_gaussian_history_1/  # Second failed attempt (if any)
    ...
```

## API Reference

### Main Functions

#### `check_cause(job_status, directory, theory, id=None, old=False, debug=False)`
Analyze a job to determine why it failed.

#### `create_handle_fail(ledger_path)`
Factory function that returns a `handle_fail(row)` function configured with the ledger path.

#### `rewrite_job(row, new_settings, ledger_path)`
Archive failed job, apply new settings, regenerate inputs, and update ledger.

#### `restart_routine(ledger_path)`
Main entry point: load ledger, apply `handle_fail` to all rows.

### Helper Functions

#### `merge_keywords(original, restart_keywords, conflicts)`
Merge keyword lists while filtering conflicts.

#### `get_ledger(root, directory, ledger, debug=False)`
Load ledger and augment with failure analysis columns.

#### `create_new_job(config, program)`
Generate new input/script files from a config dict.

## Limitations and TODOs

1. **Keyword filtering only handles `other_keywords`** - Other keyword sources like `mix_guess` are handled separately. See TODO in source code.

2. **NODE_FAIL/TIMEOUT handling is crude** - Changes are hardcoded values, not adaptive.

3. **No recovery for SCF failures** - These typically need manual intervention.

4. **CREST jobs not handled** - Will be skipped with a message.

5. **History numbering uses simple incrementing** - Uses `_history_0`, `_history_1`, etc.

## Integration with Batch Runner

The batch runner calls the restart system via:

```python
# In batch_runner.py
if args.restart_failed:
    restart_jobs.restart_routine(ledger_path)
```

This is called after status checking but before job submission, allowing failed jobs to be fixed and resubmitted in the same cycle.
