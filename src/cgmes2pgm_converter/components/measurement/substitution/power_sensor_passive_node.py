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

import numpy as np
from power_grid_model import ComponentType, MeasuredTerminalType, initialize_array

from cgmes2pgm_converter.common import SymPowerType

from ...component import AbstractPgmComponentBuilder


class SymPowerForPassiveNodeBuilder(AbstractPgmComponentBuilder):

    def is_active(self):
        return self._converter_options.measurement_substitution.passive_nodes.enable

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:
        # find ids of sym_gens of the passive nodes
        appliance_ids = []
        for gen_id, info in self._extra_info.items():
            if info.get("_type") == "SymLoadOrGenPassiveNode":
                appliance_ids.append(gen_id)

        # create new IDs and names for the sensors
        sensor_iris = [self._id_mapping.get_cgmes_iri(x) + "_PQ" for x in appliance_ids]

        sensor_names = [
            self._id_mapping.get_name_from_pgm(x) + " Meas PQ" for x in appliance_ids
        ]

        # create array with power sensors
        arr = initialize_array(
            self._data_type, self.component_name(), len(appliance_ids)
        )
        arr["id"] = self._id_mapping.add_cgmes_iris(sensor_iris, sensor_names)
        arr["measured_object"] = appliance_ids

        arr["measured_terminal_type"] = self.get_measured_terminal_type()

        arr["p_measured"] = 0.0
        arr["q_measured"] = 0.0

        sigma = (
            self._converter_options.measurement_substitution.passive_nodes.sigma * 1e6
        )
        arr["p_sigma"] = sigma
        arr["q_sigma"] = sigma
        arr["power_sigma"] = arr["p_sigma"]

        extra_info = self._create_extra_info_with_type(arr, SymPowerType.PASSIVE)

        return arr, extra_info

    def get_measured_terminal_type(self):
        appliance_type = (
            self._converter_options.measurement_substitution.passive_nodes.appliance_type
        )
        if appliance_type == ComponentType.sym_gen:
            return MeasuredTerminalType.generator
        if appliance_type == ComponentType.sym_load:
            return MeasuredTerminalType.load

        raise ValueError("Unknown appliance type")
