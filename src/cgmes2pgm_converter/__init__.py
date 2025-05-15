# Copyright [2025] [SOPTIM AG]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This package provides a library to convert 
Common Grid Model Exchange Standard (CGMES) data to PGM format 
and apply the State Estimation from 
[PowerGridModel](https://github.com/PowerGridModel/power-grid-model).
"""

import logging
import sys

from .common import CgmesDataset, ConverterOptions
from .converter import CgmesToPgmConverter

logging.basicConfig(
    level=logging.INFO,  # or DEBUG, WARNING, etc.
    format="%(levelname)-8s :: %(message)s",
    stream=sys.stdout,
)
