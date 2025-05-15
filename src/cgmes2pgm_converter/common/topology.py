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
from typing import Any, Literal

import numpy as np
from power_grid_model import ComponentType, MeasuredTerminalType

from .converter_literals import COMPONENT_TYPE, NodeType
from .topology_subnets import TopologySubnets


class Topology:

    def __init__(
        self,
        input_data: dict[ComponentType, np.ndarray],
        extra_info: dict,
        result_data: dict[str, np.ndarray] | None = None,
        eval_measurements: bool = False,
    ):
        self._input_data = input_data
        self._extra_info = extra_info
        self._result_data = result_data

        self._topology: dict[str | int, dict[str | ComponentType, Any]] = {}
        self._topology_subnets = TopologySubnets()
        self._build_topology(eval_measurements)

    def get_topology(self):
        return self._topology

    def __getitem__(self, key):
        return self._topology[key]

    def add_results(self, result_data: dict[str, np.ndarray]):
        self._result_data = result_data

        self._assign_result(ComponentType.node)
        self._assign_result(ComponentType.line)
        self._assign_result(ComponentType.generic_branch)
        self._assign_result(ComponentType.link)
        self._assign_result(ComponentType.transformer)
        self._assign_result(ComponentType.three_winding_transformer)
        self._assign_result(ComponentType.source)
        self._assign_result(ComponentType.sym_gen)
        self._assign_result(ComponentType.sym_load)
        self._assign_result(ComponentType.shunt)

    def _build_topology(self, eval_measurements: bool):
        self._add_nodes()

        self._add_branch2(ComponentType.line)
        self._add_branch2(ComponentType.generic_branch)
        self._add_branch2(ComponentType.link)
        self._add_branch2(ComponentType.transformer)
        self._add_transformer_3w()

        self._add_appliance(ComponentType.source)
        self._add_appliance(ComponentType.sym_gen)
        self._add_appliance(ComponentType.sym_load)
        self._add_appliance(ComponentType.shunt)

        self._add_voltage_sensors()
        self._add_power_sensors()

        self._assign_subnets_to_nodes()

        if eval_measurements:
            self._eval_measurements()

    def _add_nodes(self):
        topology = self._topology
        nodes = self._input_data[ComponentType.node]
        for n in nodes:
            pgm_id = n["id"]
            topology[pgm_id] = {
                COMPONENT_TYPE: ComponentType.node,
                ComponentType.node: n,
                "_extra": self._extra_info.get(pgm_id),
            }

    def _add_branch2(
        self,
        branch_type: Literal[
            ComponentType.line,
            ComponentType.generic_branch,
            ComponentType.link,
            ComponentType.transformer,
        ],
    ):
        topology = self._topology
        branches = self._input_data[branch_type]
        for branch in branches:
            branch_id = branch["id"]

            from_node_id = branch["from_node"]
            from_node = topology[from_node_id]
            from_node.setdefault("_branches", []).append(branch_id)

            to_node_id = branch["to_node"]
            to_node = topology[to_node_id]
            to_node.setdefault("_branches", []).append(branch_id)

            topology[branch_id] = {
                COMPONENT_TYPE: branch_type,
                branch_type: branch,
                "_extra": self._extra_info.get(branch_id),
            }

            self._topology_subnets.eval_branch2(branch)

    def _add_transformer_3w(self):
        topology = self._topology
        transformer_3w = self._input_data[ComponentType.three_winding_transformer]
        for tr3w in transformer_3w:
            tr_id = tr3w["id"]

            node1_id = tr3w["node_1"]
            node1 = topology[node1_id]
            node1.setdefault("_branches", []).append(tr_id)

            node2_id = tr3w["node_2"]
            node2 = topology[node2_id]
            node2.setdefault("_branches", []).append(tr_id)

            node3_id = tr3w["node_3"]
            node3 = topology[node3_id]
            node3.setdefault("_branches", []).append(tr_id)

            topology[tr_id] = {
                COMPONENT_TYPE: ComponentType.three_winding_transformer,
                ComponentType.three_winding_transformer: tr3w,
                "_extra": self._extra_info.get(tr_id),
            }

            self._topology_subnets.eval_branch3(tr3w)

    def _add_appliance(
        self,
        component_type: Literal[
            ComponentType.source,
            ComponentType.sym_gen,
            ComponentType.sym_load,
            ComponentType.shunt,
        ],
    ):
        topology = self._topology
        srcs = self._input_data[component_type]
        for src in srcs:
            src_id = src["id"]
            node_id = src["node"]
            node = topology[node_id]
            node.setdefault(component_type, []).append(src_id)
            topology[src_id] = {
                COMPONENT_TYPE: component_type,
                component_type: src,
                "_extra": self._extra_info.get(src_id),
            }

    def _add_voltage_sensors(self):
        v_sensor = self._input_data[ComponentType.sym_voltage_sensor]
        for sensor in v_sensor:
            node_id = sensor["measured_object"]
            self._topology[node_id]["_sensor_v"] = sensor

    def _add_power_sensors(self):
        power_sensor = self._input_data[ComponentType.sym_power_sensor]
        for p_sensor in power_sensor:
            obj_id = p_sensor["measured_object"]
            obj_type = p_sensor["measured_terminal_type"]

            meas_obj = self._topology[obj_id]
            sensor_name = self.sensor_name(obj_type)
            meas_obj[sensor_name] = p_sensor

    def sensor_name(self, obj_type: MeasuredTerminalType) -> str:
        match obj_type:
            case (
                MeasuredTerminalType.source
                | MeasuredTerminalType.generator
                | MeasuredTerminalType.load
                | MeasuredTerminalType.node
                | MeasuredTerminalType.shunt
            ):
                return "_sensor_p"
            case MeasuredTerminalType.branch_from:
                return "_sensor_p_from"
            case MeasuredTerminalType.branch_to:
                return "_sensor_p_to"
            case MeasuredTerminalType.branch3_1:
                return "_sensor_p_1"
            case MeasuredTerminalType.branch3_2:
                return "_sensor_p_2"
            case MeasuredTerminalType.branch3_3:
                return "_sensor_p_3"
            case _:
                raise ValueError("unknown type")

    def _assign_result(self, component_name: ComponentType):
        if self._result_data is not None:
            components = self._result_data.get(component_name)
            if components is not None:
                for comp in components:
                    self._topology[comp["id"]]["_result"] = comp

    def _assign_subnets_to_nodes(self):
        subnet_names = self._topology_subnets.get_subnets()
        nodes = self.get_nodes()

        marker_dict = self._topology_subnets.get_marker()
        for node in nodes:
            node_id = node[ComponentType.node]["id"]
            node_marker = marker_dict.get(node_id)
            node["_subnet"] = (
                subnet_names[node_marker.get_island_marker().id]
                if node_marker is not None
                else "isolated"
            )

    def get_nodes(self):
        return [
            node
            for node in self._topology.values()
            if node.get(ComponentType.node) is not None
        ]

    def get_branches(self):
        return [
            branch
            for branch in self._topology.values()
            if branch.get(ComponentType.line) is not None
            or branch.get(ComponentType.generic_branch) is not None
            or branch.get(ComponentType.link) is not None
            or branch.get(ComponentType.transformer) is not None
        ]

    def get_branches3(self):
        return [
            branch
            for branch in self._topology.values()
            if branch.get(ComponentType.three_winding_transformer) is not None
        ]

    def get_appliances(self):
        return [
            appl
            for appl in self._topology.values()
            if appl.get(ComponentType.source) is not None
            or appl.get(ComponentType.sym_gen) is not None
            or appl.get(ComponentType.sym_load) is not None
            or appl.get(ComponentType.shunt) is not None
        ]

    def get_attached_branches(self, node_id: str | int):
        branch_ids = self._topology[node_id].get("_branches", [])
        return [self._topology[branch_id] for branch_id in branch_ids]

    def get_attached_appliances(self, node_id: str | int):
        return [
            appl
            for appl in self._topology[node_id].values()
            if appl.get(ComponentType.source) is not None
            or appl.get(ComponentType.sym_gen) is not None
            or appl.get(ComponentType.sym_load) is not None
            or appl.get(ComponentType.shunt) is not None
        ]

    def _eval_measurements(self):
        nodes = self.get_nodes()

        no_v_nodes = [node for node in nodes if self._is_node_without_v(node)]
        if len(no_v_nodes) > 0:
            logging.warning("%s Nodes without voltage sensor", len(no_v_nodes))

            for n in no_v_nodes:
                has_shunt = n.get(ComponentType.shunt) is not None
                has_load = n.get(ComponentType.sym_load) is not None
                has_gen = n.get(ComponentType.sym_gen) is not None

                pgm_id = n[ComponentType.node]["id"]
                mrid = n["_extra"]["_mrid"].split("#")[-1]
                name = n["_extra"]["_name"]
                node_info = f"Node '{name}' (id={pgm_id}, mrid={mrid})"

                logging.debug(
                    "\t%s in VL '%s' and Substation '%s' (has appliances: %s, %s, %s)",
                    node_info,
                    n["_extra"]["_container"],
                    n["_extra"]["_substation"],
                    has_gen,
                    has_load,
                    has_shunt,
                )

    def _is_node_without_v(self, item):
        extra = item.get("_extra")
        is_node = item.get(ComponentType.node) is not None
        is_aux_node = (
            extra.get("_type") == NodeType.AUX_NODE if extra is not None else False
        )
        has_no_v_sensor = item.get("_sensor_v") is None
        return is_node and not is_aux_node and has_no_v_sensor

    def get_input_data(self):
        return self._input_data

    def get_extra_info(self):
        return self._extra_info

    def get_topology_subnets(self):
        return self._topology_subnets
