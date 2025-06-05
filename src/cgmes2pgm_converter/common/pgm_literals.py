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

from power_grid_model import ComponentType

BRANCH_COMPONENTS = [
    ComponentType.generic_branch,
    ComponentType.line,
    ComponentType.transformer,
    ComponentType.link,
]

APPLIANCE_COMPONENTS = [
    ComponentType.sym_load,
    ComponentType.sym_gen,
    ComponentType.asym_load,
    ComponentType.asym_gen,
    ComponentType.source,
    ComponentType.shunt,
]

SENSOR_COMPONENTS = [
    ComponentType.sym_power_sensor,
    ComponentType.asym_power_sensor,
    ComponentType.sym_voltage_sensor,
    ComponentType.asym_voltage_sensor,
]
