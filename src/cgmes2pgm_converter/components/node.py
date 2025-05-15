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

import numpy as np
from power_grid_model import ComponentType, initialize_array

from .component import AbstractPgmComponentBuilder


class NodeBuilder(AbstractPgmComponentBuilder):
    """
    This class builds the node component of the power grid model
    from CGMES data based on cim:TopologicalNode.
    """

    _query = """
        SELECT DISTINCT ?tn ?name ?voltage ?substationName ?substation ?containerType ?container ?containerName
        WHERE {
            ?tn a cim:TopologicalNode;
                  cim:IdentifiedObject.name ?name.

            OPTIONAL {
                ?tn cim:TopologicalNode.ConnectivityNodeContainer ?container.
                ?container a ?containerType;

                OPTIONAL {
                    ?container a cim:Bay;
                        cim:Bay.VoltageLevel ?voltageLevel.
                    ?voltageLevel cim:VoltageLevel.Substation ?substation.
                    ?substation cim:IdentifiedObject.name ?substationName.
                }

                OPTIONAL {
                    ?container a cim:VoltageLevel;
                        cim:VoltageLevel.Substation ?substation.
                    ?substation cim:IdentifiedObject.name ?substationName.
                }

                ?container cim:IdentifiedObject.name ?containerName.
            }

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "name";
            #            cim:TopologicalIsland.TopologicalNodes ?tn;

            OPTIONAL {
                ?tn cim:TopologicalNode.BaseVoltage ?_bv.
                ?_bv cim:BaseVoltage.nominalVoltage ?_nv1.
            }

            BIND(COALESCE(?_nv1, -1) AS ?voltage)
        }
        ORDER BY ?tn
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        args = {"$TOPO_ISLAND": self._at_topo_island_node("?tn")}
        q = self._replace(self._query, args)
        query_result = self._source.query(q)

        arr = initialize_array(
            self._data_type, self.component_name(), query_result.shape[0]
        )
        arr["id"] = self._id_mapping.add_cgmes_iris(
            query_result["tn"], query_result["name"]
        )

        arr["u_rated"] = query_result["voltage"] * 1e3

        # Warning for nodes without voltage
        if np.any(arr["u_rated"] == 0):
            logging.warning("Found topological nodes without a BaseVoltage")
            logging.warning(
                query_result[arr["u_rated"] == 0]["tn"].to_string(
                    index=False,
                )
            )
            logging.warning("These nodes will be treated as 1V nodes.")

            np.putmask(arr["u_rated"], arr["u_rated"] == 0, 1)

        return arr, self._generate_extra_info(query_result, arr)

    def _generate_extra_info(self, query_result, arr):
        extra_info = {}
        subs = query_result["substation"]
        sub_names = query_result["substationName"]
        containers = query_result["container"]
        container_names = query_result["containerName"]
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_substationMrid": str(subs[idx]),
                "_substation": str(sub_names[idx]),
                "_containerMrid": containers[idx],
                "_container": str(container_names[idx]),
                "_type": "TopologicalNode",
            }

        self._log_type_counts(extra_info)
        self._log_distinct_values(extra_info, "_substation")
        return extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.node
