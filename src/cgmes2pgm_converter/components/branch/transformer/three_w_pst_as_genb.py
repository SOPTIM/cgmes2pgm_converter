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

from .abstract_transformer import AbstractTransformerBuilder
from .util.three_w_transformer_props import PstTransformerProps


class Pst3WAsGenericBranchBuilder(AbstractTransformerBuilder):

    def is_active(self):
        return self._converter_options.use_generic_branch[BranchType.THREE_WINDING_PST]

    def build_from_cgmes(self, _) -> tuple[np.ndarray, dict | None]:
        res = self._get_pst_result()

        # Convert kv to v, MVA to VA
        for col in ["ratedU1", "ratedU2", "ratedU3", "nomU1", "nomU2", "nomU3"]:
            res[col] = res[col] * 1e3

        for col in ["ratedS1", "ratedS2", "ratedS3"]:
            res[col] = res[col] * 1e6

        arr = initialize_array(
            self._data_type, self.component_name(), int(res.shape[0] * 3)
        )

        if res.shape[0] == 0:
            return arr, None

        props = PstTransformerProps(self.winding_count())

        for _, trafo in res.iterrows():

            u_node1 = trafo["nomU1"]
            u_node2 = trafo["nomU2"]
            u_node3 = trafo["nomU3"]

            u_node_aux = u_node1

            u_trafo1 = trafo["ratedU1"]
            u_trafo2 = trafo["ratedU2"]
            u_trafo3 = trafo["ratedU3"]

            u_trafo_aux = u_trafo1

            name1 = trafo["name1"] + "-w1"
            name2 = trafo["name2"] + "-w2"
            name3 = trafo["name3"] + "-w3"

            wid1 = self._id_mapping.add_cgmes_term_iri(
                trafo["tr1"], trafo["_term1"], name1
            )

            wid2 = self._id_mapping.add_cgmes_term_iri(
                trafo["tr2"], trafo["_term2"], name2
            )

            wid3 = self._id_mapping.add_cgmes_term_iri(
                trafo["tr3"], trafo["_term3"], name3
            )

            id_node1 = self._id_mapping.get_pgm_id(trafo["node1"])
            id_node2 = self._id_mapping.get_pgm_id(trafo["node2"])
            id_node3 = self._id_mapping.get_pgm_id(trafo["node3"])
            id_node_aux = self._id_mapping.get_pgm_id(trafo["tr1"])

            # W1
            props.append_base_props(
                wid1,
                id_node1,
                id_node_aux,
                trafo["connected1"],
                trafo["ratedS1"],
            )
            props.append_electric_props(
                trafo=trafo,
                winding=1,
                node_u1=u_node1,
                node_u2=u_node_aux,
                trafo_u1=u_trafo1,
                trafo_u2=u_trafo_aux,
            )
            props.add_extra_info(
                wid=wid1,
                name=name1,
                term1=trafo["_term1"],
                term2=trafo["tr1"],
            )

            # W2
            props.append_base_props(
                wid2,
                id_node_aux,
                id_node2,
                trafo["connected2"],
                trafo["ratedS2"],
            )
            props.append_electric_props(
                trafo=trafo,
                winding=2,
                node_u1=u_node_aux,
                node_u2=u_node2,
                trafo_u1=u_trafo_aux,
                trafo_u2=u_trafo2,
            )
            props.add_extra_info(
                wid=wid2,
                name=name2,
                term1=trafo["tr1"],
                term2=trafo["_term2"],
            )

            # W3
            props.append_base_props(
                wid3,
                id_node_aux,
                id_node3,
                trafo["connected3"],
                trafo["ratedS3"],
            )
            props.append_electric_props(
                trafo=trafo,
                winding=3,
                node_u1=u_node_aux,
                node_u2=u_node3,
                trafo_u1=u_trafo_aux,
                trafo_u2=u_trafo3,
            )
            props.add_extra_info(
                wid=wid3,
                name=name3,
                term1=trafo["tr1"],
                term2=trafo["_term3"],
            )

        arr["id"] = props.ids
        arr["from_node"] = props.from_node
        arr["to_node"] = props.to_node
        arr["from_status"] = props.from_status
        arr["to_status"] = props.to_status
        arr["sn"] = props.sn
        arr["r1"] = props.r
        arr["x1"] = props.x
        arr["g1"] = props.g
        arr["b1"] = props.b
        arr["k"] = props.k
        arr["theta"] = props.theta

        return arr, props.extra_info

    def component_name(self) -> ComponentType:
        return ComponentType.generic_branch

    def winding_count(self) -> int:
        return 3
