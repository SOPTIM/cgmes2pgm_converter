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

from ..component import AbstractPgmComponentBuilder


class SymLoadBuilder(AbstractPgmComponentBuilder):

    _query = """
        SELECT DISTINCT ?topologicalNode ?name ?connected ?EnergyConsumer ?p ?q ?type
        WHERE
        {
            ?EnergyConsumer rdf:type ?_type;
                            $IN_SERVICE
                            # cim:Equipment.inService "true";
                            cim:IdentifiedObject.name ?name.

            VALUES ?_type {
                cim:EnergyConsumer
                cim:ConformLoad
                cim:NonConformLoad
                cim:StationSupply
                cim:AsynchronousMachine
            }

            BIND(STRAFTER(STR(?_type), "#") AS ?type)

            ?Terminal a cim:Terminal;
                        cim:Terminal.TopologicalNode ?topologicalNode;
                        cim:ACDCTerminal.connected ?connected;
                        cim:Terminal.ConductingEquipment ?EnergyConsumer.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?topologicalNode.

            OPTIONAL { ?EnergyConsumer cim:EnergyConsumer.p ?p. }
            OPTIONAL { ?EnergyConsumer cim:EnergyConsumer.q ?q. }
            OPTIONAL { ?EnergyConsumer cim:RotatingMachine.p ?p. }
            OPTIONAL { ?EnergyConsumer cim:RotatingMachine.q ?q. }
        }
        ORDER BY ?EnergyConsumer
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?topologicalNode"),
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        # Mw, MVar to W, Var
        res["p"] = res["p"] * 1e6
        res["q"] = res["q"] * 1e6

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(res["EnergyConsumer"], res["name"])
        arr["node"] = [
            self._id_mapping.get_pgm_id(uuid) for uuid in res["topologicalNode"]
        ]
        arr["status"] = res["connected"]
        arr["type"] = LoadGenType.const_power
        arr["p_specified"] = res["p"]
        arr["q_specified"] = res["q"]

        extra_info = self._create_extra_info_with_types(arr, res["type"])

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.sym_load
