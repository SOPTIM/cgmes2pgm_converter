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

from dataclasses import dataclass, field
from enum import Enum

from .measurement_substitution import MeasurementSubstitutionOptions
from .network_splitting import NetworkSplittingOptions


class BranchType(Enum):
    """Enumeration for the branch types."""

    LINE = "line"
    TRANSFORMER = "transformer"
    THREE_WINDING_TRANSFORMER = "three_winding_transformer"
    PST = "pst"
    THREE_WINDING_PST = "three_winding_pst"


@dataclass
class ConverterOptions:
    """
    A class to define options for the converter.

    Attributes:
        only_topo_island (bool): Only include nodes belonging to any topological island (SV).
            Defaults to False.
        topo_island_name (str | None): Only include nodes belonging to a specific
            topological island (SV). Defaults to None.
        sources_from_sv (bool): If True, sources are created based on the topological islands
            in the SV profile (using  `cim:TopologicalIsland.AngleRefTopologicalNode`).
        measurement_substitution (MeasurementSubstitutionOptions | None):
            Options for creation of additional measurements for state estimation.
            If None, no additional measurements are created.
        network_splitting (NetworkSplittingOptions | None):
            Options for network splitting during conversion.
        use_generic_branch (dict): A dictionary indicating the use of generic branches for
            various branch types. Generic branches are used for all branch types.
            It is only possible to disable the use of generic branches for lines.
    """

    only_topo_island: bool = False
    topo_island_name: str | None = None
    sources_from_sv: bool = False
    measurement_substitution: MeasurementSubstitutionOptions | None = field(
        default_factory=MeasurementSubstitutionOptions
    )
    network_splitting: NetworkSplittingOptions | None = field(
        default_factory=NetworkSplittingOptions
    )

    # Deprecated: support for disabling the use of generic branches has been removed
    # Generic branches are used for all branch types
    use_generic_branch: dict[BranchType, bool] = field(
        default_factory=lambda: {
            BranchType.LINE: True,
            BranchType.TRANSFORMER: True,
            BranchType.THREE_WINDING_TRANSFORMER: True,
            BranchType.PST: True,
            BranchType.THREE_WINDING_PST: True,
        }
    )
