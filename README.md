<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO 
<br />
<div align="center">
  <a href="https://github.com/zedo-heptulose/CC-batch-manager">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>
-->
<h3 align="center">CCBatchMan</h3>

  <p align="center">
    Your man(ager) for CC Batches. Utilities for running batch computational chemistry jobs. Includes a combinatorial input generator, a job runner, and an output file postprocessor. Also includes data structures for automating thermochemical calculations with data from multiple runs. Supports automatically transferring coordinates from run to run and selectively overwriting failed and unfinished jobs with new settings. Supports several programs and is modular and easily extensible.
<!--     <br />
    <a href="https://github.com/zedo-heptulose/CC-batch-manager"><strong>Explore the docs »</strong></a>
    <br /> -->
    <br />
<!--     <a href="https://github.com/zedo-heptulose/CC-batch-manager">View Demo</a>
    · -->
    <a href="https://github.com/zedo-heptulose/CC-batch-manager/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/zedo-heptulose/CC-batch-manager/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

```plaintext
ccbatchman/
├── src/
│   ├── input_generator.py
│   ├── input_combi.py
│   ├── batch_runner.py
│   ├── job_harness.py
│   ├── editor.py
│   ├── helpers.py
│   ├── file_parser.py
│   ├── postprocessor.py
│   ├── parse_tree.py
│   ├── parse_tree_builders.py
│   └── __init__.py
├── config/
|   ├── input_generator_config/
|   |   ├── batch_runner_config.json
|   |   ├── crest_config.json
|   |   ├── gaussian_config.json
|   |   ├── orca_config.json
|   |   ├── pyaroma_config.json
|   |   └── xtb_config.json
|   └── file_parser_config/
|       ├── crest_rules.dat
|       ├── gaussian_rules.dat
|       ├── orca_rules.dat
|       ├── pyaroma_rules.dat
|       └── xtb_rules.dat
├── examples/
├── LICENSE
└── README.md
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Dependencies

Python 3.8+, NumPy, pandas. 
Current implementation requires an environment with the SLURM job scheduler to run batch jobs.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running, follow these simple steps.

### Prerequisites

* NumPy and pandas
   ```sh
   conda install numpy pandas
   ```
   or
   ```sh
   pip install numpy pandas
   ```
  
### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/zedo-heptulose/CC-batch-manager.git
   ```
   
2. In the configs directory, edit the .json files relevant to each program you plan to use.
   You should, at minimum, set the path to each program or set the conda environment containing the program.

   <!--will need to include some screenshots here-->

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

### Generating input files and workflows
<!--a flowchart would go a long way here-->
The combinatorial input generator creates input files separated into meaningfully named directories.
```python
import sys
path = 'path/to/ccbatchman'
if path not in sys.path:
  sys.path.append(path)
import input_combi

global_configs = {'num_cores' : 8, 'mem_per_cpu_GB' : 4, 'runtime' : '1-00:00:00'}

#solvent settings to iterate through
solvents = {
  'reaction_in_water' : {'solvent' : 'water'},
  'reaction_in_thf' : {'solvent' : 'thf'},
  'reaction_in_dcm' : {'solvent' : 'dcm'},
}

#getting molecules to iterate through
path_to_xyz = '/path/to/directory/containing/xyz/files/'
molecules = input_combi.xyz_files_from_directory(path_to_xyz) #returns a dict of dicts with directories and filenames of xyz files
molecules['!directories'] = True #separate this category into directories. 


crest_conformer_search_gfn2 = {
  'program' : 'CREST',
  'functional' : 'gfn2',
  'noreftopo' : True
}
orca_opt_freq_r2scan3c = {
  'program' : 'ORCA',
  'functional' : 'r2SCAN-3c',
  'run_type':'opt freq',
  '!coords_from': '../conformer_search', #use coordinates from job with directory 'root/path_to_this_dir/../crest'
  '!xyz_file':'crest_best.xyz' #look for (output) xyz file 'crest_best.xyz' in this directory
}
orca_singlepoint_wb97x3c = {
  'program' : 'ORCA',
  'functional' :'wb97x-3c',
  '!coords_from' : '../optimization_frequency',
  '!xyz_file':'optimization_frequency.xyz',
  '!overwrite' : True #will overwrite jobs not flagged succeeded in ledger
}

composite_workflow = {
  'conformer_search' : crest_conformer_search_gfn2,
  'optimization_frequency' : orca_opt_freq_r2scan3c,
  'singlepoint' : orca_singlepoint_wb97x3c,
}
```
Once you have defined several sets of options, we can iterate through every combination of them and create our jobs.
```python
root_dir = '/where/you/run/your/job/'
batch_runner_configs = {'max_jobs': 10, 'job_basename' : 'my_workflow'}
input_combi.do_everything(
  root_dir,
  batch_runner_configs,
  [global_configs,solvents,molecules,composite_workflow],
)
```
When we navigate to the directory we set, we should see something like this:
```plaintext
run_root_dir/
├── my_workflow.sh
├── batchfile.csv
├── reaction_in_dcm/
|   ├── some_reactant/
|   │   ├── conformer_search/
|   |   |   ├── conformer_search.sh
|   |   |   ├── conformer_search.xyz
|   |   |   └── conformer_search.inp
|   │   ├── optimization_frequency/
|   |   |   ├── optimization_frequency.sh
|   |   |   ...
|   │   └── singlepoint/
|   |       ├── singlepoint.sh
|   |       ...
|   └── some_product/
|       ├── conformer_search/
|       ├── optimization_frequency/
|       └── singlepoint/
├── reaction_in_thf/
|   ├── some_reactant/
|   │   ├── conformer_search/
|   │   ├── optimization_frequency/
|   │   └── singlepoint/
|   └── some_product/
|       ├── conformer_search/
|       ├── optimization_frequency/
|       └── singlepoint/
├── reaction_in_water/
...
```

