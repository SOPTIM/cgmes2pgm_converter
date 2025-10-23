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

from cgmes2pgm_converter.common.cgmes_literals import Profile

from ..component import AbstractPgmComponentBuilder


class LinearShuntBuilder(AbstractPgmComponentBuilder):
    _query = """
        SELECT ?name ?topologicalNode ?connected ?ShuntCompensator ?b ?g (xsd:float(?_sections) as ?sections) ?Terminal
        WHERE {
            ?Terminal a cim:Terminal ;
                    cim:Terminal.TopologicalNode ?topologicalNode;
                    cim:ACDCTerminal.connected ?connected;
                    cim:Terminal.ConductingEquipment ?ShuntCompensator.

            ?ShuntCompensator a cim:LinearShuntCompensator;
                                $IN_SERVICE
                                # cim:Equipment.inService "true";
                                cim:IdentifiedObject.name ?name;
                                cim:LinearShuntCompensator.bPerSection ?_bPerSec;
                                cim:LinearShuntCompensator.gPerSection ?_gPerSec;
                                cim:ShuntCompensator.sections ?_sections.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?topologicalNode.

            BIND((xsd:double(?_bPerSec) * xsd:double(?_sections)) as ?b)
            BIND((xsd:double(?_gPerSec) * xsd:double(?_sections)) as ?g)
        }
        ORDER BY ?ShuntCompensator
    """

    _query_graph = """
        SELECT ?name ?topologicalNode ?connected ?ShuntCompensator ?b ?g (xsd:float(?_sections) as ?sections) ?Terminal
        WHERE {
            VALUES ?eq_graph { $EQ_GRAPH }
            VALUES ?tp_graph { $TP_GRAPH }
            VALUES ?ssh_graph { $SSH_GRAPH }

            GRAPH ?eq_graph {
                ?Terminal a cim:Terminal ;
                        cim:Terminal.ConductingEquipment ?ShuntCompensator.

                ?ShuntCompensator a cim:LinearShuntCompensator;
                                    cim:IdentifiedObject.name ?name;
                                    cim:LinearShuntCompensator.bPerSection ?_bPerSec;
                                    cim:LinearShuntCompensator.gPerSection ?_gPerSec.
            }

            $IN_SERVICE
            # GRAPH ?ssh_graph { ?ShuntCompensator cim:Equipment.inService "true"; }

            GRAPH ?ssh_graph {
                ?Terminal cim:ACDCTerminal.connected ?connected.
                ?ShuntCompensator cim:ShuntCompensator.sections ?_sections.
            }
            GRAPH ?tp_graph {
                ?Terminal cim:Terminal.TopologicalNode ?topologicalNode.
            }

            $TOPO_ISLAND
            # GRAPH ?sv_graph {
            #     ?topoIsland # cim:IdentifiedObject.name "Network";
            #                 cim:TopologicalIsland.TopologicalNodes ?topologicalNode.
            # }


            BIND((xsd:double(?_bPerSec) * xsd:double(?_sections)) as ?b)
            BIND((xsd:double(?_gPerSec) * xsd:double(?_sections)) as ?g)
        }
        ORDER BY ?ShuntCompensator
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        if self._source.split_profiles:
            named_graphs = self._source.named_graphs
            args = {
                "$IN_SERVICE": self._in_service_graph("?ShuntCompensator"),
                "$TOPO_ISLAND": self._at_topo_island_node_graph("?topologicalNode"),
                "$EQ_GRAPH": named_graphs.format_for_query(Profile.EQ),
                "$TP_GRAPH": named_graphs.format_for_query(Profile.TP),
                "$SSH_GRAPH": named_graphs.format_for_query(Profile.SSH),
                "$SV_GRAPH": named_graphs.format_for_query(Profile.SV),
            }
            q = self._replace(self._query_graph, args)
            res = self._source.query(q)
        else:
            args = {
                "$IN_SERVICE": self._in_service(),
                "$TOPO_ISLAND": self._at_topo_island_node("?topologicalNode"),
            }
            q = self._replace(self._query, args)
            res = self._source.query(q)

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(
            res["ShuntCompensator"], res["name"]
        )
        arr["node"] = [
            self._id_mapping.get_pgm_id(uuid) for uuid in res["topologicalNode"]
        ]
        arr["status"] = res["connected"]
        arr["b1"] = res["b"]
        arr["g1"] = res["g"]

        extra_info = self._create_extra_info_with_type(arr, "LinearShuntCompensator")

        for i, pgm_id in enumerate(arr["id"]):
            extra_info[pgm_id]["_terminal"] = res["Terminal"][i]

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.shunt
