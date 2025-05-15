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


class SourceBuilder(AbstractPgmComponentBuilder):

    def is_active(self):
        return not self._converter_options.sources_from_sv

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        pgm_id, _ = self.get_source()

        # Extract Row with source id
        idx = input_data[ComponentType.sym_gen]["id"] == pgm_id
        source = input_data[ComponentType.sym_gen][idx]
        # Remove Row
        input_data[ComponentType.sym_gen] = input_data[ComponentType.sym_gen][~idx]

        # Add Source to Source
        sources = initialize_array(self._data_type, ComponentType.source, 1)
        sources["id"] = source["id"]
        sources["status"] = source["status"]
        sources["node"] = source["node"]
        sources["u_ref"] = 1
        sources["sk"] = 1e40
        sources["rx_ratio"] = 0.1
        sources["z01_ratio"] = 1

        extra_info = {}
        return sources, extra_info

    def get_source(self) -> tuple[int, float]:
        query = """
            SELECT ?EnergyProducer ?ref ?uref
            WHERE {
                VALUES ?type { cim:ExternalNetworkInjection cim:SynchronousMachine}
                ?EnergyProducer a ?type.

                OPTIONAL { ?EnergyProducer cim:SynchronousMachine.referencePriority ?_RefS. }
                OPTIONAL { ?EnergyProducer cim:ExternalNetworkInjection.referencePriority ?_RefE.}
                BIND(COALESCE(?_RefS, ?_RefE) AS ?ref)

                ?EnergyProducer $IN_SERVICE
                                # cim:Equipment.inService "true";
                                cim:Equipment.EquipmentContainer ?_voltLevel.

                ?_voltLevel cim:VoltageLevel.BaseVoltage ?_baseVoltage.
                ?_baseVoltage cim:BaseVoltage.nominalVoltage ?uref.

                ?terminal a cim:Terminal;
                            cim:Terminal.ConductingEquipment ?EnergyProducer;
                            cim:Terminal.TopologicalNode ?topologicalNode;
                            cim:ACDCTerminal.connected "true".

                $TOPO_ISLAND
                #?topoIsland cim:IdentifiedObject.name "Network";
                #            cim:TopologicalIsland.TopologicalNodes ?topologicalNode.
            }
            ORDER BY ASC(?ref) ?EnergyProducer
        """
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?topologicalNode"),
        }
        q = self._replace(query, args)
        res = self._source.query(q)

        if res.shape[0] == 0:
            raise ValueError(
                "Grid has no SynchronousMachines or ExternalNetworkInjections"
            )

        ref = res["ref"]
        ## replace 0 with 9999 and determine the index of minimal value
        n_ref_is_min = ref.where(ref > 0, 9999).idxmin()

        # Return element with lowest reference priority != 0
        return (
            self._id_mapping.get_pgm_id(res["EnergyProducer"][n_ref_is_min]),
            res["uref"][n_ref_is_min] * 1e3,
        )

    def component_name(self) -> ComponentType:
        return ComponentType.source
