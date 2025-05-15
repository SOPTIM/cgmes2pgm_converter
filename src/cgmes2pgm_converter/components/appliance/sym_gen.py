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

from cgmes2pgm_converter.common import convert_unit_multiplier

from ..component import AbstractPgmComponentBuilder


class SymGenBuilder(AbstractPgmComponentBuilder):
    _query = """
        SELECT ?name ?topologicalNode ?connected ?EnergyProducer ?p ?q ?targetVoltage ?valMultiplier ?type
        WHERE {
            ?Terminal a cim:Terminal;
                        cim:Terminal.TopologicalNode ?topologicalNode;
                        cim:ACDCTerminal.connected ?connected;
                        cim:Terminal.ConductingEquipment ?EnergyProducer.

            VALUES ?_type { cim:GeneratingUnit
                           cim:SynchronousMachine
                           cim:ExternalNetworkInjection
                           cim:EquivalentInjection
                           cim:StaticVarCompensator
                           cim:EnergySource
                           }

            ?EnergyProducer a ?_type;
                            $IN_SERVICE
                            # cim:Equipment.inService "true";
                            cim:IdentifiedObject.name ?name.

            BIND(STRAFTER(STR(?_type), "#") AS ?type)

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?topologicalNode.

            OPTIONAL {
                ?RegC a cim:RegulatingControl;
                        cim:RegulatingControl.Terminal ?Terminal;
                        cim:RegulatingControl.mode <cim:RegulatingControlModeKind.voltage>;
                        cim:RegulatingControl.targetValue ?targetVoltage;
                        cim:RegulatingControl.targetValueUnitMultiplier ?valMultiplier.
            }

            OPTIONAL { ?EnergyProducer cim:RotatingMachine.p ?_pRotMa. }
            OPTIONAL { ?EnergyProducer cim:RotatingMachine.q ?_qRotMa. }
            OPTIONAL { ?EnergyProducer cim:ExternalNetworkInjection.p ?_pExtInj. }
            OPTIONAL { ?EnergyProducer cim:ExternalNetworkInjection.q ?_qExInj. }
            OPTIONAL { ?EnergyProducer cim:EquivalentInjection.p ?_pEquivInj. }
            OPTIONAL { ?EnergyProducer cim:EquivalentInjection.q ?_qEquivInj. }
            OPTIONAL { ?EnergyProducer cim:StaticVarCompensator.q ?_qSVC. }
  			OPTIONAL { ?EnergyProducer cim:EnergySource.activePower ?_pEnSrc. }
            OPTIONAL { ?EnergyProducer cim:EnergySource.reactivePower ?_qEnSrc. }

            BIND(COALESCE(?_pRotMa, ?_pExtInj, ?_pEquivInj, ?_pEnSrc, 0) AS ?p)
            BIND(COALESCE(?_qRotMa, ?_qExInj, ?_qEquivInj, ?_qEnSrc, ?_qSVC) AS ?q)

            FILTER(BOUND(?p) && BOUND(?q))

        }
        ORDER BY ?EnergyProducer
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | dict]:
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?topologicalNode"),
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        # Mw, MVar to W, Var
        res["p"] = -res["p"] * 1e6
        res["q"] = -res["q"] * 1e6

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(res["EnergyProducer"], res["name"])
        arr["node"] = [
            self._id_mapping.get_pgm_id(uuid) for uuid in res["topologicalNode"]
        ]
        arr["status"] = res["connected"]
        arr["type"] = LoadGenType.const_power
        arr["p_specified"] = res["p"]
        arr["q_specified"] = res["q"]

        extra_info = self._create_extra_info_with_types(arr, res["type"])

        for i, pgm_id in enumerate(arr["id"]):
            if not np.isnan(res["targetVoltage"][i]):
                info = extra_info.setdefault(pgm_id, {})
                info["_targetVoltage"] = res["targetVoltage"][
                    i
                ] * convert_unit_multiplier(
                    res["valMultiplier"][i], self._source.cim_namespace
                )

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.sym_gen
