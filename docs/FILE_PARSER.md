# File Parser System

This document describes CCBatchMan's output file parsing system, which extracts data from computational chemistry output files using configurable rule files.

## Overview

The file parser (`file_parser.py`) reads output files line-by-line and extracts data based on pattern-matching rules defined in `.dat` rule files. This allows flexible extraction of energies, status flags, and other data from various programs (Gaussian, ORCA, xTB, CREST).

## Quick Usage

```python
import file_parser

# Parse a Gaussian output file
data = file_parser.extract_data(
    'calculation.log',
    'ccbatchman/config/file_parser_config/gaussian_rules.dat'
)

# Access extracted values
scf_energy = data['E_el_au']          # float
free_energy = data['G_au']            # float  
normal_termination = data['normal_exit']  # bool
has_imaginary = data['imaginary_frequencies']  # bool
```

## Rule File Format

Rule files use a semicolon-delimited format:
```
varname ; search_regex ; flag ; [var_type] ; [var_flag] ; [var_regex]
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `varname` | Yes | Name of the variable in output dict |
| `search_regex` | Yes | Regex pattern to match lines |
| `flag` | Yes | Operation to perform (see below) |
| `var_type` | No | Type of extracted value: `float`, `int`, `string` |
| `var_flag` | No | Index of match: `last`, integer index |
| `var_regex` | No | Custom regex for value extraction |

### Operation Flags

| Flag | Description |
|------|-------------|
| `first` | Store first matching value encountered |
| `last` | Store last matching value encountered (overwrites) |
| `largest` | Store the largest value encountered |
| `smallest` | Store the smallest value encountered |
| `sum_all` | Sum all matching values |
| `found` | Set `True` if pattern found, `False` if not found |
| `not_found` | Set `True` if pattern NOT found, `False` if found |
| `at_least_2` | Set `True` if pattern found 2+ times |
| `list` | Create numbered variables: `varname_1`, `varname_2`, etc. |

### Control Flow Directives

Rules can be scoped to specific sections of output files:

```
__after__ ; pattern  
  # Rules here only apply after "pattern" is found
  varname ; search ; flag ; type
__before__ ; pattern
  # Ends the scoped section when "pattern" is found
```

Example from ORCA rules:
```
__after__ ; VIBRATIONAL\s+FREQUENCIES
    imaginary_frequencies; -\s*\d+\.\d+\s*cm\*\*-1 ; found
__before__ ; NORMAL\s+MODES
```

This only looks for imaginary frequencies in the vibrational frequencies section.

### Comments

Lines starting with `#` are comments:
```
# This is a comment
E_el_au ; SCF Done: ; last ; float  # Inline comments NOT supported
```

## Example Rules

### Gaussian Rules (`gaussian_rules.dat`)

```
# Electronic and thermochemical energies
E_el_au ; SCF Done: ; last ; float
E_au ; Sum of electronic and thermal Energies ; last ; float
H_au ; Sum of electronic\s+and\s+thermal\s+Enthalpies ; last ; float 
G_au ; Sum of electronic and thermal Free Energies ; last ; float

# Spin expectation
<S**2> ; <S\*\*2> ; last; float

# Status flags
imaginary_frequencies ; imaginary ; found   
opt_fail ; Optimization stopped ; found
scf_fail ; Convergence failure -- run terminated ; found
bad_internals ; FormBX had a problem ; found
normal_exit ; Normal\s*termination\s*of\s*Gaussian ; found
normal_exit_opt_freq ; Normal\s*termination\s*of\s*Gaussian ; at_least_2
normal_exit_opt_freq_2 ; Stationary point found ; at_least_2
```

### ORCA Rules (`orca_rules.dat`)

