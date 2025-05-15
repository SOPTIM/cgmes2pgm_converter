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
from power_grid_model import ComponentType, LoadGenType, initialize_array

from cgmes2pgm_converter.common import NodeType, Topology

from ...component import AbstractPgmComponentBuilder


class SymLoadOrGenForPassiveNodeBuilder(AbstractPgmComponentBuilder):

    def is_active(self):
        return self._converter_options.measurement_substitution.passive_nodes.enable

    def component_name(self) -> ComponentType:
        if (
            self._converter_options.measurement_substitution.passive_nodes.appliance_type
            is None
        ):
            raise ValueError("Appliance type must be set")
        return (
            self._converter_options.measurement_substitution.passive_nodes.appliance_type
        )

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:
        # find passive nodes
        topo = Topology(input_data, self._extra_info)
        nodes = [
            n
            for n in topo.get_topology().values()
            if n.get(ComponentType.node) is not None
        ]
        passive_nodes = [n for n in nodes if self._is_passive_node(n)]

        # create new IDs and names for the sym_loads or sym_gens
        passive_node_ids = [x[ComponentType.node]["id"] for x in passive_nodes]
        load_or_gen_iris = [
            self._id_mapping.get_cgmes_iri(x) + "_PASS" for x in passive_node_ids
        ]

        appendix = self.get_type()

        load_or_gen_names = [
            str(self._id_mapping.get_name_from_pgm(x)) + appendix
            for x in passive_node_ids
        ]

        # create array with generation
        arr = initialize_array(
            self._data_type, self.component_name(), len(passive_nodes)
        )
        arr["id"] = self._id_mapping.add_cgmes_iris(load_or_gen_iris, load_or_gen_names)
        arr["node"] = passive_node_ids

        arr["status"] = True
        arr["type"] = LoadGenType.const_power
        arr["p_specified"] = 0.0
        arr["q_specified"] = 0.0

        extra_info = self._create_extra_info_with_type(arr, "SymLoadOrGenPassiveNode")

        return arr, extra_info

    def _is_passive_node(self, node):
        appliances = [
            ComponentType.sym_gen,
            ComponentType.source,
            ComponentType.sym_load,
            ComponentType.shunt,
        ]
        has_no_appliances = all(node.get(appliance) is None for appliance in appliances)
        has_branches = node.get("_branches") is not None
        is_not_aux_node = node.get("_extra").get("_type") != NodeType.AUX_NODE

        # A passive node is not an AuxNode, has no appliances, but is connected with branches
        return has_no_appliances and has_branches and is_not_aux_node

    def get_type(self) -> str:
        appliance_type = (
            self._converter_options.measurement_substitution.passive_nodes.appliance_type
        )
        return " Gen P" if appliance_type == ComponentType.sym_gen else " Load P"
