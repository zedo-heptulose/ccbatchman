# Job Status Checking (progcheck)

This document describes CCBatchMan's job status checking and failure analysis system.

## Overview

The `progcheck.py` module provides utilities for:
1. Loading and querying ledger files
2. Classifying job failures by type
3. Analyzing computational chemistry-specific errors
4. Generating statistics and visualizations

## Quick Usage

```python
import progcheck

# Load the ledger
ledger = progcheck.load_ledger('/path/to/working_dir', '__ledger__.csv')

# Classify failures
failures = progcheck.classify_failures(ledger, '/path/to/working_dir')

# Further categorize computational errors
detailed = progcheck.categorize_errors(failures, '/path/to/working_dir')

# Get statistics
stats = progcheck.get_outcome_statistics(detailed)
print(stats)

# Filter by specific failure type
imag_freq_failures = progcheck.filter_by_fail(detailed, 'imaginary_freq')

# Visualize
progcheck.plot_outcomes(stats, save_path='failures.png')
```

## Functions

### `load_ledger(working_path, ledger_filename='__ledger__.csv')`

Load the batch runner ledger from disk.

**Parameters:**
- `working_path` - Directory containing the ledger
- `ledger_filename` - Name of the CSV file (default: `__ledger__.csv`)

**Returns:**
- `pd.DataFrame` with columns: `job_id`, `job_basename`, `job_directory`, `job_status`, `program`, etc.

### `classify_failures(ledger, working_path, verbose=False)`

Analyze failed jobs and classify them by SLURM/system-level failure type.

**Parameters:**
- `ledger` - DataFrame from `load_ledger()`
- `working_path` - Base path for job directories
- `verbose` - Print extra information

**Returns:**
- DataFrame with columns: `full_path`, `identifier`, `system`, `method`, `outcome`

**Classification Logic:**
1. Find the latest SLURM output file (`slurm-*.out`)
2. Run `seff {job_id}` to get SLURM job status
3. Classify based on status line:
   - `COMPLETED` (but failed) → `FAILED`
   - `NODE_FAIL` → `NODE_FAIL`
   - `TIMEOUT` → `TIMEOUT`
   - `OUT_OF_MEMORY` → `OUT_OF_MEMORY`
   - Other → `OTHER`
   - No SLURM output → `NO_SLURM_OUTPUT`

### `categorize_errors(data, working_path)`

Further categorize jobs that failed due to computational chemistry errors.

**Parameters:**
- `data` - DataFrame from `classify_failures()`
- `working_path` - Base path for job directories

**Returns:**
- DataFrame with refined `outcome` column

**Classification Logic:**
1. Parse output file using `file_parser`
2. Check parsed flags:
   - `imaginary_frequencies` → `imaginary_freq`
   - `opt_fail` → `opt_maxcycle`
   - `scf_fail` → `scf_fail`
   - `bad_internals` → `bad_internals`
   - Not `normal_exit_opt_freq_2` → `bad_stationary_point`

### `regenerate_jobs(data, new_configs)`

Generate updated job configurations for failed jobs.

**Parameters:**
- `data` - DataFrame with job information
- `new_configs` - Dictionary of settings to update

**Returns:**
- Dictionary mapping job identifiers to updated configuration dicts

**Example:**
```python
# Increase walltime for all timeout failures
timeouts = progcheck.filter_by_fail(data, 'TIMEOUT')
new_jobs = progcheck.regenerate_jobs(timeouts, {'runtime': '5-00:00:00'})
```

### `get_outcome_statistics(data)`

Calculate statistics on job outcomes.

**Parameters:**
- `data` - DataFrame with `outcome` column

**Returns:**
- Dictionary with keys:
  - `total_jobs` - Total number of jobs
  - `outcome_counts` - Dict of outcome → count
  - `outcome_percentages` - Dict of outcome → percentage

### `filter_by_fail(data, fail_type)`

Filter jobs by failure type.

**Parameters:**
- `data` - DataFrame with `outcome` column
- `fail_type` - String or list of strings

**Returns:**
- Filtered DataFrame

**Example:**
```python
# Single type
scf_fails = progcheck.filter_by_fail(data, 'scf_fail')

# Multiple types
recoverable = progcheck.filter_by_fail(data, ['imaginary_freq', 'bad_stationary_point'])
```

### `plot_outcomes(stats_dict, title, save_path, figsize)`

Create a bar chart of job outcomes.

**Parameters:**
- `stats_dict` - Output from `get_outcome_statistics()`
- `title` - Plot title (default: 'Computational Chemistry Job Outcomes')
- `save_path` - Path to save figure (optional)
- `figsize` - Figure size tuple (default: (10, 6))

**Color Coding:**
- Green: System failures (NODE_FAIL, TIMEOUT, OUT_OF_MEMORY)
- Orange/Red: Chemistry failures (imaginary_freq, opt_maxcycle, scf_fail, etc.)
- Blue: Other failures (FAILED, OTHER, NO_SLURM_OUTPUT)

## Failure Type Reference

### System-Level Failures

| Outcome | Description | Typical Resolution |
|---------|-------------|-------------------|
| `NODE_FAIL` | Compute node crashed | Resubmit (usually transient) |
| `TIMEOUT` | Job exceeded walltime | Increase `runtime` |
| `OUT_OF_MEMORY` | Memory limit exceeded | Increase `mem-per-cpu` or reduce cores |
| `NO_SLURM_OUTPUT` | No SLURM file found | Check job was actually submitted |

### Computational Chemistry Failures

| Outcome | Description | Typical Resolution |
|---------|-------------|-------------------|
| `imaginary_freq` | Converged to transition state | Re-optimize from perturbed geometry |
| `opt_maxcycle` | Optimization hit max cycles | Increase cycles or use better initial geometry |
| `scf_fail` | SCF did not converge | Adjust convergence settings |
| `bad_internals` | Internal coordinate issues | Use Cartesian coordinates |
| `bad_stationary_point` | Freq calc failed after opt | Re-optimize with tighter criteria |

## Integration with Restart Handler

The `restart_jobs.py` module uses similar logic to `progcheck` but is designed for automatic recovery rather than analysis. See `RESTART_HANDLING.md` for details.

Key difference: `restart_jobs.check_cause()` is called per-job during batch_runner execution, while `progcheck` functions operate on entire ledgers for post-hoc analysis.

## Example Workflow: Analyzing a Failed Batch

```python
import progcheck

# 1. Load ledger
working_path = '/path/to/track1_bs_dft'
ledger = progcheck.load_ledger(working_path)

# 2. Filter to failed jobs only
failed = ledger[ledger['job_status'] == 'failed']
print(f"Total failed: {len(failed)}")

# 3. Classify by SLURM status
classified = progcheck.classify_failures(failed, working_path)

# 4. Get detailed chemistry errors
detailed = progcheck.categorize_errors(classified, working_path)

# 5. Statistics
stats = progcheck.get_outcome_statistics(detailed)
print(f"Breakdown: {stats['outcome_counts']}")

# 6. Visualize
progcheck.plot_outcomes(stats, save_path='failure_analysis.png')

# 7. Filter for recoverable errors
recoverable = progcheck.filter_by_fail(detailed, ['imaginary_freq', 'bad_stationary_point'])
print(f"Recoverable: {len(recoverable)}")
```

## Notes

- The module uses `seff` (SLURM) for job status queries - this must be available on the system
- Output file parsing uses `file_parser` with program-specific rules
- The `categorize_errors` function saves parsed data as JSON files alongside outputs
