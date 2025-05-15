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
import pandas as pd
from power_grid_model import ComponentType, MeasuredTerminalType, initialize_array
from power_grid_model_io.data_types import ExtraInfo

from cgmes2pgm_converter.common import Profile, SymPowerType

from ..component import AbstractPgmComponentBuilder

log = logging.debug


class SymPowerBuilder(AbstractPgmComponentBuilder):
    """
    ToDo: For now measurements in the default graph and measurements in named graphs are
    not handled the same way.
    In the default graph, measurements at the same terminal are merged and the sensorAccuracy is
    interpreted as sigma.
    """

    _query_meas_in_graph = """
        SELECT
            (SAMPLE(?_eq) as ?eq)
            (SAMPLE(?_tn) as ?tn)
            ?term
            (SAMPLE(?_max_p) as ?max_p)
            (SAMPLE(?_min_p) as ?min_p)
            (SAMPLE(?_p) as ?p)
            (SAMPLE(?_max_q) as ?max_q)
            (SAMPLE(?_min_q) as ?min_q)
            (SAMPLE(?_q) as ?q)
            (SAMPLE(?_acc_p) as ?acc_p)
            (SAMPLE(?_acc_q) as ?acc_q)
            (SAMPLE(?_sigma_p) as ?sigma_p)
            (SAMPLE(?_sigma_q) as ?sigma_q)
            (SAMPLE(?_name_p) as ?name_p)
            (SAMPLE(?_name_q) as ?name_q)
            (SAMPLE(?_meas_p) as ?meas_p)
            (SAMPLE(?_meas_q) as ?meas_q)
        WHERE {
        GRAPH ?g_p {
            ?_meas_p cim:Measurement.measurementType ?_type_p;
                    cim:IdentifiedObject.name ?_name_p;
                    cim:Measurement.PowerSystemResource ?_eq;
                    cim:Analog.maxValue ?_max_p;
                    cim:Analog.minValue ?_min_p;
                    cim:Measurement.Terminal ?term.

            ?_measVal_p cim:AnalogValue.Analog ?_meas_p.
            OPTIONAL { ?_measVal_p cim:MeasurementValue.sensorAccuracy ?_acc_p. }
            OPTIONAL { ?_measVal_p cim:MeasurementValue.sensorSigma ?_sigma_p. }
        }
        FILTER(?_type_p = "ThreePhaseActivePower")

        ?term cim:Terminal.TopologicalNode ?_tn.

        $TOPO_ISLAND
        #?topoIsland cim:IdentifiedObject.name "Network";
        #            cim:TopologicalIsland.TopologicalNodes ?_tn.

        GRAPH ?g_q {
            ?_meas_q cim:Measurement.measurementType ?_type_q;
                    cim:IdentifiedObject.name ?_name_q;
                    cim:Measurement.PowerSystemResource ?_eq;
                    cim:Analog.maxValue ?_max_q;
                    cim:Analog.minValue ?_min_q;
                    cim:Measurement.Terminal ?term.

    		?_meas_val_q cim:AnalogValue.Analog ?_meas_q.
    		OPTIONAL { ?_meas_val_q cim:MeasurementValue.sensorAccuracy ?_acc_q. }
    		OPTIONAL { ?_meas_val_q cim:MeasurementValue.sensorSigma ?_sigma_q. }
        }
        FiLTER(?_type_q = "ThreePhaseReactivePower")

        GRAPH ?g_p_val {
            ?_measVal_p cim:AnalogValue.value ?_p.
        }

        GRAPH ?g_q_val {
            ?_meas_val_q cim:AnalogValue.value ?_q.
        }

        }
        GROUP BY ?term
        ORDER BY ?term
    """

    _query_meas_in_default = """
        SELECT
            ?eq
            ?tn
            ?nomv
            ?term
            ?value
            ?sigma
            ?name
            ?meas
            ?pfi
        WHERE {
            # "ThreePhaseActivePower" or "ThreePhaseReactivePower"
            ?meas cim:Measurement.measurementType $MEASUREMENT_TYPE;
                        cim:IdentifiedObject.name ?name;
                        cim:Measurement.Terminal ?term.

            OPTIONAL {
                ?meas cim:Analog.positiveFlowIn ?pfi.
            }

            ?_measVal_scada cim:AnalogValue.Analog ?meas;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "SCADA";
                            cim:AnalogValue.value ?value.

            OPTIONAL {
                ?_measVal_est cim:AnalogValue.Analog ?meas;
                              cim:MeasurementValue.sensorAccuracy ?sigma.
            }

            ?term cim:Terminal.TopologicalNode ?tn;
                cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nomv.

            $TOPO_ISLAND
            #?topoIsland # cim:IdentifiedObject.name "TODO";
            #        cim:TopologicalIsland.TopologicalNodes ?tn.

        }
        ORDER BY ?term
    """

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        if Profile.OP in self._source.graphs:
            res = self._read_meas_from_graph()
        else:
            res = self._read_meas_from_default_graph()

        terminal_types = self.get_terminal_types(res, input_data)
        res = res[terminal_types != -1]
        res.reset_index(drop=True, inplace=True)
        terminal_types = terminal_types[terminal_types != -1]

        res["p"] *= 1e6
        res["q"] *= 1e6

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])

        # Use p measurement for name and id
        arr["id"] = self._id_mapping.add_cgmes_iris(res["meas_p"], res["name_p"])

        # A measured object can be a regular cgmes equipment or a replacement
        # object that was added in the removal of certain components (e.g. phase shifting
        # transformers). Such replacement objects are identified by an additional
        # terminal IRI. Here, we pass on both the equipment and the terminal IRIs and let
        # the ID mapper look up the correct PGM ID.
        arr["measured_object"] = [
            self._id_mapping.get_pgm_id(eq, term)
            for eq, term in zip(res["eq"], res["term"])
        ]
        arr["measured_terminal_type"] = terminal_types
        arr["p_measured"] = res["p"]
        arr["q_measured"] = res["q"]

        p_sigma = res["sigma_p"] * 1e6
        q_sigma = res["sigma_q"] * 1e6

        arr["p_sigma"] = p_sigma
        arr["q_sigma"] = q_sigma
        arr["power_sigma"] = arr["p_sigma"]

        # Invert power for generators and sources as they use generation reference convention in PGM
        arr["p_measured"] = np.where(
            np.logical_or(
                terminal_types == MeasuredTerminalType.generator,
                terminal_types == MeasuredTerminalType.source,
            ),
            -arr["p_measured"],
            arr["p_measured"],
        )

        arr["q_measured"] = np.where(
            np.logical_or(
                terminal_types == MeasuredTerminalType.generator,
                terminal_types == MeasuredTerminalType.source,
            ),
            -arr["q_measured"],
            arr["q_measured"],
        )

        extra_info = self._create_extra_info_with_types(arr, res["meas_type"])

        arr = np.concatenate(
            (
                arr,
                self._build_sensors_for_replaced_lines(arr, input_data, extra_info),
            )
        )

        return arr, extra_info

    def _read_meas_from_graph(self):
        args = {"$TOPO_ISLAND": self._at_topo_island_node("?_tn")}
        q = self._replace(self._query_meas_in_graph, args)
        res = self._source.query(q)
        res["meas_type"] = SymPowerType.FIELD

        return res

    def _read_meas_from_default_graph(self):
        args = {
            "$TOPO_ISLAND": self._at_topo_island_node("?tn"),
            "$MEASUREMENT_TYPE": '"ThreePhaseActivePower"',
        }
        # Read active power measurements
        q_p = self._replace(self._query_meas_in_default, args)
        res_p = self._source.query(q_p)

        # Invert Measurement if "positiveFlowIn" is set to true
        res_p["value"] = res_p["value"].where(res_p["pfi"], res_p["value"] * -1)

        # Read reactive power measurements
        args["$MEASUREMENT_TYPE"] = '"ThreePhaseReactivePower"'
        q_q = self._replace(self._query_meas_in_default, args)
        res_q = self._source.query(q_q)

        # Invert Measurement if "positiveFlowIn" is set to true
        res_q["value"] = res_q["value"].where(res_q["pfi"], res_q["value"] * -1)

        meas_by_term = {}
        self._join_measurements_by_terminal(
            res_p, meas_by_term, "ThreePhaseActivePower"
        )
        self._join_measurements_by_terminal(
            res_q, meas_by_term, "ThreePhaseReactivePower"
        )

        p = []
        q = []
        p_sigma = []
        q_sigma = []
        p_meas = []
        p_name = []
        meas_type = []

        # get one p- and q-measurement per terminal for the potentially many available
        for val in meas_by_term.values():
            meas_p = val.get("ThreePhaseActivePower")
            meas_q = val.get("ThreePhaseReactivePower")

            if meas_p is None and meas_q is None:
                continue

            p_m, p_s, p_n, p_mm, p_is_default = self._get_one_measurement_and_sigma(
                meas_p, val["nomv"]
            )

            q_m, q_s, q_n, q_mm, q_is_default = self._get_one_measurement_and_sigma(
                meas_q, val["nomv"]
            )

            p.append(p_m)
            p_sigma.append(p_s)

            q.append(q_m)
            q_sigma.append(q_s)

            if p_n is not None:
                p_name.append(p_n)
            else:
                p_name.append(q_n)

            if p_mm is not None:
                p_meas.append(p_mm)
            else:
                p_meas.append(q_mm)

            if p_is_default and q_is_default:
                # This should not happen here. Terminals without any power measurements
                # are handled in power_sensor_from_branch.py
                raise RuntimeError("Unexpected: Both P and Q are default values.")

            if p_is_default:
                meas_type.append(SymPowerType.P_ZERO)
            elif q_is_default:
                meas_type.append(SymPowerType.Q_ZERO)
            else:
                meas_type.append(SymPowerType.FIELD)

        # Because of I-measurements there might be more terminals than needed for P/Q-measurements.
        # Filter out terminals with only I-measurements
        term, eq, tn = self._get_valid_values(meas_by_term)

        res_data = {
            "term": term,
            "eq": eq,
            "tn": tn,
            "p": p,
            "q": q,
            "meas_p": p_meas,
            "name_p": p_name,
            "sigma_p": p_sigma,
            "sigma_q": q_sigma,
            "meas_type": meas_type,
        }
        res = pd.DataFrame(res_data)

        return res

    def _get_valid_values(self, meas_by_term):
        term = []
        eq = []
        tn = []
        for key, val in meas_by_term.items():
            if self._is_valid_value(val):
                term.append(key)
                eq.append(val["eq"])
                tn.append(val["tn"])

        return term, eq, tn

    def _get_valid_values_for_key(self, meas_by_term, key):
        return [val[key] for val in meas_by_term.values() if self._is_valid_value(val)]

    def _is_valid_value(self, val):
        """A value is not valid if only the current measurement is available."""
        return (
            val.get("ThreePhaseActivePower") is not None
            or val.get("ThreePhaseReactivePower") is not None
        )

    def _build_sensors_for_replaced_lines(
        self, arr, input_data: dict, extra_info: ExtraInfo
    ) -> np.ndarray:
        """Duplicate sensors for lines that were replaced by a source.
        The original sensors were moved from the lines to the sources.
        Here, we are adding the sensors again to the lines. This allows
        to later enable the line again by setting the status of the line
        to 1 and the status of the appliance to 0, so that the sensors
        are only used once.
        """
        # find sources that were added as replacement for lines
        appl_extras = [
            (idx, src)
            for idx, src in self._extra_info.items()
            if src.get("_type") == "SubstationLineAsSource"
        ]

        if len(appl_extras) == 0:
            return initialize_array(self._data_type, self.component_name(), 0)

        # create map from PGM ID to a helper object in order to resolve references easily
        id_map = {}

        for line in input_data[ComponentType.line]:
            id_map[line["id"]] = {
                "from_node": line["from_node"],
                "to_node": line["to_node"],
            }

        for gen_br in input_data[ComponentType.generic_branch]:
            id_map[gen_br["id"]] = {
                "from_node": gen_br["from_node"],
                "to_node": gen_br["to_node"],
            }

        for src in input_data[ComponentType.source]:
            id_map[src["id"]] = {"node": src["node"]}

        for gen in input_data[ComponentType.sym_gen]:
            id_map[gen["id"]] = {"node": gen["node"]}

        # add sensors to the relevant helper objects referenced by the sources/generations
        for sensor in arr:
            mo_id = sensor["measured_object"]
            mtt = sensor["measured_terminal_type"]
            mo = id_map.get(mo_id, {})
            mo["sensor"] = (mtt, sensor)

        # array for the properties of the duplicated sensors
        ids = []
        measured_objects = []
        measured_terminal_types = []
        p_measured = []
        q_measured = []
        p_sigma = []
        q_sigma = []
        power_sigma = []

        for appl_idx, appl in appl_extras:
            # get the branch that was replaced by the source/generation
            branch_id = appl["branch"]
            branch = id_map[branch_id]

            # get the nodes of the branch
            from_node = branch["from_node"]
            to_node = branch["to_node"]

            # get the sensor that was moved to the source/generation
            sensor = id_map[appl_idx]
            sensor_node = id_map[appl_idx]["node"]
            sensor_ = sensor.get("sensor")
            if sensor_ is None:
                continue
            sensor_data = sensor_[1]

            # create new sensor with adjusted name and iri
            sensor_iri = self._id_mapping.get_cgmes_iri(appl_idx)
            sensor_name = self._id_mapping.get_name_from_pgm(appl_idx)
            new_id = self._id_mapping.add_cgmes_iri(
                sensor_iri + "_dupl", sensor_name + "_dupl"
            )
            ids.append(new_id)

            # connect the sensor to the branch with the correct terminal type
            measured_objects.append(branch_id)
            if sensor_node == from_node:
                measured_terminal_types.append(MeasuredTerminalType.branch_from)
            elif sensor_node == to_node:
                measured_terminal_types.append(MeasuredTerminalType.branch_to)
            else:
                raise ValueError("Sensor node not in branch nodes")

            # (re-)negate the sensor values, because they were already negated
            # when they were moved to the sources
            p_measured.append(sensor_data["p_measured"] * -1)
            q_measured.append(sensor_data["q_measured"] * -1)

            # keep the original sigmas
            p_sigma.append(sensor_data["p_sigma"])
            q_sigma.append(sensor_data["q_sigma"])
            power_sigma.append(sensor_data["p_sigma"])

        # add the new sensors to the array
        arr_branches = initialize_array(
            self._data_type, self.component_name(), len(ids)
        )

        arr_branches["id"] = ids
        arr_branches["measured_object"] = measured_objects
        arr_branches["measured_terminal_type"] = measured_terminal_types
        arr_branches["p_measured"] = p_measured
        arr_branches["q_measured"] = q_measured
        arr_branches["p_sigma"] = p_sigma
        arr_branches["q_sigma"] = q_sigma
        arr_branches["power_sigma"] = power_sigma

        self._create_extra_info_with_type(arr_branches, SymPowerType.SPLIT, extra_info)

        return arr_branches

    def sigma_from_accuracy(
        self, res: dict[str, np.ndarray], acc: str, maximum: str, minimum: str
    ) -> np.ndarray:
        return (
            (1 - res[acc]) * np.maximum(np.abs(res[maximum]), np.abs(res[minimum])) / 3
        )

    def get_terminal_types(
        self, res: pd.DataFrame, input_data: dict[ComponentType, np.ndarray]
    ) -> np.ndarray:
        # eq may not be in id_mapping
        eq_ids = -np.ones(res.shape[0], dtype=int)
        for i, (eq, term) in enumerate(zip(res["eq"], res["term"])):
            if eq in self._id_mapping:
                eq_ids[i] = self._id_mapping.get_pgm_id(eq, term)
            else:
                eq_ids[i] = -1

        terminal_types = -np.ones(len(eq_ids), dtype=int)

        for i, eq_id in enumerate(eq_ids):
            meas_node = self._id_mapping.get_pgm_id(res["tn"].iloc[i])

            if eq_id in input_data[ComponentType.sym_gen]["id"]:
                terminal_types[i] = MeasuredTerminalType.generator
            elif eq_id in input_data[ComponentType.sym_load]["id"]:
                terminal_types[i] = MeasuredTerminalType.load
            elif eq_id in input_data[ComponentType.source]["id"]:
                terminal_types[i] = MeasuredTerminalType.source
            elif eq_id in input_data[ComponentType.shunt]["id"]:
                terminal_types[i] = MeasuredTerminalType.shunt
            elif eq_id in input_data[ComponentType.line]["id"]:

                node_from = input_data[ComponentType.line]["from_node"][
                    input_data[ComponentType.line]["id"] == eq_id
                ]
                node_to = input_data[ComponentType.line]["to_node"][
                    input_data[ComponentType.line]["id"] == eq_id
                ]

                if meas_node == node_from:
                    terminal_types[i] = MeasuredTerminalType.branch_from
                elif meas_node == node_to:
                    terminal_types[i] = MeasuredTerminalType.branch_to

            elif eq_id in input_data[ComponentType.generic_branch]["id"]:

                node_from = input_data[ComponentType.generic_branch]["from_node"][
                    input_data[ComponentType.generic_branch]["id"] == eq_id
                ]
                node_to = input_data[ComponentType.generic_branch]["to_node"][
                    input_data[ComponentType.generic_branch]["id"] == eq_id
                ]

                if meas_node == node_from:
                    terminal_types[i] = MeasuredTerminalType.branch_from
                elif meas_node == node_to:
                    terminal_types[i] = MeasuredTerminalType.branch_to

            elif eq_id in input_data[ComponentType.transformer]["id"]:

                node_from = input_data[ComponentType.transformer]["from_node"][
                    input_data[ComponentType.transformer]["id"] == eq_id
                ]
                node_to = input_data[ComponentType.transformer]["to_node"][
                    input_data[ComponentType.transformer]["id"] == eq_id
                ]

                if meas_node == node_from:
                    terminal_types[i] = MeasuredTerminalType.branch_from
                elif meas_node == node_to:
                    terminal_types[i] = MeasuredTerminalType.branch_to

            elif eq_id in input_data[ComponentType.three_winding_transformer]["id"]:
                node_1 = input_data[ComponentType.three_winding_transformer]["node_1"][
                    input_data[ComponentType.three_winding_transformer]["id"] == eq_id
                ]
                node_2 = input_data[ComponentType.three_winding_transformer]["node_2"][
                    input_data[ComponentType.three_winding_transformer]["id"] == eq_id
                ]
                node_3 = input_data[ComponentType.three_winding_transformer]["node_3"][
                    input_data[ComponentType.three_winding_transformer]["id"] == eq_id
                ]

                if meas_node == node_1:
                    terminal_types[i] = MeasuredTerminalType.branch3_1
                elif meas_node == node_2:
                    terminal_types[i] = MeasuredTerminalType.branch3_2
                elif meas_node == node_3:
                    terminal_types[i] = MeasuredTerminalType.branch3_3

            else:
                terminal_types[i] = -1

        return terminal_types

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor

    def _get_one_measurement_and_sigma(
        self, meas_pq, nomv
    ) -> tuple[float | None, float | None, str | None, str | None, bool, float]:
        has_sigma = (
            any(not np.isnan(m["sigma"]) for m in meas_pq)
            if meas_pq is not None
            else False
        )
        has_value = (
            any(not np.isnan(m["value"]) for m in meas_pq)
            if meas_pq is not None
            else False
        )

        value = None
        sigma = None
        name = None
        meas = None
        is_default = False

        if has_sigma and has_value:
            # remove measurements that have no sigma
            meas_filtered = [v for v in meas_pq if not np.isnan(v["sigma"])]

            # get median value if the available measurements
            meas_val = self._get_median_value(meas_filtered, "value")

            value = meas_val["value"]
            sigma = meas_val["sigma"]
            name = meas_val["name"]
            meas = meas_val["meas"]
        elif has_value:
            # there is no sigma -> get median value and use default sigma
            meas_val = self._get_median_value(meas_pq, "value")

            value = meas_val["value"]
            sigma = self._converter_options.measurement_substitution.default_sigma_pq.get_sigma(
                nomv
            )
            name = meas_val["name"]
            meas = meas_val["meas"]
        else:
            # there is no value (e.g. only Q but no P) -> use default value and sigma
            value = 0.0
            sigma = self._converter_options.measurement_substitution.default_sigma_pq.get_sigma(
                nomv
            )
            is_default = True

        return value, sigma, name, meas, is_default

    def _get_median_value(self, arr: list[dict], key: str):
        arr.sort(key=lambda x: x[key])
        ll = len(arr)
        return arr[ll // 2]

    def _join_measurements_by_terminal(
        self, res_p, meas_by_term: dict, measurement_type: str
    ):
        for idx in range(res_p.shape[0]):
            term = res_p["term"][idx]
            val = meas_by_term.setdefault(term, {})
            self.set(val, "eq", res_p["eq"][idx])
            self.set(val, "tn", res_p["tn"][idx])
            self.set(val, "nomv", res_p["nomv"][idx])
            self.append(
                val,
                measurement_type,
                {
                    "name": res_p["name"][idx],
                    "meas": res_p["meas"][idx],
                    "value": res_p["value"][idx],
                    "sigma": res_p["sigma"][idx],
                },
            )

    def set(self, dic, key, val):
        old_val = dic.get(key)
        if old_val is None:
            dic[key] = val
        elif old_val != val:
            raise ValueError(f"Key {key} already set to {old_val}, cannot set to {val}")

    def append(self, dic, key, val):
        old_val = dic.get(key)
        if old_val is None:
            dic[key] = [val]
        else:
            dic[key].append(val)
