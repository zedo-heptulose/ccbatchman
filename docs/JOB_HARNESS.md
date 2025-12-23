# Job Harness Module Documentation

## Overview

`job_harness.py` provides classes for managing individual computational chemistry jobs. Each `JobHarness` instance represents a single calculation, handling submission, status tracking, output parsing, and post-processing.

## Class Hierarchy

```
JobHarness (base class)
    ├── GaussianHarness
    ├── ORCAHarness
    ├── CRESTHarness
    ├── xTBHarness
    └── pyAromaHarness
```

## JobHarness Base Class

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `directory` | str | `'./'` | Job directory path |
| `job_name` | str | `''` | Base name (matches input file without extension) |
| `status` | str | `'not_started'` | Current job status |
| `job_id` | int | `None` | SLURM job ID |
| `output_extension` | str | `'.out'` | Output file extension |
| `ruleset` | str | ORCARULES | Path to file_parser rules |
| `restart` | bool | `True` | Whether to use existing temp files |
| `mode` | str | `'slurm'` | Execution mode (slurm or direct) |
| `tmp_extension` | str | `'.tmp'` | Temp file extension for cleanup |

### Status Values

- `not_started` - Job has not been submitted
- `pending` - Job submitted, waiting in SLURM queue (PD)
- `running` - Job currently executing (R)
- `succeeded` - Job completed successfully
- `failed` - Job completed with errors

### Key Methods

#### `get_id()`
Discovers job ID from filesystem:
```python
def get_id(self):
    # Looks for slurm-{id}.out files in directory
    # Sets self.job_id to the highest ID found
    # Safe for resubmitted jobs (takes max ID)
```
**Design note:** Uses max(slurm IDs) to handle user resubmissions safely.

#### `update_status()`
**The core status-checking method.** Flow:
```
1. If no job_id, call get_id()
2. Call squeue --job {job_id}
3. Parse squeue output:
   - If error or empty → job not in queue
   - If 'PD' → status = 'pending'
   - If 'R' → status = 'running'
4. If not in queue:
   - Check if output file exists
   - If exists → call check_success_static()
   - If not exists → status = 'not_started'
```

**Performance issue:** Makes one subprocess call per invocation.

#### `check_success_static()`
Parses output file to determine success/failure:
```python
def check_success_static(self):
    # 1. Check output file exists
    # 2. Call file_parser.extract_data() with ruleset
    # 3. Call interpret_fp_out() to set status
```

#### `interpret_fp_out(file_parser_output)`
Base implementation:
```python
def interpret_fp_out(self, file_parser_output):
    self.status = 'succeeded' if file_parser_output['normal_exit'] else 'failed'
```
**Overridden by subclasses** for program-specific success criteria.

#### `submit_job()`
Submits job to SLURM:
```python
def submit_job(self):
    # 1. Run: sbatch {job_name}.sh
    # 2. Parse job ID from output
    # 3. Set status = 'pending'
    # 4. Write run_info.json
```

#### `OneIter()`
Single iteration of job monitoring (called by BatchRunner):
```python
def OneIter(self):
    # 1. Read run_info.json
    # 2. Call update_status()
    # 3. Write run_info.json
    # 4. If running/succeeded: parse_output()
    # 5. If failed: prune_temp_files()
    # 6. If succeeded: final_parse()
```

#### `final_parse()`
Post-processing hook. Base class does nothing. Overridden by subclasses.

#### `parse_output()`
Extracts data from output file using file_parser:
```python
def parse_output(self):
    # 1. Read output file with file_parser.extract_data()
    # 2. Write results to {job_name}.json
```

### Serialization

#### `to_dict()` / `from_dict()`
Convert to/from dictionary for JSON serialization.

#### `write_json()` / `read_json()`
Persist state to `run_info.json`:
```json
{
    "directory": "/path/to/job",
    "job_name": "calculation",
    "status": "succeeded",
    "job_id": 12345678,
    "restart": true,
    "ruleset": "/path/to/rules.dat"
}
```

## Program-Specific Subclasses

### GaussianHarness

| Attribute | Value |
|-----------|-------|
| `output_extension` | `.log` |
| `input_extension` | `.gjf` |
| `ruleset` | GAUSSRULES |

**`interpret_fp_out()` logic:**
- For OPT+FREQ: requires `normal_exit_opt_freq` AND `normal_exit_opt_freq_2`
- Fails if `imaginary_frequencies` detected
- Otherwise: just checks `normal_exit`

**`final_parse()`:** Extracts final coordinates to `{job_name}.xyz`

### ORCAHarness

| Attribute | Value |
|-----------|-------|
| `output_extension` | `.out` |
| `input_extension` | `.inp` |
| `ruleset` | ORCARULES |

**`interpret_fp_out()` logic:**
- For OPT: requires `normal_exit` AND `opt_normal_exit`
- Fails if `imaginary_frequencies` detected
- Otherwise: just checks `normal_exit`

**`final_parse()`:** Calls `OrcaPostProcessor.orca_pp_routine()`

### CRESTHarness, xTBHarness, pyAromaHarness

Minimal subclasses that set appropriate rulesets and extensions.

## File Parser Rules

Each program has a rules file in `config/file_parser_config/`:
- `gaussian_rules.dat`
- `orca_rules.dat`
- `xtb_rules.dat`
- `crest_rules.dat`
- `pyaroma_rules.dat`

These define regex patterns for extracting success/failure indicators from output files.

## Usage Patterns

### Standalone Job Management
```python
job = GaussianHarness()
job.directory = '/path/to/job'
job.job_name = 'opt_freq'
job.MainLoop()  # Submit and wait for completion
```

### With BatchRunner
```python
# BatchRunner creates harnesses via:
job = batch_runner.create_job_harness(program)
job.job_name = row['job_basename']
job.directory = row['job_directory']
job.update_status()
```

## Critical Design Notes

1. **get_id() uses max(slurm IDs)**: This handles cases where users manually resubmit jobs - always takes the most recent submission.

2. **update_status() calls squeue per job**: Current bottleneck for large batches. Each call is a subprocess.

3. **run_info.json status can be stale**: The status field in run_info.json is written after each update but can become stale if:
   - Job finishes between writes
   - BatchRunner crashes
   - User manually intervenes

4. **Output file is ground truth**: For completed jobs, the output file (parsed via file_parser) is the authoritative source for success/failure.

5. **SLURM queue is ground truth for active jobs**: For running/pending status, squeue output is authoritative.

## Potential Improvements

1. **Batch squeue support**: Add method to accept pre-fetched squeue results instead of calling subprocess.

2. **Parallel output parsing**: file_parser calls could be parallelized for large batches.

3. **Caching**: Cache squeue results for short periods during batch operations.
