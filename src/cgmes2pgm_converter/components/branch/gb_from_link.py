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
from power_grid_model import ComponentType, initialize_array

from cgmes2pgm_converter.common import AbstractCgmesIdMapping, BranchType, CgmesDataset

from ..component import AbstractPgmComponentBuilder


class GenericBranchFromLinkBuilder(AbstractPgmComponentBuilder):

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, data_type)
        self._component_name = ComponentType.generic_branch

    def is_active(self) -> bool:
        return self._converter_options.link_as_short_line.enable

    def build_from_cgmes(self, input_data) -> tuple[np.ndarray, dict | None]:

        filtered_sensors = [
            s
            for s in input_data[ComponentType.sym_power_sensor]
            if self.filter_sensor(s)
        ]
        # link_with_sensors_indices = [i for i in input_data[ComponentType.sym_power_sensor]["measured_object"] if self.filter_link(i)]
        link_with_sensors_indices = [
            i
            for i in [m["measured_object"] for m in filtered_sensors]
            if self.filter_link(i)
        ]
        mask = np.isin(input_data[ComponentType.link]["id"], link_with_sensors_indices)
        filtered_links = input_data[ComponentType.link][mask]

        # Remove links
        input_data[ComponentType.link] = input_data[ComponentType.link][~mask]

        # -> add GenericBranch
        arr = initialize_array(
            self._data_type, self.component_name(), filtered_links.shape[0]
        )

        # arr["id"] = self._id_mapping.add_cgmes_iris(res["line"], res["name"])
        arr["id"] = filtered_links["id"]
        arr["from_node"] = filtered_links["from_node"]
        arr["to_node"] = filtered_links["to_node"]
        arr["from_status"] = filtered_links["from_status"]
        arr["to_status"] = filtered_links["to_status"]
        arr["r1"] = self._converter_options.link_as_short_line.r
        arr["x1"] = self._converter_options.link_as_short_line.x
        arr["g1"] = 0.0
        arr["b1"] = 0.0
        arr["k"] = 1.0
        arr["theta"] = 0.0

        for s in filtered_sensors:
            s["p_sigma"] = (
                self._converter_options.link_as_short_line.sigma_factor * s["p_sigma"]
            )
            s["q_sigma"] = (
                self._converter_options.link_as_short_line.sigma_factor * s["q_sigma"]
            )
            s["power_sigma"] = (
                self._converter_options.link_as_short_line.sigma_factor
                * s["power_sigma"]
            )

        ## TODO: _type = kopieren aus extra_data von Link
        extra_info = {}
        return arr, extra_info

    def filter_sensor(self, sensor) -> bool:
        meas = sensor["measured_object"]
        return self.filter_link(meas)

    def filter_link(self, idx: int) -> bool:
        extra = self._extra_info[idx]
        if (
            extra["_type"] == "Breaker"
            or extra["_type"] == "Switch"
            or extra["_type"] == "Disconnector"
        ):
            return True
        return False

    def component_name(self) -> ComponentType:
        return self._component_name
