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
This module contains common classes and functions used throughout the package.
"""

from .cgmes_dataset import CgmesDataset
from .cgmes_literals import (
    CIM_ID_OBJ,
    CIM_MEAS,
    MeasurementValueSource,
    Profile,
    convert_unit_multiplier,
    phase_tap_changer_types,
)
from .converter_literals import COMPONENT_TYPE, NodeType, SymPowerType, VoltageMeasType
from .converter_options import BranchType, ConverterOptions
from .id_mapper import AbstractCgmesIdMapping, CgmesPgmIdMapping
from .measurement_substitution import (
    BranchMeasurements,
    DefaultSigma,
    IncompleteMeasurements,
    MeasSub,
    MeasurementSubstitutionOptions,
    PassiveNodeOptions,
    QFromIOptions,
    SshSubstitutionOptions,
    UMeasurementSubstitutionOptions,
)
from .network_splitting import NetworkSplittingOptions
from .timer import Timer
from .topology import Topology
