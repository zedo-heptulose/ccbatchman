# Handoff: CCBatchMan Restart Handler Keyword Fix

**Date:** 2026-01-03
**Status:** Plan complete, ready for implementation

## Problem Summary

When Gaussian jobs fail (imaginary frequencies or bad stationary point) and are restarted by CCBatchMan, the `other_keywords` list is **overwritten** instead of **merged**. This causes keywords like `emp=gd3` to be lost.

**Example:**
```
Original:  ["emp=gd3", "pop=NO", "integral=ultrafine"]
After restart: ["geom=checkpoint", "int=ultrafine nosymm"]  # emp=gd3 LOST!
```

## Root Cause

**File:** `ccbatchman/src/restart_jobs.py` lines 306-329

In `handle_fail()`, the `override_configs` dict contains hardcoded `other_keywords`:
```python
'other_keywords' : [
    'geom=checkpoint',
    'int=ultrafine nosymm'
],
```

Then `rewrite_job()` calls `config.update(new_settings)` which replaces the entire list.

Note: `old_config` is already read from `job_config.json` at line 280-282 but not used for merging.

## Previous Fix Attempt

A fix was attempted that added keyword merging, but the batch_runner crashed with:
```
ValueError: OneIter called without run_info.json existing
```

The crash cause is unclear - empirically the restart handler worked before. Possible cause: `old_config.get('other_keywords', [])` returns `None` if the key exists with value `None`, and iterating over `None` raises TypeError. Fix: use `or []`.

All changes were reverted. Current code is at last committed state.

## Proposed Fix

### 1. Add helper function in `restart_jobs.py`:
```python
def merge_keywords(original, restart_keywords, conflicts):
    """Merge original keywords with restart keywords, filtering conflicts."""
    original = original or []
    filtered = []
    kept = []
    for kw in original:
        if any(kw.lower().startswith(c.lower()) for c in conflicts):
            filtered.append(kw)
        else:
            kept.append(kw)
    return kept + restart_keywords, filtered
```

### 2. Modify `is_gaussian and is_imaginary_freq` case (lines 306-316):
```python
elif is_gaussian and is_imaginary_freq:
    print('Gaussian imaginary frequency')
    original_keywords = old_config.get('other_keywords', []) or []
    merged, filtered = merge_keywords(original_keywords, ['geom=allcheck'], ['geom='])
    if filtered:
        print(f"WARNING: Filtered keywords during restart: {filtered}")
        with open(os.path.join(directory, 'WARNING.txt'), 'w') as f:
            f.write(f"Restart due to: imaginary frequency\n")
            f.write(f"Filtered keywords: {filtered}\n")
            f.write(f"Added keywords: ['geom=allcheck']\n")
    override_configs = {
        'xyz_file': None,
        'other_keywords': merged,
    }
    rewrite_job(row, override_configs, ledger_path)
```

### 3. Modify `is_gaussian and is_bad_stationary_point` case (lines 317-329):
```python
elif is_gaussian and is_bad_stationary_point:
    print('Gaussian bad stationary point')
    original_keywords = old_config.get('other_keywords', []) or []
    merged, filtered = merge_keywords(original_keywords, ['geom=allcheck'], ['geom='])
    if filtered:
        print(f"WARNING: Filtered keywords during restart: {filtered}")
        with open(os.path.join(directory, 'WARNING.txt'), 'w') as f:
            f.write(f"Restart due to: bad stationary point\n")
            f.write(f"Filtered keywords: {filtered}\n")
            f.write(f"Added keywords: ['geom=allcheck']\n")
    override_configs = {
        'xyz_file': None,
        'run_type': old_config['run_type'].lower().replace('opt', 'opt=readfc'),
        'broken_symmetry': False,
        'other_keywords': merged,
    }
    rewrite_job(row, override_configs, ledger_path)
```

## Key Design Decisions

1. **Use `geom=allcheck` for both cases** - consistency
2. **Only filter `geom=` keywords** - don't touch integral, guess, nosymm, etc.
3. **Don't add integral keywords** - keep whatever was in original
4. **Create WARNING.txt** in job directory when keywords are filtered
5. **Use `or []`** to handle case where `other_keywords` is `None`

## Testing Strategy

**Unit test approach (recommended):**
1. Create mock job directory with `job_config.json` containing test keywords
2. Create fake ledger row with `fail_cause='imaginary_freq'`
3. Call `handle_fail()` directly
4. Verify regenerated input contains merged keywords
5. Verify WARNING.txt created if keywords were filtered

## Track 1 Status

Track 1 calculations are paused. To restart after fix is applied:
```bash
cd /gpfs/research/alabuginlab/gage/michael/cleanup_calculations/recalc_working_dir
rm __ledger__.csv
sbatch cc_workflow.sh
```

CCBatchMan will rebuild state from `run_info.json` files.

## Files to Modify

- `ccbatchman/src/restart_jobs.py` - lines 306-329 in `handle_fail()`

## Plan File Location

Full plan with code snippets: `/gpfs/home/gdb20/.claude/plans/drifting-napping-lightning.md`
