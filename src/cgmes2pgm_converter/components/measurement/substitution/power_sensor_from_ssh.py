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
from power_grid_model import ComponentType, MeasuredTerminalType

from cgmes2pgm_converter.common import SymPowerType

from ...component import AbstractPgmComponentBuilder
from .power_sensor_list import PowerSensorList

IRI_SUFFIX = "_ssh_measurement"


class SymPowerFromSshBuilder(AbstractPgmComponentBuilder):
    """
    Creates Power Sensors for Appliances that don't have a power sensor
    a power sensor using p_specified and q_specified from the appliances
    These values correspond to the ssh values
    """

    def is_active(self) -> bool:
        return self._converter_options.measurement_substitution.use_ssh.enable

    def _init_sensor_dict(self, input_data):
        _sensor_dict = {}
        for sensor in input_data[ComponentType.sym_power_sensor]:
            meas_obj_list = _sensor_dict.setdefault(sensor["measured_object"], [])
            meas_obj_list.append(sensor)
        return _sensor_dict

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        sensor_dict = self._init_sensor_dict(input_data)

        sensor_list = PowerSensorList()
        self.create_sensor(
            ComponentType.sym_load,
            MeasuredTerminalType.load,
            input_data,
            sensor_list,
            sensor_dict,
        )
        self.create_sensor(
            ComponentType.sym_gen,
            MeasuredTerminalType.generator,
            input_data,
            sensor_list,
            sensor_dict,
        )

        arr = sensor_list.to_input_data()
        extra_info = self._create_extra_info_with_type(arr, SymPowerType.SSH)

        return arr, extra_info

    def create_sensor(
        self,
        component_type: ComponentType,
        measured_terminal_type: MeasuredTerminalType,
        input_data: dict,
        sensor_list: PowerSensorList,
        sensor_dict: dict,
    ):
        """
        Creates a power sensor for each appliance with the given component_type
        and creates a power sensor with the given measured_terminal_type
        """

        for appliance in input_data[component_type]:

            appliance_id = appliance["id"]
            any_sensor = sensor_dict.get(appliance_id, [])
            if len(any_sensor) > 0:
                continue

            appliance_iri = self._id_mapping.get_cgmes_iri(appliance["id"])
            appliance_name = self._id_mapping.get_name_from_pgm(appliance["id"])

            sensor_id = self._id_mapping.add_cgmes_iri(
                appliance_iri + IRI_SUFFIX, str(appliance_name) + IRI_SUFFIX
            )

            # no sensors if no ssh values
            if appliance["p_specified"] is None or appliance["q_specified"] is None:
                continue

            if np.isnan(appliance["p_specified"]) or np.isnan(appliance["q_specified"]):
                continue

            type_ = self._extra_info[appliance["id"]]["_type"]

            sensor_list.append(
                sensor_id,
                appliance["id"],
                measured_terminal_type,
                appliance["p_specified"],
                appliance["q_specified"],
                self._converter_options.measurement_substitution.use_ssh.sigma,
                type_,
            )

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor
