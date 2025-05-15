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

from .line import LineBuilder


class EquivalentBranchBuilder(LineBuilder):
    """
    ACLineSegments or EquivalentBranches that connect different voltage levels
    must be modeled as "generic_branch", as "line" can only handle the same
    voltage level on both nodes.

    ACLineSegments and EquivalentBranches that connect the same voltage level
    are handled in `LineBuilder`
    """

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:

        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?_tn1", "?_tn2"),
            "$NOMV_FILTER": "FILTER(?_nomv1 != ?_nomv2)",  # <- filter for different voltage levels
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        arr = initialize_array(self._data_type, self.component_name(), res.shape[0])
        arr["id"] = self._id_mapping.add_cgmes_iris(res["line"], res["name"])
        arr["from_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn1"]]
        arr["to_node"] = [self._id_mapping.get_pgm_id(uuid) for uuid in res["tn2"]]
        arr["from_status"] = res["status1"]
        arr["to_status"] = res["status2"]

        nomv1 = res["nomv1"]
        nomv2 = res["nomv2"]

        z_conv, y_conv = self._calc_conversion_factors(nomv1, nomv2)

        arr["r1"] = res["r"] * z_conv
        arr["x1"] = res["x"] * z_conv
        arr["g1"] = res["gch"] * y_conv
        arr["b1"] = res["bch"] * y_conv
        # arr["g1"] = 0
        # arr["b1"] = res["bch"]/ (np.maximum(nomv1, nomv2) ** 2) / y_conv

        arr["k"] = [self._compute_ratio(v1, v2) for v1, v2 in zip(nomv1, nomv2)]

        types = res["type"]
        extra_info = {}
        for idx in range(arr.shape[0]):
            extra_info[arr["id"][idx]] = {
                "_term1": res["term1"][idx],
                "_term2": res["term2"][idx],
                "_type": types[idx],
                "_name": res["name"][idx],
            }

        self._log_type_counts(extra_info)

        return arr, extra_info

    def _compute_ratio(self, v1, v2):
        maxv, minv = (v1, v2) if v1 > v2 else (v2, v1)
        if (maxv - minv) / maxv > 0.1:
            # if the difference is more than 10% we assume that the ratio is 1.0
            return 1.0
        return maxv / minv

    def _calc_conversion_factors(self, rated_u1, rated_u2):
        rated_u_max = np.maximum(rated_u1, rated_u2)
        rated_u_min = np.minimum(rated_u1, rated_u2)

        z_conv = (rated_u_min * rated_u_min) / (rated_u_max * rated_u_max)
        y_conv = 1 / z_conv
        return z_conv, y_conv

    def component_name(self) -> ComponentType:
        return ComponentType.generic_branch
