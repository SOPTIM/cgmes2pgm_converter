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
from power_grid_model import ComponentType, MeasuredTerminalType, initialize_array

from cgmes2pgm_converter.common import Profile

from ..component import AbstractPgmComponentBuilder


class ReactivePowerForShuntBuilder(AbstractPgmComponentBuilder):

    def is_active(self):
        return (
            self._converter_options.measurement_substitution.imeas_used_for_qcalc.enable
        )

    _query_meas_in_graph = """
        SELECT ?name ?eq ?meas_i ?meas_U ?nom_u ?nom_u_shunt ?tn ?connected
        WHERE {
            ?Terminal a cim:Terminal ;
                    cim:Terminal.TopologicalNode ?tn;
                    cim:ACDCTerminal.connected ?connected;
                    cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nom_u.

            VALUES ?type {
                cim:LinearShuntCompensator
                cim:NonlinearShuntCompensator
            }

            ?eq a ?type;
                cim:ShuntCompensator.nomU ?nom_u_shunt;
                $IN_SERVICE
                # cim:Equipment.inService "true";
                cim:IdentifiedObject.name ?name.
            GRAPH ?g_i {
                ?_meas cim:Measurement.measurementType "LineCurrent";
                    cim:Measurement.PowerSystemResource ?eq;
                    cim:Measurement.Terminal ?Terminal.

                ?_measVal_scada cim:AnalogValue.Analog ?_meas;
                                cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name 	"SCADA".
            }

            GRAPH ?g_i_val {
                ?_measVal_scada cim:AnalogValue.value ?meas_i.
            }

            OPTIONAL {

                GRAPH ?g_u {
                    ?_measU cim:Measurement.measurementType "LineToLineVoltage";
                            cim:Measurement.PowerSystemResource ?eq;
                            cim:Measurement.Terminal ?Terminal.
                    ?_measVal_u cim:AnalogValue.Analog ?_measU;
                                    cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name 	"SCADA".
                }
                GRAPH ?g_u_val {
                    ?_measVal_u cim:AnalogValue.value ?meas_U.
                }
            }

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?tn.

        }
        ORDER BY ?eq
    """

    _query_meas_in_default = """
        SELECT ?name ?eq ?meas_i ?meas_U ?nom_u ?nom_u_shunt ?tn ?connected
        WHERE {
            ?Terminal a cim:Terminal ;
                    cim:Terminal.TopologicalNode ?tn;
                    cim:ACDCTerminal.connected ?connected;
                    cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nom_u.

            VALUES ?type {
                cim:LinearShuntCompensator
                cim:NonlinearShuntCompensator
            }

            ?eq a ?type;
                cim:ShuntCompensator.nomU ?nom_u_shunt;
                $IN_SERVICE
                # cim:Equipment.inService "true";
                cim:IdentifiedObject.name ?name.

            ?_meas cim:Measurement.measurementType "LineCurrent";
                   cim:Measurement.PowerSystemResource ?eq;
                   cim:Measurement.Terminal ?Terminal.

            ?_measVal_scada cim:AnalogValue.Analog ?_meas;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name 	"SCADA";
                            cim:AnalogValue.value ?meas_i.


            OPTIONAL {
            ?_meas4 cim:Measurement.measurementType "LineToLineVoltage";
                    cim:Measurement.PowerSystemResource ?eq;
                    cim:Measurement.Terminal ?Terminal.

            ?_measVal_scada3 cim:AnalogValue.Analog ?_meas4;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name 	"SCADA";
                            cim:AnalogValue.value ?meas_U.
            }

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?tn.

        }
        ORDER BY ?eq
     """

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        # get all power sensors with the measured object id as key
        measured_objects_dict = {
            sensor["measured_object"]: sensor
            for sensor in input_data[ComponentType.sym_power_sensor]
        }

        shunt_ids = input_data["shunt"]["id"]

        # determine all shunts without Q measurement
        shunt_without_q_meas = []
        for shunt_id in shunt_ids:
            if shunt_id not in measured_objects_dict:
                shunt_without_q_meas.append(shunt_id)

        if Profile.MEAS in self._source.graphs:
            res_orig = self._read_meas_from_named_graph()
        else:
            res_orig = self._read_meas_from_default_graph()

        # Determine median value of measured u
        agg_dict = {
            "meas_U": "median",
        }
        agg_dict.update(
            {col: "first" for col in res_orig.columns if col not in ["eq", "meas_U"]}
        )

        # and build the result again
        res = res_orig.groupby("eq").agg(agg_dict).reset_index()

        # get the pgm_id for the shunts with i meas
        shunt_pgm_with_i_meas = [
            self._id_mapping.get_pgm_id(uuid) for uuid in res["eq"]
        ]

        # determine the intersection of shunts with I but without Q measurement
        shunt_with_i_without_q_meas = list(
            set(shunt_without_q_meas) & set(shunt_pgm_with_i_meas)
        )

        arr = initialize_array(
            self._data_type,
            self.component_name(),
            len(shunt_with_i_without_q_meas),
        )

        if shunt_with_i_without_q_meas:

            # create new IDs and names for the sensor
            sensor_iris = [
                self._id_mapping.get_cgmes_iri(shunt) + "_Q"
                for shunt in shunt_without_q_meas
            ]

            sensor_names = [
                self._id_mapping.get_name_from_pgm(shunt) + " Meas Q"
                for shunt in shunt_without_q_meas
            ]

            arr["id"] = self._id_mapping.add_cgmes_iris(sensor_iris, sensor_names)
            arr["measured_object"] = shunt_without_q_meas

            arr["measured_terminal_type"] = MeasuredTerminalType.shunt

            u = res["meas_U"].fillna(res["nom_u"]) * 1e3

            # Replace remaining NaN values in u with the corresponding values from 'nom_u_shunt'
            u = u.fillna(res["nom_u_shunt"]) * 1e3

            # TODO: if there is no Q or I measurement given for this shunt compensator,
            # the reactive power could be calculated
            # via the nominal voltage and the susceptance B of the shunt compensator: Q = Un^2 * B
            arr["q_measured"] = np.sqrt(3) * u * res["meas_i"]
            arr["p_measured"] = 0.0

            arr["q_sigma"] = (
                self._converter_options.measurement_substitution.passive_nodes.sigma
                * 1e6
            )
            arr["p_sigma"] = arr["q_sigma"]
            arr["power_sigma"] = arr["q_sigma"]
        return arr, None

    def _read_meas_from_default_graph(self):
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?tn"),
        }
        q = self._replace(self._query_meas_in_default, args)
        res = self._source.query(q)
        return res

    def _read_meas_from_named_graph(self):
        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?tn"),
        }
        q = self._replace(self._query_meas_in_graph, args)
        res = self._source.query(q)
        return res

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor
