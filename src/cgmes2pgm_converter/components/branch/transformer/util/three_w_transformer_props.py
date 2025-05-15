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

from .pst_tapchanger_calculation import calc_theta_k_3w


class TransformerProps:
    """Property lists for all transformer windings"""

    def __init__(self, winding_count):
        self.winding_count = winding_count
        self.ids = []
        self.from_node = []
        self.to_node = []
        self.from_status = []
        self.to_status = []
        self.sn = []
        self.r = []
        self.x = []
        self.g = []
        self.b = []
        self.k = []
        self.theta = []
        self.extra_info = {}
        self._type = "PowerTransformer-" + str(winding_count) + "W"

    def append_base_props(
        self,
        wid: int,
        from_node: int,
        to_node: int,
        status: int,
        sn: float,
    ):
        self.ids.append(wid)
        self.from_node.append(from_node)
        self.to_node.append(to_node)
        self.from_status.append(status)
        self.to_status.append(status)
        self.sn.append(sn)

    def add_extra_info(
        self,
        wid: int,
        name: str,
        term1: str,
        term2: str,
    ):
        self.extra_info[wid] = {
            "_type": self._type,
            "_name": name,
            "_term1": term1,
            "_term2": term2,
        }

    def append_electric_props(
        self,
        trafo,
        winding,
        node_u1,
        node_u2,
        trafo_u1,
        trafo_u2,
    ):
        _r = trafo[f"r{winding}"]
        _x = trafo[f"x{winding}"]
        _g = trafo[f"g{winding}"]
        _b = trafo[f"b{winding}"]

        step = trafo[f"step{winding}"]
        if np.isnan(step):
            step = 0
            neutral_step = 0
            step_size_kv = 0

        else:
            neutral_step = trafo[f"neutralStep{winding}"]
            step_size = trafo[f"stepSize{winding}"]
            if winding == 1:
                step_size_kv = trafo_u1 * (step_size / 100)
            elif winding == 2:
                step_size_kv = trafo_u2 * (step_size / 100)
            else:
                step_size_kv = 0.0

        u1_corr = trafo_u1
        u2_corr = trafo_u2
        if winding == 1:
            u1_corr += (step - neutral_step) * step_size_kv
        elif winding == 2:
            u2_corr += (step - neutral_step) * step_size_kv

        nominal_ratio = node_u1 / node_u2

        _k = (u1_corr / u2_corr) / nominal_ratio

        self.r.append(_r)
        self.x.append(_x)
        self.g.append(_g)
        self.b.append(_b)
        self.k.append(_k)


class PstTransformerProps(TransformerProps):

    def __init__(self, winding_count):
        super().__init__(winding_count)
        self._type = "PST-" + str(winding_count) + "W"

    def append_electric_props(
        self,
        trafo,
        winding,
        node_u1,
        node_u2,
        trafo_u1,
        trafo_u2,
    ):
        _r = trafo[f"r{winding}"]
        _x = trafo[f"x{winding}"]
        _g = trafo[f"g{winding}"]
        _b = trafo[f"b{winding}"]

        tapside = 1 if isinstance(trafo["tapchanger1"], str) else 2
        _theta, _k = calc_theta_k_3w(trafo, winding, tapside)

        self.r.append(_r)
        self.x.append(_x)
        self.g.append(_g)
        self.b.append(_b)

        self.k.append(_k)
        self.theta.append(_theta)
