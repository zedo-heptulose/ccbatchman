# HANDOFF: Batch Runner Performance Improvements

**Date:** December 23, 2025
**Branch:** `feature/jit-ledger-rebuild` (in ccbatchman repo)
**Status:** Implementation in progress

## Problem Summary

BatchRunner has two related issues:

1. **Stale ledger bug**: `initialize_run()` merges old `__ledger__.csv` with fresh batchfile, which can preserve stale status values (like "broken_dependency") even when jobs have actually completed.

2. **Performance bottleneck**: `check_status_all()` and `queue_new_jobs()` call `squeue --job {id}` once per job via subprocess. For 50 jobs = 50 subprocess calls.

## Solution Design

### 1. Add `slurm_cache` parameter to `update_status()` in job_harness.py

Modify `update_status()` to accept optional `slurm_cache` kwarg:
- If `slurm_cache` provided and job_id is in cache → use cached status
- If job_id not in cache → job not running, check output file
- If `slurm_cache` not provided → original squeue call behavior (backward compatible)

### 2. Add `get_all_slurm_statuses()` in batch_runner.py

```python
def get_all_slurm_statuses():
    """
    Single squeue call to get all user's running/pending jobs.
    Returns: {job_id (int): status (str)}  # 'running' or 'pending'
    """
    result = subprocess.run(
        'squeue -u $USER -o "%i|%T" --noheader',
        shell=True, capture_output=True, text=True
    )
    # Parse output, filter to our job IDs, return dict
```

### 3. Modify `check_status_all()` in batch_runner.py

```python
def check_status_all(self, **kwargs):
    slurm_cache = get_all_slurm_statuses()  # Single squeue call
    for i, row in self.ledger.iterrows():
        job = self.create_job_harness(row['program'])
        job.from_dict({'directory': directory, 'job_name': basename})
        job.update_status(slurm_cache=slurm_cache)  # Uses cache
        # ... update ledger
```

### 4. Modify `initialize_run()` in batch_runner.py

Remove old ledger merge logic entirely:
```python
def initialize_run(self):
    self.read_batchfile()  # Fresh ledger from batchfile
    self.check_status_all()  # Runtime status detection with batch squeue
    return self
```

## Files to Modify

### `ccbatchman/src/job_harness.py`

**Location:** `update_status()` method (line ~100)

**Change:** Add `slurm_cache` kwarg handling at the start:

```python
def update_status(self, **kwargs):
    debug = kwargs.get('debug', False)
    slurm_cache = kwargs.get('slurm_cache', None)

    # ... existing get_id() call ...

    if slurm_cache is not None:
        if self.job_id and self.job_id in slurm_cache:
            cached_status = slurm_cache[self.job_id]
            if cached_status == 'running':
                self.status = 'running'
                return
            elif cached_status == 'pending':
                self.status = 'pending'
                return
        else:
            # Job not in cache = not running, check output file
            # Fall through to check_success_static()
            pass
    else:
        # Original squeue logic here (for backward compatibility)
        ...
```

### `ccbatchman/src/batch_runner.py`

**Add function** (near top, after imports):
```python
def get_all_slurm_statuses():
    """Get all user's SLURM jobs in one call. Returns {job_id: status}."""
    try:
        result = subprocess.run(
            'squeue -u $USER -o "%i|%T" --noheader',
            shell=True, capture_output=True, text=True, timeout=30
        )
        statuses = {}
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split('|')
            if len(parts) >= 2:
                job_id = int(parts[0])
                state = parts[1].upper()
                if state in ('RUNNING', 'R'):
                    statuses[job_id] = 'running'
                elif state in ('PENDING', 'PD'):
                    statuses[job_id] = 'pending'
        return statuses
    except Exception as e:
        print(f"Warning: batch squeue failed: {e}")
        return {}
```

**Modify `check_status_all()`** (line ~569):
```python
def check_status_all(self, **kwargs):
    slurm_cache = get_all_slurm_statuses()
    print(f"Got {len(slurm_cache)} running/pending jobs from squeue")
    # ... rest of method, passing slurm_cache to update_status()
```

**Modify `initialize_run()`** (line ~476):
- Remove the `if self.restart and os.path.exists(...)` block entirely
- Add `self.check_status_all()` call after `read_batchfile()`

## Testing Plan

1. **Unit test slurm_cache**:
   ```python
   job = GaussianHarness()
   job.directory = '/path/to/completed/job'
   job.job_name = 'test'
   job.update_status(slurm_cache={})  # Should check output file
   assert job.status in ['succeeded', 'failed', 'not_started']
   ```

2. **Integration test with Track 1**:
   ```bash
   cd recalc_working_dir
   rm __ledger__.csv
   python3 -m ccbatchman.src.batch_runner batchfile.csv -j 30 -s  # status only
   # Should complete quickly with single squeue call
   ```

3. **Verify no stale status**:
   - Check that jobs with output files get correct succeeded/failed status
   - Check that "broken_dependency" is not carried over from old ledger

## Current State

### Completed
- [x] Documentation for batch_runner.py (`docs/BATCH_RUNNER.md`)
- [x] Documentation for job_harness.py (`docs/JOB_HARNESS.md`)
- [x] Merged `feature/sf-tddft-orbital-transfer` to main
- [x] Created branch `feature/jit-ledger-rebuild`
- [x] Design for slurm_cache implementation

### In Progress
- [ ] Modify `update_status()` in job_harness.py

### Not Started
- [ ] Add `get_all_slurm_statuses()` to batch_runner.py
- [ ] Modify `check_status_all()` to use cache
- [ ] Modify `initialize_run()` to remove old ledger logic
- [ ] Testing

## Notes

- `get_id()` in job_harness.py was recently updated to also check run_info.json for job_id (in addition to slurm-*.out files). This is fine and doesn't affect our changes.

- The `self.restart` flag in BatchRunner controls old ledger reading. We're removing this behavior but keeping the flag for potential other uses.

- For jobs not in squeue, we still need to call `check_success_static()` which parses the output file. This is I/O bound but can't be avoided.

## Prompt to Continue

```
Continue implementing batch runner performance improvements.

Read HANDOFF_BATCH_RUNNER_PERF.md in ccbatchman/docs for context.

Current task: Modify update_status() in job_harness.py to accept slurm_cache kwarg.

The logic:
1. If slurm_cache provided and job_id in cache → use cached status (running/pending)
2. If slurm_cache provided but job_id NOT in cache → job finished, fall through to check_success_static()
3. If slurm_cache not provided → original squeue call behavior

Then proceed with:
- Add get_all_slurm_statuses() to batch_runner.py
- Modify check_status_all() to use cache
- Modify initialize_run() to remove old ledger merge
```
