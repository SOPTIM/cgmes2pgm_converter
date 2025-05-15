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

import logging
from abc import ABC, abstractmethod
from collections import Counter

import numpy as np
from power_grid_model import ComponentType

from cgmes2pgm_converter.common import (
    AbstractCgmesIdMapping,
    CgmesDataset,
    ConverterOptions,
)

log = logging.debug


class AbstractPgmComponentBuilder(ABC):
    """Abstract class to build an PGM-Component from a CGMES dataset."""

    _extra_info: dict = {}

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        converter_options: ConverterOptions,
        data_type: str = "input",
    ):
        self._source = cgmes_source
        self._converter_options = converter_options
        self._data_type = data_type
        self._id_mapping = id_mapping

    @abstractmethod
    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:
        """Creates a pgm component from the cgmes data.

        Args:
            input_data (dict): Existing pgm_model

        Returns:
            tuple (np.ndarray, dict | None):
                Tuple of the created component and the extra info
        """
        raise NotImplementedError

    @abstractmethod
    def component_name(self) -> ComponentType:
        """
        Name of the component in the PGM model
        """

        raise NotImplementedError

    def is_active(self) -> bool:
        return True

    def set_extra_info(self, extra_info: dict):
        self._extra_info = extra_info

    def _in_service(self):
        if self._source.cim_namespace == "http://iec.ch/TC57/CIM100#":
            return 'cim:Equipment.inService "true";'
        return ""

    def _at_topo_island_node(self, node1, node2=None):
        options = self._converter_options
        if options.only_topo_island is True or options.topo_island_name is not None:
            stmt = "?topoIsland "
            if options.topo_island_name is not None:
                stmt += f'cim:IdentifiedObject.name "{options.topo_island_name}"; '

            stmt += "cim:TopologicalIsland.TopologicalNodes " + node1
            if node2 is not None:
                stmt += "; cim:TopologicalIsland.TopologicalNodes " + node2

            stmt += "."
            return stmt
        return ""

    def _replace(self, query: str, query_params: dict):
        return self._source.format_query(query, query_params)

    def _create_extra_info_with_types(self, arr: np.ndarray, types: list[str]) -> dict:
        extra_info = {}
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_type": types[idx],
            }
        return extra_info

    def _create_extra_info_with_type(
        self, arr: np.ndarray, type_: str, extra_info=None
    ) -> dict:

        if extra_info is None:
            # Cant be set as default value because it is mutable and
            # would be modified with each call
            extra_info = {}

        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_type": type_,
            }

        return extra_info

    def _log_type_counts(self, extra_info: dict):
        self._log_counts(extra_info, "_type")

    def _log_counts(self, extra_info: dict, key: str):
        types = [ei[key] for ei in extra_info.values()]
        counter = Counter(types)
        total = 0
        for c in counter:
            total += counter[c]
            log("\t\tFound %d %s", counter[c], c)
        if len(counter) > 1:
            log("\t\tTotal: %d", total)

    def _log_distinct_values(self, extra_info: dict, key: str):
        values = [ei[key] for ei in extra_info.values()]
        counter = Counter(values)
        log("\t\tFound %d %s", len(counter), key)
