# Copyright [2024] [SOPTIM AG]
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
from power_grid_model.enum import LoadGenType
from power_grid_model_io.data_types import ExtraInfo

from cgmes2pgm_converter.common import (
    AbstractCgmesIdMapping,
    CgmesDataset,
    ConverterOptions,
    Topology,
)

from ..component import AbstractPgmComponentBuilder


class NetworkSplitter(AbstractPgmComponentBuilder):
    """Class identifies lines that connect different substations and disables them.

    The list of lines can be adjusted by the configuration to include only
    certain lines or only those that connect certain substations. The disabling
    is done by setting the status of the line to 0 and additionally creating
    `source` objects at the nodes of the line, that are supposed to take the
    p/q flow measurements of the line.

    The measurements are duplicated and attached to the line again
    in the class `SymPowerBuilder`. This way, the sources can be disabled
    and the line can be enabled again, and the p/q flow
    remains the same in the network.
    """

    SPLITTABLE_TYPES = {ComponentType.line, ComponentType.generic_branch}

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        converter_options: ConverterOptions,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, converter_options, data_type)

        self.enable = converter_options.network_splitting.enable
        self._cut_branches = (
            set(converter_options.network_splitting.cut_branches)
            if converter_options.network_splitting.cut_branches is not None
            else set()
        )
        self._cut_substations = (
            set(converter_options.network_splitting.cut_substations)
            if converter_options.network_splitting.cut_substations is not None
            else set()
        )

    def component_name(self) -> ComponentType:
        return (
            ComponentType.source
            if self._converter_options.network_splitting.add_sources
            else ComponentType.sym_gen
        )

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:
        if not self.enable:
            arr = initialize_array(self._data_type, self.component_name(), 0)
            return arr, {}

        topo = Topology(input_data, self._extra_info)
        # get branches from topology
        all_branches = [
            self._filter_branch(branch)
            for branch in topo.get_topology().values()
            if self._filter_branch(branch) is not None
        ]

        # filter branches that connect different substations
        sub_branches = [
            br
            for br in all_branches
            if self._filter_between_substation_branch2(br, topo)
        ]

        # disable branches that connect different substations
        for br in sub_branches:
            if br is not None:
                br["from_status"] = 0
                br["to_status"] = 0

        extra_info: ExtraInfo = {}
        arr = self._convert_to_sources(sub_branches, topo, extra_info)
        return arr, extra_info

    def _filter_branch(self, branch):
        for t in self.SPLITTABLE_TYPES:
            if branch.get(t) is not None:
                return branch.get(t)
        return None

    def _filter_between_substation_branch2(self, br, topo) -> bool:
        from_node = topo.get_topology()[br["from_node"]]
        to_node = topo.get_topology()[br["to_node"]]

        topo_branch = topo.get_topology()[br["id"]]
        branch_name = str(topo_branch["_extra"]["_name"]).strip()

        from_status = br["from_status"]
        to_status = br["to_status"]

        substation1 = from_node["_extra"]["_substationMrid"]
        substation2 = to_node["_extra"]["_substationMrid"]

        substation_name1 = from_node["_extra"]["_substation"]
        substation_name2 = to_node["_extra"]["_substation"]

        return (len(self._cut_branches) > 0 and branch_name in self._cut_branches) or (
            # is string -> keep nodes without substation connected
            isinstance(substation1, str)
            and isinstance(substation2, str)
            and substation1 != substation2
            and (
                (
                    len(self._cut_substations) > 0
                    # cut the branch that connects an included substation
                    # with a substation that shall be excluded
                    and (
                        substation_name1 in self._cut_substations
                        and substation_name2 not in self._cut_substations
                    )
                    or (
                        substation_name1 not in self._cut_substations
                        and substation_name2 in self._cut_substations
                    )
                )
                # all branches if no explicit filter is defined
                or (len(self._cut_substations) == 0 and len(self._cut_branches) == 0)
            )
            and from_status == 1
            and to_status == 1
        )

    def _convert_to_sources(self, branches, topo, extra_info):
        arr = initialize_array(
            self._data_type, self.component_name(), len(branches) * 2
        )

        # create PGM Ids from equipment and terminal IRIs
        ids = []
        nodes = []

        for eq in branches:
            brid = eq["id"]
            eq_iri = self._id_mapping.get_cgmes_iri(brid)
            topo_branch = topo.get_topology()[brid]
            name = self._id_mapping.get_name_from_pgm(brid)
            for term_idx in range(2):
                term_num = str(term_idx + 1)
                term_iri = topo_branch["_extra"][f"_term{term_num}"]
                # create a pgm id depending on the transformer iri AND the transformer end iri
                src_id = self._id_mapping.add_cgmes_term_iri(
                    eq_iri, term_iri, f"{name}-{term_num}"
                )
                ids.append(src_id)
                topo_branch["_extra"][f"source{term_num}"] = src_id

                node_iri = "from_node" if term_idx == 0 else "to_node"
                node_id = eq[node_iri]
                nodes.append(node_id)

                extra_info[src_id] = {
                    "_type": "SubstationLineAsSource",
                    "branch": brid,
                }

        arr["id"] = ids
        arr["node"] = nodes
        arr["status"] = 1

        if self.component_name() == ComponentType.source:
            arr["u_ref"] = 1
            arr["sk"] = 1e40
            arr["rx_ratio"] = 0.1
            arr["z01_ratio"] = 1
        elif self.component_name() == ComponentType.sym_gen:
            arr["p_specified"] = 0
            arr["q_specified"] = 0
            arr["type"] = LoadGenType.const_power
        else:
            raise ValueError(f"Unsupported component name {self.component_name()}")

        return arr
