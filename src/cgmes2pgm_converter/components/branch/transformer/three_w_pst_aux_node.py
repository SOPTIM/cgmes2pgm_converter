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

from cgmes2pgm_converter.common import BranchType, NodeType

from .abstract_transformer import AbstractTransformerBuilder


class Pst3WAuxNodeBuilder(AbstractTransformerBuilder):

    def is_active(self):
        return self._converter_options.use_generic_branch[BranchType.THREE_WINDING_PST]

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        res = self._get_pst_result()

        arr = initialize_array(
            self._data_type, self.component_name(), int(res.shape[0])
        )

        if res.shape[0] == 0:
            return arr, None

        # use transformer name and iri for the aux node
        arr["id"] = self._id_mapping.add_cgmes_iris(
            res["tr1"], res["name1"] + "_pst_aux"
        )

        # use nominal voltage of the node at the HV side for the aux node
        arr["u_rated"] = res["nomU1"] * 1e3

        # get node ids for the HV side
        hv_node_id = [self._id_mapping.get_pgm_id(niri) for niri in res["node1"]]
        hv_node_info = [self._extra_info[nid] for nid in hv_node_id]

        extra_info = {}

        # put aux node into the same substation and container as the node at the HV side
        for idx, tn in enumerate(hv_node_info):
            extra_info[arr["id"][idx]] = {
                "_substationMrid": tn["_substationMrid"],
                "_substation": tn["_substation"],
                "_containerMrid": tn["_containerMrid"],
                "_container": tn["_container"],
                "_type": NodeType.AUX_NODE,
                "_hv_node_id": hv_node_id[idx],
            }

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.node

    def winding_count(self) -> int:
        return 3
