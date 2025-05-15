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

from ..component import AbstractPgmComponentBuilder


class SourceFromIslandBuilder(AbstractPgmComponentBuilder):
    """
    Class to create source objects based on existing SV-Profile.
    The same Nodes are used as Sources as in the SV-Profile.
    Based on `cim:TopologicalIsland.AngleRefTopologicalNode`.
    """

    def is_active(self):
        return self._converter_options.sources_from_sv

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:
        res = self.get_source()

        if res.shape[0] == 0:
            return initialize_array(self._data_type, "source", 0), {}

        res["angle_ref"] = "AngleRefTopologicalNode"

        # Add Source to Source
        arr = initialize_array(self._data_type, "source", res.shape[0])

        arr["id"] = self._id_mapping.add_cgmes_iris(
            res["topologicalNode"] + "_angleRef", res["islandName"]
        )
        arr["node"] = [
            self._id_mapping.get_pgm_id(uuid) for uuid in res["topologicalNode"]
        ]

        arr["status"] = 1
        arr["u_ref"] = 1
        arr["sk"] = 1e40
        arr["rx_ratio"] = 0.1
        arr["z01_ratio"] = 1

        extra_info = self._create_extra_info_with_types(arr, res["angle_ref"])
        return arr, extra_info

    def get_source(self):
        query = """
            SELECT ?topologicalNode ?islandName
            WHERE {
                ?topoIsland a cim:TopologicalIsland;
                            cim:TopologicalIsland.AngleRefTopologicalNode ?topologicalNode.

                $TOPO_ISLAND
                # ?topoIsland cim:IdentifiedObject.name "Network E BWW 170";
                #             cim:TopologicalIsland.TopologicalNodes ?topologicalNode.

                ?topoIsland cim:IdentifiedObject.name ?islandName;
            }
            ORDER BY ?topologicalNode
        """
        args = {
            "$TOPO_ISLAND": self._at_topo_island_node("?topologicalNode"),
        }
        q = self._replace(query, args)
        return self._source.query(q)

    def component_name(self) -> ComponentType:
        return ComponentType.source