```
# Energies
E_el_au ; FINAL SINGLE POINT ENERGY ; last; float
E_au  ; Total thermal energy ; last ; float
H_au  ; Total Enthalpy           ; last; float
G_au ; Final Gibbs free energy ; last; float

# Dispersion (scoped section)
__after__ ; DFT DISPERSION CORRECTION 
  E_dispersion_au ; Dispersion\s+correction  ; last ; float
  E_gCP_au ; gCP\s+correction ; last ; float
__before__ ; FINAL SINGLE POINT ENERGY

# Optimization status
opt_normal_exit ; \*\*\* OPTIMIZATION RUN DONE \*\*\* ; found
opt_fail ; The optimization did not converge but reached ; found
scf_fail ; SCF NOT CONVERGED ; found

# Imaginary frequencies (scoped to vibrations section)
__after__ ; VIBRATIONAL\s+FREQUENCIES
    imaginary_frequencies; -\s*\d+\.\d+\s*cm\*\*-1 ; found
__before__ ; NORMAL\s+MODES

# Broken-symmetry analysis (scoped section)
__after__ ; BROKEN\s+SYMMETRY\s+MAGNETIC\s+
    E_high_spin_au ; E\s*\(High-Spin\); first; float
    E_broken_sym_au ; E\s*\(BrokenSym\); first; float
    <S^2>_HS ; <S\*\*2>\s*\(High-Spin\); first; float
    <S^2>_BS ; <S\*\*2>\s*\(BrokenSym\);first; float
__before__ ; Spin-Hamiltonian\s+Analysis
```

## API Reference

### `extract_data(read_filename, ruleset_filename)`

Main entry point. Parses an output file using the specified rule file.

**Parameters:**
- `read_filename` - Path to output file to parse
- `ruleset_filename` - Path to rule file (`.dat`)

**Returns:**
- `dict` - Variable names mapped to extracted values

**Raises:**
- `ValueError` if no data extracted

### `read_rulesfile(rule_filename)`

Parse a rule file into an actions dictionary.

**Returns:**
- `dict` with keys:
  - `__normal__` - Rules always applied
  - `__after__` - Section start markers
  - `__before__` - Section end markers
  - `{pattern}` - Rules for specific sections

### `read_var_from_line(line, var_type, var_flag, var_regex)`

Extract a typed value from a matched line.

**Parameters:**
- `line` - The matched line
- `var_type` - `float`, `int`, or `string`
- `var_flag` - `last` or integer index
- `var_regex` - Custom regex (defaults based on type)

## Available Rule Files

| File | Program | Key Variables |
|------|---------|---------------|
| `gaussian_rules.dat` | Gaussian | `E_el_au`, `G_au`, `normal_exit`, `imaginary_frequencies` |
| `orca_rules.dat` | ORCA | `E_el_au`, `G_au`, `opt_fail`, `E_high_spin_au` |
| `xtb_rules.dat` | xTB/CREST | `E_el_au`, `G_au`, `Delta_E_homo_lumo_ev` |
| `crest_rules.dat` | CREST | (minimal) |
| `pyaroma_rules.dat` | pyAroma | (minimal) |

## Integration with Other Modules

### Restart Handler

`restart_jobs.py` uses file_parser to determine failure causes:

```python
output = file_parser.extract_data(out_path, orca_rules_path)

if output.get('imaginary_frequencies', False):
    outcome = 'imaginary_freq'
elif output.get('opt_fail', False):
    outcome = 'opt_maxcycle'
```

### Data Processing

The `data_routines.py` module uses file_parser for batch data extraction. See `DATA_PROCESSING.md` for details.

## Adding New Rules

1. Identify the pattern in the output file
2. Determine what type of value to extract
3. Choose the appropriate flag
4. Add the rule to the appropriate `.dat` file

**Example:** Adding ZPE extraction for Gaussian:
```
ZPE_au ; Zero-point correction= ; last ; float
```

**Testing a new rule:**
```python
import file_parser

data = file_parser.extract_data('test.log', 'gaussian_rules.dat')
print(data.get('ZPE_au'))
```

## Limitations

1. **No multi-line matching** - Each rule matches single lines
2. **Regex escaping required** - Special characters must be escaped
3. **No arithmetic** - Cannot compute derived values (use post-processing)
4. **Whitespace sensitive** - Indentation in scoped sections is cosmetic only
5. **Comments must be on own line** - No inline comments after rules
