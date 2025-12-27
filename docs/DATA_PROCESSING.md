# Data Processing & Parsing Module Documentation

## Overview

CCBatchMan provides a layered architecture for extracting and processing data from computational chemistry output files. The system is designed to work with both CCBatchMan-managed directories and arbitrary directory structures.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        High-Level APIs                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │  data_routines  │  │   ParseTree      │  │  parse_tree_builders  │  │
│  │  (batch extract)│  │  (tree traversal)│  │  (preset configs)     │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────┬───────────┘  │
└───────────┼────────────────────┼────────────────────────┼───────────────┘
            │                    │                        │
┌───────────┼────────────────────┼────────────────────────┼───────────────┐
│           │              Mid-Level APIs                 │               │
│  ┌────────▼────────┐  ┌────────▼─────────┐  ┌──────────▼────────────┐  │
│  │   ParseLeaf     │  │   CompoundNode   │  │   PostProcessors      │  │
│  │ (single job)    │  │   DiradicalNode  │  │ (ORCA/Gaussian)       │  │
│  └────────┬────────┘  └──────────────────┘  └───────────┬───────────┘  │
└───────────┼─────────────────────────────────────────────┼───────────────┘
            │                                             │
┌───────────┼─────────────────────────────────────────────┼───────────────┐
│           │              Low-Level APIs                 │               │
│  ┌────────▼──────────────────────────────────────────────▼────────────┐ │
│  │                      file_parser.extract_data()                    │ │
│  │                    (regex-based line scanning)                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         Rules Files (.dat)                         │ │
│  │                  (config/file_parser_config/*.dat)                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Parsing a Single Output File (Low-Level)

```python
import sys
sys.path.append('/path/to/ccbatchman/src')
import file_parser

# Parse a Gaussian output file
data = file_parser.extract_data(
    'calculation.log',
    '/path/to/ccbatchman/config/file_parser_config/gaussian_rules.dat'
)
print(data['E_el_au'])        # Electronic energy
print(data['normal_exit'])    # True if job completed successfully
```

### Parsing with Postprocessing (Mid-Level)

```python
import postprocessing

# For Gaussian files
pp = postprocessing.GaussianPostProcessor(
    dirname='/path/to/job/directory',
    basename='job_name'  # without extension
)
pp.read_raw_state()           # Parse output file
pp.prune_data()               # Remove None values
pp.thermal_energies()         # Calculate thermal corrections
pp.parse_frontier_UNO_occupations()  # Get natural orbital occupations
pp.parse_spin_squared()       # Extract <S**2>
pp.data = postprocessing.delta_unit_conversions(pp.data)  # Unit conversions
pp.write_json()               # Save to JSON

# Access the data
print(pp.data)
```

### Parsing a CCBatchMan Job Directory (Mid-Level)

```python
import parse_tree

# ParseLeaf automatically detects program type from run_info.json or file extension
leaf = parse_tree.ParseLeaf(basename='cam-b3lyp_6-31gdp_opt_freq_gaussian')
leaf.directory = '/path/to/_gas_0_1_molecule/cam-b3lyp_6-31gdp_opt_freq_gaussian'
leaf.parse_data()

print(leaf.data)  # Dict with all extracted values
```

### Batch Extraction (High-Level)

```python
import data_routines

# Extract data for multiple molecules
df = data_routines.get_molecule_data(
    root='/path/to/calculation/root',
    molecules=['molecule_a', 'molecule_b', 'molecule_c'],
    theory='cam-b3lyp_6-31gdp_opt_freq_gaussian'
)
print(df)  # pandas DataFrame with energies and status
```

---

## Low-Level API: `file_parser`

The `file_parser` module provides regex-based extraction of values from text output files.

### Main Function

```python
file_parser.extract_data(read_filename, ruleset_filename) -> dict
```

**Parameters:**
- `read_filename`: Path to output file (.log for Gaussian, .out for ORCA)
- `ruleset_filename`: Path to rules file defining extraction patterns

**Returns:** Dictionary mapping variable names to extracted values

### Rules File Format

Rules files are located in `config/file_parser_config/` and define how to extract data from output files.

#### Basic Syntax

```
varname ; search_regex ; flag ; var_type ; var_regex
```

| Field | Description |
|-------|-------------|
| `varname` | Name of variable in output dict |
| `search_regex` | Pattern to match target lines |
| `flag` | Extraction behavior (see below) |
| `var_type` | `float`, `int`, or `string` |
| `var_regex` | Optional: custom capture regex |

#### Extraction Flags

| Flag | Behavior |
|------|----------|
| `first` | Keep first match found |
| `last` | Keep last match found (overwrites previous) |
| `largest` | Keep largest value seen |
| `smallest` | Keep smallest value seen |
| `sum_all` | Sum all matches |
| `found` | Boolean: True if pattern found |
| `not_found` | Boolean: True if pattern NOT found |
| `at_least_2` | Boolean: True if pattern found 2+ times |
| `list` | Create numbered entries (`varname_1`, `varname_2`, ...) |

#### Control Flow

```
__after__ ; search_regex    # Only apply following rules after this pattern
__before__ ; search_regex   # Stop special rules when this pattern is found
```

#### Example Rules File (Gaussian)

```
# gaussian_rules.dat
E_el_au ; SCF Done: ; last ; float
E_au ; Sum of electronic and thermal Energies ; last ; float
H_au ; Sum of electronic\s+and\s+thermal\s+Enthalpies ; last ; float
G_au ; Sum of electronic and thermal Free Energies ; last ; float
imaginary_frequencies ; imaginary ; found
normal_exit ; Normal\s*termination\s*of\s*Gaussian ; found
<S**2> ; <S\*\*2> ; last; float
```

#### Creating Custom Rules

For custom output formats, create a new `.dat` file:

```
# my_custom_rules.dat
# Extract total energy from "Total Energy = -123.456789" lines
total_energy ; Total Energy = ; last ; float

# Check for convergence
converged ; Optimization Converged ; found

# Extract all gradient components (creates gradient_1, gradient_2, ...)
gradient_{} ; Gradient Component ; list ; float
```

---

## Mid-Level API: `parse_tree` Module

### ParseLeaf

The workhorse for parsing single calculation directories. Handles program detection and postprocessing automatically.

```python
class ParseLeaf(ParseNode):
    def __init__(self, basename="", **kwargs):
        """
        Args:
            basename: Job name (without file extension)
            lazy: If True, read from existing JSON instead of re-parsing
        """
```

**Key Attributes:**
- `directory`: Path to job directory
- `basename`: Job name (e.g., 'cam-b3lyp_6-31gdp_opt_freq_gaussian')
- `data`: Dict containing extracted data (populated after `parse_data()`)

**Program Detection:**
1. If `run_info.json` exists in directory, reads `ruleset` field
2. Otherwise, infers from file extension (`.log` = Gaussian, `.out` = ORCA)

**Example: Parsing Arbitrary Directories**

```python
import parse_tree

# For a directory NOT created by CCBatchMan
leaf = parse_tree.ParseLeaf(basename='my_calculation')
leaf.directory = '/some/arbitrary/path/to/my_calculation'
# Expects: my_calculation.log (Gaussian) or my_calculation.out (ORCA)
leaf.parse_data()

# Data is now available
print(leaf.data['E_el_au'])
print(leaf.data['normal_exit'])
```

### CompoundNode

Combines opt+freq and singlepoint data, transferring thermal corrections from opt+freq to singlepoint electronic energy.

```python
node = parse_tree.CompoundNode(
    basename='molecule_results',
    of_basename='b3lyp_opt_freq',       # opt+freq job name
    sp_basename='ccsd_singlepoint',     # singlepoint job name
    directory='/path/to/molecule',
    recursive=True                       # Parse children automatically
)
node.parse_data()
# node.data now has: E_el_au (from SP), G_au, H_au, E_au (with thermal from opt+freq)
```

### DiradicalNode

Specialized node for diradical calculations with broken-symmetry singlet and triplet singlepoints.

```python
node = parse_tree.DiradicalNode(
    basename='molecule_diradical',
    of_basename='opt_freq',
    singlet_sp_basename='singlet_sp',
    triplet_sp_basename='triplet_sp',
    multiplicity='singlet',              # Which geometry this represents
    directory='/path/to/molecule',
    recursive=True
)
node.parse_data()
# node.data includes spin-corrected energies
```

### ParseTree

Orchestrates depth-first parsing of a tree of calculation directories.

```python
tree = parse_tree.ParseTree()
tree.root_dir = '/path/to/calculations'
tree.root_node = my_compound_node
tree.depth_first_parse()  # Recursively parses all nodes
```

---

## Mid-Level API: `postprocessing` Module

### GaussianPostProcessor

```python
class GaussianPostProcessor:
    def __init__(self, dirname=None, basename=None, debug=False):
        """
        Args:
            dirname: Directory containing output file
            basename: Job name without extension
            debug: Enable verbose output
        """
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `read_raw_state()` | Parse output file using file_parser |
| `prune_data()` | Remove keys with None values |
| `thermal_energies()` | Calculate G/H/E minus E_el corrections |
| `parse_frontier_UNO_occupations()` | Extract natural orbital occupations and diradical character |
| `parse_spin_squared()` | Extract <S**2> expectation value |
| `pp_routine()` | Run full postprocessing pipeline |
| `write_json()` | Save data to JSON file |

**Full Pipeline:**

```python
pp = postprocessing.GaussianPostProcessor(
    dirname='/path/to/job',
    basename='calculation'
)
pp.pp_routine()  # Runs everything and writes JSON
```

### OrcaPostProcessor

Similar interface to GaussianPostProcessor, with ORCA-specific parsing:

```python
class OrcaPostProcessor:
    # Same interface as GaussianPostProcessor, plus:
    def spin_corrected_bs_energies(self):
        """Calculate spin-corrected broken-symmetry energies using Yamaguchi formula"""

    def orca_pp_routine(self):
        """Full ORCA postprocessing pipeline"""
```

### Utility Functions

```python
postprocessing.delta_unit_conversions(data) -> dict
```

Converts any keys matching `Delta*au` to multiple units:
- `kcal_mol-1` (factor: 627.5)
- `kj_mol-1` (factor: 2625)
- `eV` (factor: 27.211)

---

## High-Level API: `data_routines` Module

### get_molecule_data

Extract data for multiple molecules into a pandas DataFrame.

```python
data_routines.get_molecule_data(
    root,                    # Root directory containing molecule subdirs
    molecules,               # List of molecule directory names
    theory,                  # Theory/job subdirectory name
    exclude=[],              # Molecules to skip
    debug=False,
    replace_theories=None,   # Dict mapping molecules to different theories
    check_fail_cause=True,   # Check why failed jobs failed
    silent=False
) -> pd.DataFrame
```

**Expected Directory Structure:**

```
root/
├── molecule_a/
│   └── theory/
│       ├── theory.log (or .out)
│       └── run_info.json (optional)
├── molecule_b/
│   └── theory/
│       └── ...
```

**Returns DataFrame with columns:**
- `molecule`: Molecule name
- `theory`: Theory level
- `status`: Job status (from run_info.json or 'ambiguous')
- `fail_cause`: Failure reason if applicable
- `E_el_au`: Electronic energy
- `E_au`, `H_au`, `G_au`: Thermochemistry

**Example:**

```python
import data_routines

df = data_routines.get_molecule_data(
    root='/path/to/calcs',
    molecules=['benzene', 'naphthalene', 'anthracene'],
    theory='b3lyp-d3_def2-tzvp_opt_freq'
)
print(df[['molecule', 'E_el_au', 'G_au']])
```

### get_reaction_molecule_data

Extract data for molecules involved in multiple reactions.

```python
reactions = {
    'hydrogenation': {
        'reactants': {'ethene': 1, 'h2': 1},
        'products': {'ethane': 1}
    }
}
df = data_routines.get_reaction_molecule_data(
    root='/path/to/calcs',
    reactions=reactions,
    theory='b3lyp_def2-svp'
)
```

---

## Working with Irregular Directory Structures

### Scenario 1: Different Directory Naming

If your directories don't follow CCBatchMan conventions:

```python
import parse_tree

# Manually set directory and basename
leaf = parse_tree.ParseLeaf()
leaf.directory = '/my/custom/path/to/calculation_folder'
leaf.basename = 'output_file_name'  # Will look for output_file_name.log or .out
leaf.parse_data()
```

### Scenario 2: Custom Output Format

Create a custom rules file and use file_parser directly:

```python
import file_parser

# Create my_rules.dat with appropriate patterns
data = file_parser.extract_data(
    '/path/to/output.txt',
    '/path/to/my_rules.dat'
)
```

### Scenario 3: Mixed Program Types

ParseLeaf auto-detects, but you can force a specific program:

```python
import file_parser
import os

# Force Gaussian parsing
GAUSSIAN_RULES = os.path.join(
    os.path.dirname(__file__),
    '../config/file_parser_config/gaussian_rules.dat'
)
data = file_parser.extract_data('ambiguous_output.log', GAUSSIAN_RULES)
```

### Scenario 4: Batch Processing Custom Directories

```python
import parse_tree
import pandas as pd

results = []
for job_dir in my_job_directories:
    leaf = parse_tree.ParseLeaf(basename=os.path.basename(job_dir))
    leaf.directory = job_dir
    try:
        leaf.parse_data()
        results.append({
            'job': job_dir,
            'energy': leaf.data.get('E_el_au'),
            'converged': leaf.data.get('normal_exit', False)
        })
    except Exception as e:
        results.append({
            'job': job_dir,
            'energy': None,
            'converged': False,
            'error': str(e)
        })

df = pd.DataFrame(results)
```

---

## Output Data Dictionary

### Common Keys (All Programs)

| Key | Description | Units |
|-----|-------------|-------|
| `E_el_au` | Electronic energy | Hartree |
| `E_au` | Electronic + thermal energy | Hartree |
| `H_au` | Enthalpy | Hartree |
| `G_au` | Gibbs free energy | Hartree |
| `normal_exit` | Job completed successfully | Boolean |
| `<S**2>` | Spin expectation value | - |

### Gaussian-Specific Keys

| Key | Description |
|-----|-------------|
| `imaginary_frequencies` | Has imaginary frequencies |
| `is_opt_freq` | Is optimization+frequency job |
| `opt_fail` | Optimization failed |
| `scf_fail` | SCF convergence failed |

### ORCA-Specific Keys

| Key | Description |
|-----|-------------|
| `<S^2>_HS` | High-spin S^2 expectation |
| `<S^2>_BS` | Broken-symmetry S^2 expectation |
| `E_high_spin_au` | High-spin electronic energy |
| `E_broken_sym_au` | Broken-symmetry electronic energy |
| `E_dispersion_au` | Dispersion correction energy |
| `E_gCP_au` | Geometric counterpoise correction |

### Postprocessing-Added Keys

| Key | Description |
|-----|-------------|
| `diradical_character_yamaguchi` | Yamaguchi γ₀ diradical character |
| `diradical_character_naive` | LUNO occupation |
| `G_minus_E_el_au` | Thermal correction to G |
| `H_minus_E_el_au` | Thermal correction to H |
| `Delta_*_kcal_mol-1` | Energy differences in kcal/mol |

---

## Troubleshooting

### "ParseLeaf attempted to access non-existent directory"

The specified directory doesn't exist. Check the `directory` attribute.

### "No data read from file!"

The rules file patterns don't match anything in the output file. Check:
1. Output file exists and has expected extension (.log/.out)
2. Rules file matches the program that generated the output
3. Output file contains expected patterns (may be incomplete/failed job)

### "variable regex did not match line"

A rule matched a line but couldn't extract the value. Check `var_regex` pattern.

### Natural orbital parsing fails

- Gaussian: Requires `Pop=NaturalOrbitals` or `Guess=Mix`
- ORCA: Requires UNO calculation (`!UNO` or similar)

---

## See Also

- `BATCH_RUNNER.md` - Running and monitoring calculations
- `INPUT_GENERATION.md` - Generating input files
- `JOB_HARNESS.md` - Individual job management
