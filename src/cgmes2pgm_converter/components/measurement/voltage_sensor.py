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
from power_grid_model import ComponentType, initialize_array

from cgmes2pgm_converter.common import (
    AbstractCgmesIdMapping,
    CgmesDataset,
    Profile,
    VoltageMeasType,
)

from ..component import AbstractPgmComponentBuilder


class SymVoltageBuilder(AbstractPgmComponentBuilder):

    _query_meas_in_graph = """
        SELECT ?eq ?tn ?term ?max_u ?min_u ?u ?nom_u ?acc_u ?sigma_u ?name ?meas_u
        WHERE {
            GRAPH ?g_v {
                ?meas_u cim:Measurement.measurementType ?type_u;
                        cim:IdentifiedObject.name ?name;
                        cim:Measurement.PowerSystemResource ?eq;
                        cim:Analog.maxValue ?max_u;
                        cim:Analog.minValue ?min_u;
                        cim:Measurement.Terminal ?term.

                ?measVal_v cim:AnalogValue.Analog ?meas_u;
                OPTIONAL { ?measVal_v cim:MeasurementValue.sensorAccuracy ?acc_u. }
                OPTIONAL { ?measVal_v cim:MeasurementValue.sensorSigma ?sigma_u. }

            }
            FILTER(?type_u = "Voltage")

            ?term cim:Terminal.TopologicalNode ?tn.

            GRAPH ?g_v_val {
                ?measVal_v cim:AnalogValue.value ?u.
            }

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nom_u.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?tn
        }
        ORDER BY ?tn
    """

    _query_meas_in_default = """
        SELECT ?eq ?tn ?term ?u ?sigma_u ?name ?meas_u ?nom_u
        WHERE {
            ?meas_u cim:Measurement.measurementType "LineToLineVoltage";
                  cim:IdentifiedObject.name ?name;
                  cim:Measurement.PowerSystemResource ?eq;
                  cim:Measurement.Terminal ?term.


            ?_measVal_scada cim:AnalogValue.Analog ?meas_u;
                            cim:MeasurementValue.MeasurementValueSource/cim:IdentifiedObject.name "SCADA";
                            cim:AnalogValue.value ?u.

            OPTIONAL {
                ?_measVal_est cim:AnalogValue.Analog ?meas_u;
                              cim:MeasurementValue.sensorAccuracy ?sigma_u.
            }

            ?term cim:Terminal.TopologicalNode ?tn;
                  cim:Terminal.ConductingEquipment ?eq.

            ?tn cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nom_u.

            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?tn
        }
        ORDER BY ?tn
    """

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, data_type)
        self._use_nominal_voltages = (
            self._converter_options.measurement_substitution.use_nominal_voltages
        )

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        if Profile.OP in self._source.graphs:
            res = self._read_meas_from_graph()
        else:
            res = self._read_meas_from_default_graph()

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])

        arr["id"] = self._id_mapping.add_cgmes_iris(res["meas_u"], res["name"])
        arr["measured_object"] = [self._id_mapping.get_pgm_id(tn) for tn in res["tn"]]

        zero_voltages = res["u"] < 0.1
        if any(zero_voltages):
            logging.warning(
                "Voltage measurements with values below 0.1 kV detected. Replacing with nominal voltage."
            )
            res["u"] = res["u"].mask(zero_voltages, res["nom_u"])

            for node, nom_v in zip(res["tn"][zero_voltages], res["u"][zero_voltages]):
                node_name = self._id_mapping.get_name_from_cgmes(node)
                logging.debug(
                    "\tVoltage measurement for node `%s` with replaced with nominal voltage %f.",
                    node_name,
                    nom_v,
                )

        arr["u_measured"] = res["u"] * 1e3
        arr["u_sigma"] = res["sigma_u"] * 1e3

        extra_info = self._create_extra_info_with_types(arr, res["meas_type"])

        self._log_type_counts(extra_info)

        return arr, extra_info

    def _read_meas_from_graph(self):
        args = {"$TOPO_ISLAND": self._at_topo_island_node("?tn")}
        q = self._replace(self._query_meas_in_graph, args)
        res = self._source.query(q)
        res["meas_type"] = VoltageMeasType.FIELD
        return res

    def _read_meas_from_default_graph(self):
        args = {"$TOPO_ISLAND": self._at_topo_island_node("?tn")}
        q = self._replace(self._query_meas_in_default, args)
        res = self._source.query(q)

        meas_by_tn = self._join_measurements_by_node(res)

        tn = []
        u = []
        u_sigma = []
        u_meas = []
        u_name = []
        meas_type = []

        # get one u-measurement per node for the potentially many available
        for key, val in meas_by_tn.items():
            meas_u = val.get("meas_u")

            u_m, u_s, u_n, u_mm, u_type = self._get_one_measurement_and_sigma(
                meas_u, val["nom_u"]
            )

            if u_m == 0:
                continue

            tn.append(key)
            u.append(u_m)
            u_sigma.append(u_s)
            u_name.append(u_n)
            u_meas.append(u_mm)
            meas_type.append(u_type)

        res_data = {
            "tn": tn,
            "u": u,
            "meas_u": u_meas,
            "name": u_name,
            "sigma_u": u_sigma,
            "meas_type": meas_type,
        }
        res = pd.DataFrame(res_data)
        return res

    def _join_measurements_by_node(self, res):
        meas_by_tn = {}
        for idx in range(res.shape[0]):
            term = res["tn"][idx]
            val = meas_by_tn.setdefault(term, {})
            self.set(val, "nom_u", res["nom_u"][idx])
            self.append(
                val,
                "meas_u",
                {
                    "name": res["name"][idx],
                    "meas_u": res["meas_u"][idx],
                    "u": res["u"][idx],
                    "sigma_u": res["sigma_u"][idx],
                },
            )
        return meas_by_tn

    def _get_one_measurement_and_sigma(self, meas_u, nom_u) -> tuple[
        float | None,
        float | None,
        str | None,
        str | None,
        float | None,
        VoltageMeasType,
    ]:
        has_sigma = (
            any(not np.isnan(m["sigma_u"]) for m in meas_u)
            if meas_u is not None
            else False
        )
        has_value = (
            any(not np.isnan(m["u"]) for m in meas_u) if meas_u is not None else False
        )

        value = 0.0
        sigma = 0.0
        name = None
        meas = None
        meas_type = VoltageMeasType.FIELD

        if has_sigma and has_value:
            # remove measurements that have no sigma
            meas_filtered = [v for v in meas_u if not np.isnan(v["sigma_u"])]

            # get median value if the available measurements
            meas_val = self._get_median_value(meas_filtered, "u")

            value = meas_val["u"]
            sigma = meas_val["sigma_u"]

            name = meas_val["name"]
            meas = meas_val["meas_u"]
        elif has_value:
            # there is no sigma -> get median value and use default sigma
            meas_val = self._get_median_value(meas_u, "u")

            value = meas_val["u"]
            _, sigma = self._use_nominal_voltages.map_kv(nom_u)

            name = meas_val["name"]
            meas = meas_val["meas_u"]

        if value == 0.0:
            # 0 kV is invalid for PGM, derive measurement from nominal voltage
            value, sigma = self._use_nominal_voltages.map_kv(nom_u)
            meas_type = VoltageMeasType.SUBSTITUTED_NOM_V

        return value, sigma, name, meas, meas_type

    def _get_median_value(self, arr: list[dict], key: str):
        arr.sort(key=lambda x: x[key])
        ll = len(arr)
        return arr[ll // 2]

    def component_name(self) -> ComponentType:
        return ComponentType.sym_voltage_sensor

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
