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

from cgmes2pgm_converter.common import BranchType

from .abstract_two_2_transformer import Abstract2WTransformerBuilder
from .util.pst_tapchanger_calculation import calc_theta_k_2w


class Pst2WAsGenericBranchBuilder(Abstract2WTransformerBuilder):

    def is_active(self):
        return self._converter_options.use_generic_branch[BranchType.PST]

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        res = self._get_pst_result()

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

        z_conv, y_conv = self.calc_conversion_factors(rated_u1, rated_u2)
        arr["r1"] = r * z_conv
        arr["x1"] = x * z_conv
        arr["g1"] = g * y_conv
        arr["b1"] = b * y_conv

        theta = []
        k = []
        for idx, trafo in res.iterrows():
            tapside = 1 if isinstance(trafo["tapchanger1"], str) else 2
            theta_, k_ = calc_theta_k_2w(trafo, tapside)

            theta.append(theta_)
            k.append(k_)

        arr["k"] = k
        arr["theta"] = theta

        # add r,x, ... to extra_info
        extra_info = {}
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_r": r[idx],
                "_x": x[idx],
                "_g": b[idx],
                "_b": b[idx],
                "_sn": arr["sn"][idx],
                "_type": "PST-" + str(self.winding_count()) + "W",
                "_name": res["name1"][idx],
                "_term1": res["_term1"][idx],
                "_term2": res["_term2"][idx],
            }

        self._log_type_counts(extra_info)

        return arr, extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.generic_branch

    def calc_conversion_factors(self, rated_u1, rated_u2):
        rated_u_max = np.maximum(rated_u1, rated_u2)
        rated_u_min = np.minimum(rated_u1, rated_u2)

        z_conv = (rated_u_min * rated_u_min) / (rated_u_max * rated_u_max)
        y_conv = 1 / z_conv
        return z_conv, y_conv
