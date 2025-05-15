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

from cgmes2pgm_converter.common import BranchType, phase_tap_changer_types

from .abstract_two_2_transformer import Abstract2WTransformerBuilder


class Transformer2WAsGenericBranchBuilder(Abstract2WTransformerBuilder):

    def is_active(self):
        return self._converter_options.use_generic_branch[BranchType.TRANSFORMER]

    def component_name(self) -> ComponentType:
        return ComponentType.generic_branch

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        res = self._get_query_result()

        # Remove phase shifters
        idx_phase_shifter = np.isin(
            res["taptype1"], phase_tap_changer_types(self._source.cim_namespace)
        ) | np.isin(
            res["taptype2"], phase_tap_changer_types(self._source.cim_namespace)
        )
        res = res[~idx_phase_shifter]
        res = res.reset_index(drop=True)  # Required for right shape in initialize_array

        self._validate_transformer_data(res)

        arr = initialize_array(
            self._data_type, self.component_name(), int(res.shape[0])
        )

        if res.shape[0] == 0:
            return arr, None

        arr["id"] = self._id_mapping.add_cgmes_iris(res["tr1"], res["name1"])
        arr["from_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["node1"]]
        arr["to_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["node2"]]
        arr["from_status"] = res["connected1"]
        arr["to_status"] = res["connected2"]

        arr["sn"] = np.maximum(res["ratedS1"].fillna(0), res["ratedS2"].fillna(0)) * 1e6

        r = np.where(res["r1"] == 0, res["r2"], res["r1"])
        x = np.where(res["x1"] == 0, res["x2"], res["x1"])
        g = np.where(res["g1"] == 0, res["g2"], res["g1"])
        b = np.where(res["b1"] == 0, res["b2"], res["b1"])

        rated_u1 = res["ratedU1"]
        rated_u2 = res["ratedU2"]

        z_conv, y_conv = self._calc_conversion_factors(rated_u1, rated_u2)
        arr["r1"] = r * z_conv
        arr["x1"] = x * z_conv
        arr["g1"] = g * y_conv
        arr["b1"] = b * y_conv

        arr["k"] = [
            self._calc_ratio(
                trafo["ratedU1"],
                trafo["ratedU2"],
                trafo["nomU1"],
                trafo["nomU2"],
                trafo,
            )
            for _, trafo in res.iterrows()
        ]
        arr["theta"] = 0.0

        # add r,x, ... to extra_info
        extra_info = {}
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_r": r[idx],
                "_x": x[idx],
                "_g": g[idx],
                "_b": b[idx],
                "_sn": arr["sn"][idx],
                "_type": "PowerTransformer-" + str(self.winding_count()) + "W",
                "_name": res["name1"][idx],
                "_term1": res["_term1"][idx],
                "_term2": res["_term2"][idx],
            }

        self._log_type_counts(extra_info)

        return arr, extra_info

    def _calc_ratio(self, rated_u1, rated_u2, nom_u1, nom_u2, trafo):
        """Calculate the ratio (k) for the transformer."""

        nominal_ratio_ = nom_u1 / nom_u2

        side = self._get_tap_changer_side(trafo)
        if side == -1:
            k = self._calc_rated_ratio(rated_u1, rated_u2, nominal_ratio_)
        else:
            k = self._calc_ratio_from_tap_changer(
                side, rated_u1, rated_u2, nominal_ratio_, trafo
            )

        return k

    def _get_tap_changer_side(self, trafo):
        step_1_ = trafo["step1"]
        step_2_ = trafo["step2"]

        side = -1
        if not np.isnan(step_1_) and not np.isnan(step_2_):
            logging.warning(
                "Transformer %s has steps on both sides. Choosing side 1.",
                trafo["name1"],
            )
            side = 1
        elif not np.isnan(step_1_):
            side = 1
        elif not np.isnan(step_2_):
            side = 2

        return side

    def _calc_ratio_from_tap_changer(
        self,
        end,
        rated_u1,
        rated_u2,
        nominal_ratio,
        trafo,
    ) -> float:
        """
        Calculate the ratio (k) for the transformer based on the tap changer.
        """
        ratio = trafo[f"_tratio{end}"]
        if np.isnan(ratio):
            k = self._calc_ratio_from_step(
                end, rated_u1, rated_u2, nominal_ratio, trafo
            )
        else:
            k = self._calc_ratio_from_table(
                end,
                rated_u1,
                rated_u2,
                nominal_ratio,
                ratio,
            )

        return k

    def _calc_ratio_from_step(
        self,
        end,
        rated_u1,
        rated_u2,
        nominal_ratio,
        trafo,
    ):
        step_ = trafo[f"step{end}"]
        step_neutral_ = trafo[f"neutralStep{end}"]
        step_size_ = trafo[f"stepSize{end}"]
        if end == 1:
            step_size_kv = rated_u1 * (step_size_ / 100)
        elif end == 2:
            step_size_kv = rated_u2 * (step_size_ / 100)
        else:
            step_size_kv = 0.0

        corr_u_tc = (step_ - step_neutral_) * step_size_kv
        corr_u_tc = 0.0 if np.isnan(corr_u_tc) else corr_u_tc

        corr_u1 = rated_u1
        corr_u2 = rated_u2
        if end == 1:
            corr_u1 += corr_u_tc
        elif end == 2:
            corr_u2 += corr_u_tc

        return self._calc_rated_ratio(corr_u1, corr_u2, nominal_ratio)

    def _calc_ratio_from_table(self, end, rated_u1, rated_u2, nominal_ratio, ratio):
        corr_u1 = rated_u1
        corr_u2 = rated_u2
        if end == 1:
            corr_u1 *= ratio
        elif end == 2:
            corr_u2 *= ratio
        else:
            raise ValueError("end must be 1 or 2")
        return self._calc_rated_ratio(corr_u1, corr_u2, nominal_ratio)

    def _calc_rated_ratio(self, rated_u1, rated_u2, nominal_ratio):
        return (rated_u1 / rated_u2) / nominal_ratio

    def _calc_conversion_factors(self, rated_u1, rated_u2):
        rated_u_max = np.maximum(rated_u1, rated_u2)
        rated_u_min = np.minimum(rated_u1, rated_u2)

        z_conv = (rated_u_min * rated_u_min) / (rated_u_max * rated_u_max)
        y_conv = 1 / z_conv
        return z_conv, y_conv