### Running jobs
> [!IMPORTANT]
> Follow the steps in Getting Started before running the submission script, or this will not work.
> 
In the directory you set as the root when generating input, submit the automatically generated script:
```sh
sbatch my_workflow.sh
```
This will generate a file in the root directory, "\_\_ledger\_\_.csv". This file contains the status of every job.
This run will also create my_workflow.out, which will print information about which calculations succeeded and failed and when the overall run finished.

### Parsing output
We can use parse_tree to process the data we generate. These data structures are designed for jobs arranged in a uniform hierarchy, of the sort generated by input_combi. 
The parse_tree_builders make it easy to programmatically work up data from output files stored in symmetric directory structures like this one. As an example:
```python
import parse_tree_builders

water_root = 'path/to/root/reaction_in_water'

ptb = parse_tree_builders.SimpleThermoTreeBuilder({
    #specify names of directories to look for reactants and products, and reaction coefficients
    'root_basename' : 'water', #name of .json file that will be written to job root made when data is parsed
    'root_dir' : water_root,
    'reactants' : {
      'some_reactant': 1,
      #'some_other_reactant' : 2 (if we had multiple reactants or products)
      }, 
    'products' : {
      'some_product' : 1 ,
      #'some_other_product' : 2.5
      },
    'opt_freq_dir' : 'optimization_frequency', 
    'singlepoint_dir' : 'singlepoint'
})
pt = ptb.build()
pt.depth_first_parse()
print(pt.data)
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] Improve output of batch_runner.py
- [ ] Implement unit tests
- [ ] Integrate Atomistic Simulation Environment for running jobs apart from SLURM 
- [ ] Add more options for workflow creation
    - [ ] Job priorities
    - [ ] Transfer orbitals
- [ ] Improve error handling
    - [x] Mark optimization + frequency jobs producing imaginary frequencies as failed
    - [ ] More detailed error output for failed jobs

See the [open issues](https://github.com/zedo-heptulose/CC-batch-manager/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/zedo-heptulose/CC-batch-manager/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=zedo-heptulose/CC-batch-manager" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Gage Bayliss - gdb20@fsu.edu

Project Link: [https://github.com/zedo-heptulose/CC-batch-manager](https://github.com/zedo-heptulose/CC-batch-manager)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!--
<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [othneildrew's Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/zedo-heptulose/CC-batch-manager.svg?style=for-the-badge
[contributors-url]: https://github.com/zedo-heptulose/CC-batch-manager/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/zedo-heptulose/CC-batch-manager.svg?style=for-the-badge
[forks-url]: https://github.com/zedo-heptulose/CC-batch-manager/network/members
[stars-shield]: https://img.shields.io/github/stars/zedo-heptulose/CC-batch-manager.svg?style=for-the-badge
[stars-url]: https://github.com/zedo-heptulose/CC-batch-manager/stargazers
[issues-shield]: https://img.shields.io/github/issues/zedo-heptulose/CC-batch-manager.svg?style=for-the-badge
[issues-url]: https://github.com/zedo-heptulose/CC-batch-manager/issues
[license-shield]: https://img.shields.io/github/license/zedo-heptulose/CC-batch-manager.svg?style=for-the-badge
[license-url]: https://github.com/zedo-heptulose/CC-batch-manager/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 
