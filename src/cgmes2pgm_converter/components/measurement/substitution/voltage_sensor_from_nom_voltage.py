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

from cgmes2pgm_converter.common import (
    NodeType,
    UMeasurementSubstitutionOptions,
    VoltageMeasType,
)

from ...component import AbstractPgmComponentBuilder

IRI_SUFFIX = "_nomv_measurement"


class VoltageSensorList:

    def __init__(self, use_nominal_voltages: UMeasurementSubstitutionOptions):
        self.id = []
        self.measured_object = []
        self.u_measured = []
        self.sigma = []
        self.use_nominal_voltages = use_nominal_voltages

    def to_input_data(self):
        arr = initialize_array("input", ComponentType.sym_voltage_sensor, len(self.id))
        arr["id"] = self.id
        arr["measured_object"] = self.measured_object
        arr["u_measured"] = self.u_measured
        arr["u_sigma"] = self.sigma

        return arr

    def append(self, sensor_id, measured_object, u_rated):
        self.id.append(sensor_id)
        self.measured_object.append(measured_object)
        meas_v, sigma = self.use_nominal_voltages.map_v(u_rated)
        self.u_measured.append(meas_v)
        self.sigma.append(sigma)


class SymVoltageFromNominalVoltageBuilder(AbstractPgmComponentBuilder):

    def is_active(self) -> bool:
        return (
            self._converter_options.measurement_substitution.use_nominal_voltages.enable
        )

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        sensor_list = VoltageSensorList(
            self._converter_options.measurement_substitution.use_nominal_voltages
        )

        measured_objects_dict = {
            sensor["measured_object"]: sensor
            for sensor in input_data[ComponentType.sym_voltage_sensor]
        }

        for node in input_data[ComponentType.node]:
            if node["id"] in measured_objects_dict:
                continue

            node_id = node["id"]

            type_ = self._extra_info[node_id].get("_type")
            if type_ == NodeType.AUX_NODE:
                continue

            node_iri = self._id_mapping.get_cgmes_iri(node_id)
            node_name = self._id_mapping.get_name_from_pgm(node_id)

            sensor_id = self._id_mapping.add_cgmes_iri(
                node_iri + IRI_SUFFIX, node_name + IRI_SUFFIX
            )

            sensor_list.append(sensor_id, node_id, node["u_rated"])

        arr = sensor_list.to_input_data()
        extra_info = self._create_extra_info_with_type(
            arr, VoltageMeasType.SUBSTITUTED_NOM_V
        )
        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.sym_voltage_sensor
