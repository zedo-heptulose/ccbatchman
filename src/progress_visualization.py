import os
import pandas as pd
import numpy

import sys
path1 = '/gpfs/home/gdb20/code/ccbatchman/src/'
path2 = '/gpfs/home/gdb20/code/data-processor/'
paths = [path1,path2]
for path in paths:
    if path not in sys.path:
        sys.path.append(path)
import input_combi
import helpers
import os
import re
import file_parser
import subprocess

import pandas as pd
import numpy
import matplotlib.pyplot as plt