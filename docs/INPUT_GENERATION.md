# CCBatchMan Input Generation Module Documentation

This document provides comprehensive documentation for the input generation system in CCBatchMan, covering the three main modules: `cc_workflow_generator.py`, `input_generator.py`, and `input_combi.py`.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [WorkflowGenerator (cc_workflow_generator.py)](#workflowgenerator)
3. [Input Classes (input_generator.py)](#input-classes)
4. [Combinatorial Generation (input_combi.py)](#combinatorial-generation)
5. [Configuration System](#configuration-system)
6. [Common Workflows](#common-workflows)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The input generation system has three layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    WorkflowGenerator                            │
│              (High-level API for users)                         │
│         cc_workflow_generator.py                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      input_combi.py                             │
│         (Combinatorial expansion & file orchestration)          │
│    - Cartesian product of settings                              │
│    - Directory structure creation                               │
│    - Batchfile generation                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    input_generator.py                           │
│              (Low-level input file writers)                     │
│    - ORCAInput, GaussianInput classes                           │
│    - InputBuilder classes for each program                      │
│    - SbatchScript generation                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. User creates a `WorkflowGenerator` and calls methods to define molecules, states, and calculation steps
2. `WorkflowGenerator.run()` passes configuration to `input_combi.do_everything()`
3. `input_combi` expands all combinations and calls `InputBuilder` classes
4. `InputBuilder` classes generate actual input files and SLURM scripts

---

## WorkflowGenerator

### Class: `WorkflowGenerator`

The primary user-facing API for creating computational chemistry workflows.

### Initialization

```python
from ccbatchman.src.cc_workflow_generator import WorkflowGenerator

wg = WorkflowGenerator()
wg.set_root_dir('/path/to/output')
```

### Core Methods

#### Setting Up the Environment

| Method | Description |
|--------|-------------|
| `set_root_dir(path)` | Set output directory for all calculations |
| `set_molecule_root(path)` | Set base directory for molecule files |
| `set_global_config(config)` | Set global SLURM and calculation settings |
| `set_batch_runner_config(config)` | Configure the batch runner |
| `set_solvents(names, split_directories)` | Define solvation environments |

#### Adding Molecules

| Method | Description |
|--------|-------------|
| `add_molecules_from_directory(dir, group_name)` | Load all .xyz files from directory |
| `add_molecules(dir, cm_group, atoms, group_name, exclude)` | Load molecules with CM state association |

**Example:**
```python
# Simple: load all xyz files
wg.add_molecules_from_directory('source_geometries/')

# Advanced: associate molecules with specific charge-multiplicity states
wg.add_molecules('neutrals/', 'neutral_states', group_name='neutral_mols')
wg.add_molecules('cations/', 'cation_states', group_name='cation_mols')
```

#### Adding Charge-Multiplicity States

```python
wg.add_cm_states([
    {'charge': 0, 'multiplicity': 1, 'alias': '0_1'},                    # Singlet
    {'charge': 0, 'multiplicity': 1, 'uks': True, 'alias': 'bs_singlet'}, # Broken-symmetry singlet
    {'charge': 0, 'multiplicity': 3, 'alias': '0_3'},                    # Triplet
    {'charge': 1, 'multiplicity': 2, 'alias': '1_2'},                    # Cation doublet
])
```

**CM State Configuration Options:**

| Key | Type | Description |
|-----|------|-------------|
| `charge` | int | Molecular charge |
| `multiplicity` | int | Spin multiplicity (2S+1) |
| `alias` | str | Directory name suffix (default: `{charge}_{mult}`) |
| `uks` | bool | Use unrestricted Kohn-Sham (auto-set for mult > 1) |
| `broken_symmetry` | bool | Add ORCA broken symmetry (`brokensym 1,1`) |
| `mix_guess` | bool | Add Gaussian `Guess=Mix` keyword |

**Important:** `broken_symmetry` and `mix_guess` are mutually exclusive - they serve similar purposes for different programs.
**Important:** `broken_symmetry` should be used with multiplicity = 3 for singlet state.

### Adding Calculation Steps

#### ORCA Methods

| Method | Description |
|--------|-------------|
| `add_orca_optfreq_step(name, functional, basis, ...)` | Geometry optimization + frequencies |
| `add_orca_sp_step(name, functional, basis, ...)` | Single point energy |
| `add_orca_roks_step(name, functional, basis, ...)` | ROKS calculation (for SF-TDDFT reference) |
| `add_orca_sf_tddft_sp_step(name, functional, basis, ...)` | SF-TDDFT single point |
| `add_orca_sf_tddft_opt_step(name, functional, basis, ...)` | SF-TDDFT geometry optimization |

#### Gaussian Methods

| Method | Description |
|--------|-------------|
| `add_gaussian_optfreq_step(name, functional, basis, ...)` | Geometry optimization + frequencies |
| `add_gaussian_sp_step(name, functional, basis, ...)` | Single point energy |
| `add_gaussian_nics_step(name, functional, basis, ...)` | NICS aromaticity calculation |
| `add_gaussian_aicd_step(name, functional, basis, ...)` | AICD aromaticity calculation |

#### Other Methods

| Method | Description |
|--------|-------------|
| `add_crest_step(name, config_overrides)` | CREST conformer search |
| `add_xtb_optfreq_step(name, config_overrides, coords_source)` | xTB optimization |

### Step Configuration

All `add_*_step()` methods accept these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Step name (becomes directory name) |
| `functional` | str | DFT functional |
| `basis` | str | Basis set |
| `config_overrides` | dict | Override default settings |
| `coords_source` | str | Source step for coordinates (creates dependency) |
| `xyz_filename` | str | Specific xyz file to use |

**Coordinate Chaining:**

Steps can depend on previous steps for coordinates:
```python
wg.add_orca_optfreq_step('opt_freq', 'B3LYP', 'def2-SVP', coords_source='crest')
wg.add_orca_sp_step('sp_tzvp', 'B3LYP', 'def2-TZVP', coords_source='opt_freq')
```

This creates the dependency: `crest` → `opt_freq` → `sp_tzvp`

### Config Overrides

The `config_overrides` dict can contain any key from the default config templates:

```python
wg.add_gaussian_optfreq_step(
    'cam_opt',
    'cam-b3lyp',
    '6-31G(d,p)',
    config_overrides={
        'other_keywords': ['emp=gd3', 'pop=NO', 'integral=ultrafine', 'Guess=Mix'],
        'runtime': '48:00:00',
        'num_cores': 16,
    }
)
```

**Common Override Keys:**

| Key | Type | Description |
|-----|------|-------------|
| `other_keywords` | list | Additional keywords for route line |
| `runtime` | str | SLURM walltime (e.g., '2-00:00:00') |
| `num_cores` | int | Number of CPU cores |
| `mem_per_cpu_GB` | int | Memory per core in GB |
| `charge` | int | Override charge from CM state |
| `spin_multiplicity` | int | Override multiplicity from CM state |
| `uks` | bool | Force UKS on/off |
| `solvent` | str | Solvent name for implicit solvation |
| `blocks` | dict | ORCA block specifications |

### High-Level Workflow Methods

#### `create_multi_theory_workflow()`

Creates workflows with Cartesian products of functionals and basis sets:

```python
wg.create_multi_theory_workflow(
    optfreq_functionals=['B3LYP', 'CAM-B3LYP'],
    optfreq_basis_sets=['6-31G(d,p)', 'def2-SVP'],
    sp_functionals=['B3LYP'],
    sp_basis_sets=['def2-TZVP'],
    do_crest=True,
    program='Gaussian'
)
```

#### `create_diradical_workflow()`

Specialized workflow for diradical calculations with automatic singlet/triplet single points:

```python
wg.create_diradical_workflow(
    optfreq_functionals=['cam-b3lyp'],
    optfreq_basis_sets=['6-31G(d,p)'],
    sp_functionals=['cam-b3lyp'],
    sp_basis_sets=['6-31G(d,p)'],
    nics_functionals=['cam-b3lyp'],
    nics_basis_sets=['6-31G(d,p)'],
    aicd_functionals=['cam-b3lyp'],
    aicd_basis_sets=['6-31G(d,p)'],
    program='Gaussian',
    do_crest=False,
)
```

~~**Note:** This method applies overrides uniformly to all states. For state-specific settings (e.g., `Guess=Mix` only for singlets), build the workflow manually using individual `add_*_step()` methods.~~

### Running the Workflow

```python
wg.run(overwrite='not_succeeded')
```

**Overwrite Options:**

| Value | Behavior |
|-------|----------|
| `False` | Never overwrite existing directories |
| `True` or `'not_succeeded'` | Overwrite failed/not_started jobs only |
| `'all'` | Overwrite everything |
| `'input_files_only'` | Regenerate inputs without deleting outputs |

---

## Input Classes

### `input_generator.py` Structure

```
Input (base class)
├── CCInput (computational chemistry base)
│   ├── ORCAInput
│   └── GaussianInput
└── SbatchScript
    ├── pyAromaScript
    └── xTBScript

InputBuilder (abstract base)
├── ORCAInputBuilder
├── GaussianInputBuilder
├── CRESTInputBuilder
├── xTBInputBuilder
├── pyAromaInputBuilder
└── BatchRunnerInputBuilder
```

### ORCAInput

Generates ORCA input files (`.inp`).

**Key Attributes:**
- `keywords`: List of `! keyword` lines
- `strings`: Additional lines (e.g., `%maxcore`)
- `blocks`: Dict of `%block ... end` sections
- `charge`, `multiplicity`: Molecular charge and spin
- `xyzfile`: Path to coordinate file

**Generated File Format:**
```
! UKS BHandHLYP def2-SVP D3BJ OPT FREQ
! DefGrid3 VeryTightSCF

%maxcore 3000

%pal
 nprocs 12
end

%scf
 brokensym 1,1
end

* xyzfile 0 1 molecule.xyz
```

### GaussianInput

Generates Gaussian input files (`.gjf`).

**Key Attributes:**
- `keywords`: Route line keywords
- `nprocs`, `mem_per_cpu_gb`: Resource settings
- `charge`, `multiplicity`: Molecular charge and spin
- `title`: Title line
- `coordinates`: Atomic coordinates (read from xyz)
- `post_coords_line`: Text after coordinates (for AICD)

**Generated File Format:**
```
%nprocshared=12
%mem=48gb
%chk=job_name.chk
#OPT FREQ ucam-b3lyp/6-31G(d,p) emp=gd3 integral=ultrafine Guess=Mix

Title line

0 1
 C     0.000000     0.000000     0.000000
 ...

```

### InputBuilder Classes

Each `InputBuilder` subclass:
1. Loads default config from JSON
2. Accepts parameter overrides via `change_params()`
3. Builds input file object via `build_input()`
4. Builds SLURM script via `build_submit_script()`
5. Assembles complete `Job` object via `build()`

**Example Usage (Low-Level):**
```python
from ccbatchman.src.input_generator import ORCAInputBuilder

builder = ORCAInputBuilder()
builder.change_params({
    'functional': 'B3LYP',
    'basis': 'def2-SVP',
    'run_type': 'OPT FREQ',
    'charge': 0,
    'spin_multiplicity': 1,
    'write_directory': '/path/to/job',
    'job_basename': 'optimization',
    'xyz_directory': '/path/to/xyz',
    'xyz_file': 'molecule.xyz',
})
job = builder.build()
job.create_directory()
```

---

## Combinatorial Generation

### `input_combi.py` Functions

#### `do_everything(root_directory, run_settings, *args)`

Main entry point that orchestrates the entire input generation process.

**Parameters:**
- `root_directory`: Base output directory
- `run_settings`: Batch runner configuration
- `*args`: List of configuration dictionaries to combine

**Process:**
1. Calls `sort_flags()` to extract special flags
2. Calls `iterate_inputs()` to generate all combinations
3. Calls `write_input_array()` to create directories and files
4. Calls `write_batchfile()` to create job manifest
5. Calls `write_own_script()` to create workflow manager script

#### `xyz_files_from_directory(directory)`

Scans a directory for `.xyz` files and returns a molecule dict:

```python
molecules = xyz_files_from_directory('geometries/')
# Returns:
# {
#     'molecule1': {'xyz_directory': '/abs/path', 'xyz_file': 'molecule1.xyz'},
#     'molecule2': {'xyz_directory': '/abs/path', 'xyz_file': 'molecule2.xyz'},
# }
```

#### `iterate_inputs(list_of_dict_of_dicts, flag_array)`

Generates Cartesian product of all configuration options:

```python
configs = [
    {'gas': {...}, 'water': {...}},           # Solvents
    {'0_1': {...}, '0_3': {...}},             # CM states  
    {'mol1': {...}, 'mol2': {...}},           # Molecules
    {'opt': {...}, 'sp': {...}},              # Steps
]
# Generates: gas_0_1_mol1_opt, gas_0_1_mol1_sp, gas_0_1_mol2_opt, ...
```

**Note:** settings found in dicts later in the list will override settings found earlier.

### Special Flags

Flags in configuration dicts control directory structure:

| Flag | Effect |
|------|--------|
| `!directories: True` | Creates subdirectory at this level |
| `!coords_from` | Specifies coordinate source step |
| `!xyz_file` | Specifies xyz filename |
| `!orbitals_from` | Specifies orbital source step (ORCA MORead) |
| `!gbw_file` | Specifies .gbw filename |
| `!overwrite` | Controls overwrite behavior |

**Directory Structure Example:**

With `!directories: True` on solvents and molecules:
```
root/
├── gas_0_1_molecule1/
│   ├── opt_freq/
│   └── sp_tzvp/
├── gas_0_1_molecule2/
│   ├── opt_freq/
│   └── sp_tzvp/
└── water_0_1_molecule1/
    ...
```

---

## Configuration System

### Default Config Files

Located in `config/input_generator_config/`:

| File | Purpose |
|------|---------|
| `orca_config.json` | ORCA defaults |
| `gaussian_config.json` | Gaussian defaults |
| `crest_config.json` | CREST defaults |
| `xtb_config.json` | xTB defaults |
| `pyaroma_config.json` | pyAroma (NICS preprocessing) |
| `batch_runner_config.json` | Batch runner defaults |

### Default Templates in WorkflowGenerator

```python
DEFAULT_GLOBAL_CONFIG = {
    "num_cores": 8,
    "mem_per_cpu_GB": 4,
    "runtime": "2-00:00:00",
}

DEFAULT_ORCA_OPTFREQ_CONFIG = {
    "program": "ORCA",
    "integration_grid": "DefGrid3",
    "scf_tolerance": "VeryTightSCF",
    "run_type": "OPT FREQ",
}

DEFAULT_GAUSSIAN_OPTFREQ_CONFIG = {
    "program": "Gaussian",
    "other_keywords": ["Int=Ultrafine"],
    "run_type": "OPT FREQ",
}
```

### Config Key Reference

#### Common Keys (All Programs)

| Key | Type | Description |
|-----|------|-------------|
| `program` | str | 'ORCA', 'Gaussian', 'CREST', 'XTB' |
| `charge` | int | Molecular charge |
| `spin_multiplicity` | int | Spin multiplicity |
| `uks` | bool | Unrestricted calculation |
| `num_cores` | int | CPU cores |
| `mem_per_cpu_GB` | int | Memory per core |
| `runtime` | str | SLURM walltime |
| `write_directory` | str | Output directory |
| `job_basename` | str | Job name |
| `xyz_directory` | str | Source xyz location |
| `xyz_file` | str | xyz filename |
| `solvent` | str | Implicit solvent |
| `other_keywords` | list | Additional keywords |
| `pre_submit_lines` | list | Commands before main command |
| `post_submit_lines` | list | Commands after main command |

#### ORCA-Specific Keys

| Key | Type | Description |
|-----|------|-------------|
| `functional` | str | DFT functional |
| `basis` | str | Basis set |
| `aux_basis` | str | Auxiliary basis (e.g., 'def2/J') |
| `density_fitting` | str | RI method (e.g., 'RIJCOSX') |
| `dispersion_correction` | str | Dispersion (e.g., 'D3BJ') |
| `integration_grid` | str | Grid (e.g., 'DefGrid3') |
| `scf_tolerance` | str | SCF convergence |
| `run_type` | str | Calculation type |
| `blocks` | dict | %block specifications |
| `broken_symmetry` | bool | Add brokensym 1,1 |
| `moread` | bool | Read orbitals from file |
| `natural_orbitals` | bool | Compute UNOs |

#### Gaussian-Specific Keys

| Key | Type | Description |
|-----|------|-------------|
| `functional` | str | DFT functional |
| `basis` | str | Basis set |
| `run_type` | str | Keywords (OPT, FREQ, NMR, etc.) |
| `mix_guess` | bool | Add Guess=Mix |
| `post_coords_line` | str | Text after coordinates |

---

## Common Workflows

### Basic Optimization Workflow

```python
from ccbatchman.src.cc_workflow_generator import WorkflowGenerator

wg = WorkflowGenerator()
wg.set_root_dir('calculations/')
wg.add_molecules_from_directory('geometries/')
wg.add_cm_states([{'charge': 0, 'multiplicity': 1}])

wg.add_crest_step('crest')
wg.add_orca_optfreq_step('opt_freq', 'B3LYP', 'def2-SVP', 
                         coords_source='crest')
wg.add_orca_sp_step('sp_tzvp', 'B3LYP', 'def2-TZVP',
                    coords_source='opt_freq')

wg.set_global_config({'num_cores': 8, 'mem_per_cpu_GB': 4, 'runtime': '24:00:00'})
wg.run()
```

### Diradical Workflow with State-Specific Settings

```python
wg = WorkflowGenerator()
wg.set_root_dir('diradical_calcs/')
wg.add_molecules_from_directory('source_geometries/')

# Singlet with broken-symmetry
wg.add_cm_states([{'charge': 0, 'multiplicity': 1, 'uks': True, 'alias': '0_1'}])

wg.add_gaussian_optfreq_step(
    'opt_freq_gaussian', 'cam-b3lyp', '6-31G(d,p)',
    config_overrides={
        'other_keywords': ['emp=gd3', 'integral=ultrafine', 'Guess=Mix'],
    }
)

# Triplet without Guess=Mix
wg.add_cm_states([{'charge': 0, 'multiplicity': 3, 'alias': '0_3'}])

wg.add_gaussian_optfreq_step(
    'opt_freq_gaussian', 'cam-b3lyp', '6-31G(d,p)',
    config_overrides={
        'other_keywords': ['emp=gd3', 'integral=ultrafine'],  # No Guess=Mix
    }
)

wg.run()
```

### SF-TDDFT Workflow

```python
wg = WorkflowGenerator()
wg.set_root_dir('sf_tddft/')
wg.add_molecules_from_directory('geometries/')
wg.add_cm_states([{'charge': 0, 'multiplicity': 3}])  # Triplet reference

# Step 1: Triplet optimization
wg.add_orca_optfreq_step('triplet_opt', 'BHandHLYP', 'def2-SVP',
                         dispersion='D3BJ')

# Step 2: ROKS triplet (reference for SF-TDDFT)
wg.add_orca_roks_step('roks_triplet', 'BHandHLYP', 'def2-TZVP',
                      dispersion='D3BJ', aux_basis='def2/JK',
                      density_fitting='RIJK',
                      coords_source='triplet_opt')

# Step 3: SF-TDDFT single point
wg.add_orca_sf_tddft_sp_step('sf_tddft', 'BHandHLYP', 'def2-TZVP',
                              dispersion='D3BJ', aux_basis='def2/JK',
                              density_fitting='RIJK',
                              orbitals_source='roks_triplet',
                              coords_source='triplet_opt')

wg.run()
```

---

## Troubleshooting

### Common Issues

#### 1. "oldString not found" when editing generated files

The input generator creates files with specific formatting. If manually editing, preserve exact whitespace.

#### 2. Coordinates not found

Check that:
- `xyz_directory` is an absolute path
- `xyz_file` includes the `.xyz` extension
- The source step has completed successfully

#### 3. Jobs not starting (dependency issues)

The `coords_source` parameter creates dependencies. Check:
- Source step name matches exactly
- Source step is defined before dependent steps
- Ledger shows source step as 'succeeded'

#### 4. Wrong keywords applied to states

When using `create_diradical_workflow()` or similar, overrides apply to ALL states. For state-specific settings, build the workflow manually with separate `add_*_step()` calls for each state.

#### 5. Memory errors in ORCA

ORCA's `%maxcore` is set to 75% of `mem_per_cpu_GB * 1000`. If you need more, override in `config_overrides`:
```python
config_overrides={
    'blocks': {'maxcore': ['4000']},  # 4GB per core
}
```

### Debugging Tips

1. **Check generated configs:**
   Each job directory contains `job_config.json` with all settings used.

2. **Inspect input files:**
   Review the generated `.inp` or `.gjf` files before submitting.

3. **Ledger status:**
   The `__ledger__.csv` file tracks job status and dependencies.

4. **Batchfile:**
   `batchfile.csv` lists all jobs with their dependency chains.

---

## File Reference

| File | Purpose |
|------|---------|
| `cc_workflow_generator.py` | High-level workflow API |
| `input_generator.py` | Input file classes and builders |
| `input_combi.py` | Combinatorial expansion and orchestration |
| `helpers.py` | Utility functions |
| `format_conversion.py` | Coordinate format conversion |
| `job_harness.py` | Job status checking |
| `batch_runner.py` | Workflow execution engine |

---

*Last updated: December 2025*
