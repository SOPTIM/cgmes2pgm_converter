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


class LinkBuilder(AbstractPgmComponentBuilder):
    _query = """
        SELECT  ?eq
                (SAMPLE(?_name) as ?name)
                (SAMPLE(?_tn1) as ?tn1)
                (SAMPLE(?_tn2) as ?tn2)
                (SAMPLE(?_status1) as ?status1)
                (SAMPLE(?_status2) as ?status2)
                (SAMPLE(?_open) as ?open)
                (SAMPLE(?__type) as ?type)
        WHERE {

            VALUES ?_type { cim:Breaker cim:Switch cim:Disconnector}
            ?eq a ?_type;
                cim:IdentifiedObject.name ?_name;
                $IN_SERVICE
                # cim:Equipment.inService "true";
                cim:Switch.open ?_open.

            BIND(STRAFTER(STR(?_type), "#") AS ?__type)

            ?_term1 a cim:Terminal;
                    cim:Terminal.ConductingEquipment ?eq;
                    cim:Terminal.TopologicalNode ?_tn1;
                    cim:ACDCTerminal.sequenceNumber "1";
                    cim:ACDCTerminal.connected ?_status1.

            ?_term2 a cim:Terminal;
                      cim:Terminal.ConductingEquipment ?eq;
                      cim:Terminal.TopologicalNode ?_tn2;
                      cim:ACDCTerminal.sequenceNumber "2";
                      cim:ACDCTerminal.connected ?_status2.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?_tn1;
            #            cim:TopologicalIsland.TopologicalNodes ?_tn2.

            FILTER(?_tn1 != ?_tn2)
            FILTER(?_status1 = "true" &&  ?_status2 = "true" && ?_open = "false")
        }

        GROUP BY ?eq
        ORDER BY ?eq
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?_tn1", "?_tn2"),
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(res["eq"], res["name"])
        arr["from_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn1"]]
        arr["to_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn2"]]
        arr["from_status"] = res["status1"] & ~res["open"]
        arr["to_status"] = res["status2"] & ~res["open"]

        extra_info = self._create_extra_info_with_types(arr, res["type"])

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.link
