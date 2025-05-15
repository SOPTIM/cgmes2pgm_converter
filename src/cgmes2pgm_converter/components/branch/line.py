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

from cgmes2pgm_converter.common import AbstractCgmesIdMapping, BranchType, CgmesDataset

from ..component import AbstractPgmComponentBuilder


class LineBuilder(AbstractPgmComponentBuilder):
    _query = """
        SELECT  ?line
                (SAMPLE(?_name) as ?name)
                (SAMPLE(?_bch) as ?bch)
                (SAMPLE(?_gch) as ?gch)
                (SAMPLE(?_length) as ?length)
                (SAMPLE(?_r) as ?r)
                (SAMPLE(?_x) as ?x)
                (SAMPLE(?_tn1) as ?tn1)
                (SAMPLE(?_tn2) as ?tn2)
                (SAMPLE(?_nomv1) as ?nomv1)
                (SAMPLE(?_nomv2) as ?nomv2)
                (SAMPLE(?_status1) as ?status1)
                (SAMPLE(?_status2) as ?status2)
                (SAMPLE(?__type) as ?type)
                (SAMPLE(?_term1) as ?term1)
                (SAMPLE(?_term2) as ?term2)
        WHERE {
            VALUES ?_type {
                cim:ACLineSegment
                cim:EquivalentBranch
                cim:SeriesCompensator
            }
            ?line a ?_type;
                    $IN_SERVICE
                    # cim:Equipment.inService "true";
                    cim:IdentifiedObject.name ?_name.

            BIND(STRAFTER(STR(?_type), "#") AS ?__type)

            OPTIONAL { ?line cim:ACLineSegment.r ?_aclR. }
            OPTIONAL { ?line cim:ACLineSegment.x ?_aclX. }
            OPTIONAL { ?line cim:ACLineSegment.gch ?_aclGch. }
            OPTIONAL { ?line cim:ACLineSegment.bch ?_aclBch. }

            OPTIONAL { ?line cim:EquivalentBranch.r ?_eqbR. }
            OPTIONAL { ?line cim:EquivalentBranch.x ?_eqbX. }

            OPTIONAL { ?line cim:SeriesCompensator.r ?_srcR. }
            OPTIONAL { ?line cim:SeriesCompensator.x ?_srcX. }

            ?_term1 a cim:Terminal;
                cim:Terminal.ConductingEquipment ?line;
                cim:Terminal.TopologicalNode ?_tn1;
                cim:ACDCTerminal.sequenceNumber "1"; ## order Terminal/Node by sequence number
                cim:ACDCTerminal.connected ?_status1.

            ?_term2 a cim:Terminal;
                      cim:Terminal.ConductingEquipment ?line;
                      cim:Terminal.TopologicalNode ?_tn2;
                      cim:ACDCTerminal.sequenceNumber "2";
                      cim:ACDCTerminal.connected ?_status2.

            ?_tn1 cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?_nomv1.
            ?_tn2 cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?_nomv2.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?_tn1;
            #            cim:TopologicalIsland.TopologicalNodes ?_tn2.

            BIND(COALESCE(?_aclR, ?_eqbR, ?_srcR, "0.0") as ?_r)
            BIND(COALESCE(?_aclX, ?_eqbX, ?_srcX, "0.0") as ?_x)
            BIND(COALESCE(?_aclBch, "0.0") as ?_bch)
            BIND(COALESCE(?_aclGch, "0.0") as ?_gch)

            FILTER(?_tn1 != ?_tn2)
            FILTER(?_status1 = "true" &&  ?_status2 = "true")

            $NOMV_FILTER
            #FILTER(?_nomv1 = ?_nomv2)
        }

        GROUP BY ?line
        ORDER BY ?line
    """

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, data_type)
        self._component_name = (
            ComponentType.generic_branch
            if self._converter_options.use_generic_branch[BranchType.LINE]
            else ComponentType.line
        )

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?_tn1", "?_tn2"),
            "$NOMV_FILTER": "FILTER(?_nomv1 = ?_nomv2)",  # <- filter for same voltage levels
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(res["line"], res["name"])
        arr["from_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn1"]]
        arr["to_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn2"]]
        arr["from_status"] = res["status1"]
        arr["to_status"] = res["status2"]
        arr["r1"] = res["r"]
        arr["x1"] = res["x"]

        c1 = res["bch"] / (2 * 50 * np.pi)
        tan1 = np.nan_to_num(res["gch"] / res["bch"], posinf=0, neginf=0)
        gch = res["gch"]
        bch = res["bch"]

        if self.component_name() == ComponentType.line:
            # Benato: The Positive Sequence Model of Symmetrical Lines - Section 2.3.4
            arr["c1"] = c1
            arr["tan1"] = tan1
        else:
            arr["g1"] = res["gch"]
            arr["b1"] = res["bch"]
            arr["k"] = 1.0
            arr["theta"] = 0.0

        extra_info = {}
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_term1": res["term1"][idx],
                "_term2": res["term2"][idx],
                "_type": res["type"][idx],
                "_name": res["name"][idx],
                "_c1": c1[idx],
                "_tan1": tan1[idx],
                "_g1": gch[idx],
                "_b1": bch[idx],
            }

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return self._component_name
