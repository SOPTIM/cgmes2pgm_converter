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

from cgmes2pgm_converter.common import (
    AbstractCgmesIdMapping,
    CgmesDataset,
    ConverterOptions,
    SymPowerType,
)

from ...component import AbstractPgmComponentBuilder
from .power_sensor_list import PowerSensorList

IRI_SUFFIX = "_neg_measurement"


class SymPowerSensorIncompleteBranch(AbstractPgmComponentBuilder):
    """
    Creates Power Sensors for branches that have a power sensor on only one terminal
    or don't have a power sensor at all. In the first case a new  power sensor is created
    on the other side with the negated value. In the latter case the power sensor is created
    with a values of zero and a large sigma.
    """

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        converter_options: ConverterOptions,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, converter_options, data_type)
        self._sensor_list = PowerSensorList()
        self._sensor_dict: dict[int, list] = {}

        bm = self._converter_options.measurement_substitution.branch_measurements
        conf_mirror = bm.mirror
        conf_zero_branch = bm.zero_cut_branch
        conf_zero_source = bm.zero_cut_source
        self._is_active = (
            conf_mirror.enable or conf_zero_branch.enable or conf_zero_source.enable
        )

        self._mirror_enabled = conf_mirror.enable
        self._mirror_sigma_factor = conf_mirror.sigma_factor
        self._zero_branch_enabled = conf_zero_branch.enable
        self._zero_branch_sigma = conf_zero_branch.sigma * 1e6
        self._zero_source_enabled = conf_zero_source.enable
        self._zero_source_sigma = conf_zero_source.sigma * 1e6

    def is_active(self) -> bool:
        return self._is_active

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        self._init_sensor_dict(input_data)

        self.create_sensor(ComponentType.generic_branch, input_data)
        self.create_sensor(ComponentType.line, input_data)

        arr = self._sensor_list.to_input_data()
        extra_info = self._create_extra_info_with_types(arr, self._sensor_list.type)

        return arr, extra_info

    def create_sensor(
        self,
        component_type: ComponentType,
        input_data: dict,
    ):
        """
        Creates a power sensor for each appliance with the given component_type
        and creates a power sensor with the given measured_terminal_type
        """

        for branch in input_data[component_type]:

            branch_id = branch["id"]
            sens = self._get_sensor_for_id(branch_id)

            # don't mirror measurements for transformers
            branch_type = self._extra_info[branch_id].get("_type")
            if "PowerTransformer" in branch_type or "PST" in branch_type:
                continue

            branch_iri = self._id_mapping.get_cgmes_iri(branch_id)
            branch_name = self._id_mapping.get_name_from_pgm(branch_id)

            sens_typed = {}
            for s in sens:
                sens_typed[s["measured_terminal_type"]] = s

            if (
                sens_typed.get(MeasuredTerminalType.branch_from) is not None
                and sens_typed.get(MeasuredTerminalType.branch_to) is None
                and self._mirror_enabled
            ):
                # sensor on from-side is moved to the to-side
                other_sensor = sens_typed[MeasuredTerminalType.branch_from]
                self._create_sensor(
                    other_sensor,
                    other_sensor["measured_object"],
                    MeasuredTerminalType.branch_to,
                )
            elif (
                sens_typed.get(MeasuredTerminalType.branch_to) is not None
                and sens_typed.get(MeasuredTerminalType.branch_from) is None
                and self._mirror_enabled
            ):
                # sensor on to-side is moved to the from-side
                other_sensor = sens_typed[MeasuredTerminalType.branch_to]
                self._create_sensor(
                    other_sensor,
                    other_sensor["measured_object"],
                    MeasuredTerminalType.branch_from,
                )
            elif (
                sens_typed.get(MeasuredTerminalType.branch_to) is None
                and sens_typed.get(MeasuredTerminalType.branch_from) is None
                and self._zero_branch_enabled
            ):
                # no sensor on branch, create two sensors with zero values
                self._create_sensor_zero(
                    branch_iri + "_f",
                    str(branch_name) + "_f",
                    branch["id"],
                    MeasuredTerminalType.branch_from,
                    self._zero_branch_sigma,
                )
                self._create_sensor_zero(
                    branch_iri + "_t",
                    str(branch_name) + "_t",
                    branch["id"],
                    MeasuredTerminalType.branch_to,
                    self._zero_branch_sigma,
                )

            # A branch might have been cut/disabled and replaced by two sources
            # on its nodes. These sources might not have sensors.
            # We need to create them.
            self._create_source_sensors(branch_id)

    def _create_sensor(self, other_sensor, meas_obj_id, measured_terminal_type):
        """Create a sensor with the negated values of the other sensor"""

        appliance_iri = self._id_mapping.get_cgmes_iri(other_sensor["id"])
        appliance_name = self._id_mapping.get_name_from_pgm(other_sensor["id"])

        sensor_id = self._id_mapping.add_cgmes_iri(
            appliance_iri + IRI_SUFFIX, appliance_name + IRI_SUFFIX
        )

        self._sensor_list.append(
            sensor_id,
            meas_obj_id,
            measured_terminal_type,
            # negate the values
            other_sensor["p_measured"] * -1,
            other_sensor["q_measured"] * -1,
            # adjust the sigma (but maybe the same sigma might be good enough)
            other_sensor["power_sigma"] * self._mirror_sigma_factor,
            SymPowerType.MIRRORED,
            other_sensor["p_sigma"] * self._mirror_sigma_factor,
            other_sensor["q_sigma"] * self._mirror_sigma_factor,
        )

    def _create_sensor_zero(
        self, branch_iri, branch_name, meas_obj_id, measured_terminal_type, sigma
    ):
        """Create a sensor with zero values and a large sigma"""
        sensor_id = self._id_mapping.add_cgmes_iri(
            branch_iri + IRI_SUFFIX, branch_name + IRI_SUFFIX
        )

        self._sensor_list.append(
            sensor_id,
            meas_obj_id,
            measured_terminal_type,
            0.0,
            0.0,
            sigma,
            SymPowerType.ZERO,
        )

    def _create_source_sensors(self, branch_id):
        """If a branch is cut, then two sources are placed on its nodes. These sources
        will get sensors/measurements from the branch terminals. If only one
        measurement is available, then only the corresponding source will get a sensor.
        This method identifies the sources for a branch and copies the negated measurement
        from one source to the other. If no measurement is available, then a sensor with
        zero values is created for both sources.
        """

        branch_info = self._extra_info[branch_id]

        branch_iri = self._id_mapping.get_cgmes_iri(branch_id)
        branch_name = self._id_mapping.get_name_from_pgm(branch_id)

        source1 = branch_info.get("source1")
        source2 = branch_info.get("source2")

        if source1 is None or source2 is None:
            # ignore branch that has no source associated with it, i.e. it is not cuttable
            return

        source1_sensor = self._get_sensor_for_id(source1)
        source2_sensor = self._get_sensor_for_id(source2)

        if (
            len(source1_sensor) == 0
            and len(source2_sensor) > 0
            and self._mirror_enabled
        ):
            # copy measurement from source2 to source1
            self._create_sensor(
                source2_sensor[0],
                source1,
                source2_sensor[0]["measured_terminal_type"],
            )
        elif (
            len(source1_sensor) > 0
            and len(source2_sensor) == 0
            and self._mirror_enabled
        ):
            # copy measurement from source1 to source2
            self._create_sensor(
                source1_sensor[0],
                source2,
                source1_sensor[0]["measured_terminal_type"],
            )
        elif (
            len(source1_sensor) == 0
            and len(source2_sensor) == 0
            and self._zero_source_enabled
        ):
            # create zero sensors for both sources
            self._create_sensor_zero(
                branch_iri + "_fs",
                branch_name + "_fs",
                source1,
                self._get_appliance_type(),
                self._zero_source_sigma,
            )
            self._create_sensor_zero(
                branch_iri + "_ts",
                branch_name + "_ts",
                source2,
                self._get_appliance_type(),
                self._zero_source_sigma,
            )

    def _get_appliance_type(self):
        """When a line is cut/disabled, then it is replaced by two appliances on its nodes.
        Depending if the appliance type, we have to adjust the measured_terminal_type
        """
        return (
            MeasuredTerminalType.source
            if self._converter_options.network_splitting.add_sources
            else MeasuredTerminalType.generator
        )

    def _init_sensor_dict(self, input_data):
        for sensor in input_data[ComponentType.sym_power_sensor]:
            meas_obj_list = self._sensor_dict.setdefault(sensor["measured_object"], [])
            meas_obj_list.append(sensor)

    def _get_sensor_for_id(self, id_):
        return self._sensor_dict.get(id_, [])

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor
