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
from abc import abstractmethod

import numpy as np
from power_grid_model import ComponentType, initialize_array
from power_grid_model_io.data_types import ExtraInfo

import cgmes2pgm_converter.components as c
from cgmes2pgm_converter.common import (
    CgmesDataset,
    CgmesPgmIdMapping,
    ConverterOptions,
    Timer,
)


class AbstractCgmesToPgmConverter:
    """
    Abstract class to convert a CGMES model to a PGM model
    """

    @abstractmethod
    def convert(self) -> tuple[dict[ComponentType, np.ndarray], ExtraInfo]:
        """Convert CGMES data to PGM data

        Returns:
            tuple[dict, dict]: data, extra_info
        """
        raise NotImplementedError


class CgmesToPgmConverter(AbstractCgmesToPgmConverter):
    """
    Class to convert a CGMES model to a PGM model
    """

    def __init__(
        self,
        datasource: CgmesDataset,
        options: ConverterOptions = None,
    ):
        """
        Args:
            datasource (CgmesDataset): Data source to query CGMES data
            options (ConverterOptions): Options for the converter
        """

        self._datasource = datasource
        self._options = options or ConverterOptions()
        self._id_mapping = CgmesPgmIdMapping()
        self._input_data = {}
        self._extra_info: ExtraInfo = {}

        # Initialize empty arrays for all component types
        for comp in ComponentType:
            self._input_data[comp] = initialize_array("input", comp, 0)

    def convert(self) -> tuple[dict[ComponentType, np.ndarray], dict]:

        logging.debug("Starting conversion")

        builders = self._get_component_builders()
        for builder in builders:
            if not builder.is_active():
                continue

            component_name = builder.component_name()

            with Timer(f"\tBuilding {component_name}", loglevel=logging.DEBUG):
                builder.set_extra_info(self._extra_info)
                input_data, extra_info = builder.build_from_cgmes(self._input_data)

                self._input_data[component_name] = np.concatenate(
                    (self._input_data[component_name], input_data)
                )

                if extra_info:
                    self._append_extra_info(extra_info)

        self._append_extra_info(self._id_mapping.build_extra_info())

        return self._input_data, self._extra_info

    def get_id_mapping(self):
        return self._id_mapping

    def _append_extra_info(self, new_info: ExtraInfo):
        for k, v in new_info.items():
            if k in self._extra_info:
                self._extra_info[k].update(v)
            else:
                self._extra_info[k] = v

    def _get_component_builders(
        self,
    ) -> list[c.AbstractPgmComponentBuilder]:
        """
        Initialize all component builders
        """
        builders = [
            # Nodes
            c.NodeBuilder,
            c.Transformer3WAuxNodeBuilder,
            c.Pst3WAuxNodeBuilder,
            # Branches
            c.LineBuilder,
            c.EquivalentBranchBuilder,
            c.LinkBuilder,
            # Transformers
            c.Transformer2WAsGenericBranchBuilder,
            c.Transformer3WAsGenericBranchBuilder,
            c.Pst2WAsGenericBranchBuilder,
            c.Pst3WAsGenericBranchBuilder,
            c.DcAsLoadBuilder,
            # Appliances
            c.SymGenBuilder,
            c.SymLoadBuilder,
            c.LinearShuntBuilder,
            c.NonLinearShuntBuilder,
            c.SourceBuilder,
            c.SourceFromIslandBuilder,
            # Network splitting
            c.NetworkSplitter,
            # Measurements
            c.SymVoltageBuilder,
            c.SymPowerBuilder,
            # Substituted Measurements
            c.SymVoltageFromNominalVoltageBuilder,
            c.ReactivePowerForShuntBuilder,
            c.SymPowerSensorIncompleteBranch,
            c.SymPowerFromSshBuilder,
            c.SymPowerSensorIncompleteAppliance,
            c.SymLoadOrGenForPassiveNodeBuilder,
            c.SymPowerForPassiveNodeBuilder,
        ]
        return [
            builder(self._datasource, self._id_mapping, self._options)
            for builder in builders
        ]
