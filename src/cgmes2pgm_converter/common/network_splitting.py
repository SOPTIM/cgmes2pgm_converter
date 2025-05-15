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

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NetworkSplittingOptions:
    """
    A class to define options for network splitting.
    The defined branches are split into 2 Appliances (Generators or Sources).

        `N1-----Line-----N2`

    Gets replaced with

        `N1-----Appl1 Appl2-----N2`

    Attributes:
        enable (bool): If True, network splitting is enabled. Defaults to False.
        cut_branches (list[str] | None):
            List of branch names (`IdentifiedObject.name`) to cut.
            If None, no branches are cut.
            Defaults to None.
        cut_substations (list[str] | None):
            List of substation names (`IdentifiedObject.name`) to cut.
            If None, no substations are cut.
            Defaults to None.
        add_sources (bool):
            If True, sources are added to the network instead of Generators.
            This allows that both resulting subnets can be calculated.
            Defaults to False.
    """

    enable: bool = False
    cut_branches: Optional[List[str]] = None
    cut_substations: Optional[List[str]] = None
    add_sources: bool = False
