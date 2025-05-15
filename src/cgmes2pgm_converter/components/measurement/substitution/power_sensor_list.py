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

from power_grid_model import ComponentType, initialize_array


class PowerSensorList:
    """
    Helper class to create a list of power sensors
    """

    def __init__(self):
        self.id = []
        self.measured_object = []
        self.measured_terminal_type = []
        self.p_measured = []
        self.q_measured = []
        self.power_sigma = []
        self.p_sigma = []
        self.q_sigma = []
        self.type = []

    def to_input_data(self):
        arr = initialize_array("input", ComponentType.sym_power_sensor, len(self.id))
        arr["id"] = self.id
        arr["measured_object"] = self.measured_object
        arr["measured_terminal_type"] = self.measured_terminal_type
        arr["p_measured"] = self.p_measured
        arr["q_measured"] = self.q_measured

        arr["power_sigma"] = self.power_sigma
        arr["q_sigma"] = self.q_sigma
        arr["p_sigma"] = self.p_sigma

        return arr

    def append(
        self,
        sensor_id,
        measured_object,
        measured_terminal_type,
        p_measured,
        q_measured,
        power_sigma,
        type_,
        p_sigma=None,
        q_sigma=None,
    ):
        self.id.append(sensor_id)
        self.measured_object.append(measured_object)
        self.measured_terminal_type.append(measured_terminal_type)
        self.p_measured.append(p_measured)
        self.q_measured.append(q_measured)
        self.power_sigma.append(power_sigma)
        self.p_sigma.append(power_sigma if p_sigma is None else p_sigma)
        self.q_sigma.append(power_sigma if q_sigma is None else q_sigma)
        self.type.append(type_)
