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


class Marker:
    def __init__(self, node_id: int):
        self.id: int = node_id
        self.island_size = 1
        self.island_marker: Marker | None = None

    def get_island_marker(self):
        if self.island_marker is None:
            return self

        while self.island_marker.island_marker is not None:
            self.island_marker = self.island_marker.island_marker
        return self.island_marker

    def merge_marker(self, other: "Marker"):
        """Merge subnet of other marker into subnet of this marker.
        Nodes from the other subnet will (transitively) point to this marker
        and therefore have the same subnet id.
        """
        this_island_marker = self.get_island_marker()
        other_island_marker = other.get_island_marker()
        if other_island_marker != this_island_marker:
            this_island_marker.island_size += other_island_marker.island_size
            other_island_marker.island_size = -1
            other_island_marker.island_marker = this_island_marker

    @staticmethod
    def merge_marker2(left_marker: "Marker", right_marker: "Marker"):
        """Merge two markers / subnets ordered by their id, i.e. marker
        with the larger id will be merged into the marker with the smaller id.
        """
        left_id = left_marker.get_island_marker().id
        right_id = right_marker.get_island_marker().id
        if left_id < right_id:
            left_marker.merge_marker(right_marker)
        elif left_id > right_id:
            right_marker.merge_marker(left_marker)


class TopologySubnets:

    # node_id -> Marker
    def __init__(self):
        self._marker_dict: dict[int, Marker] = {}

    def get_marker(self) -> dict[int, Marker]:
        return self._marker_dict

    def get_subnets(self) -> dict[int, str]:
        subnets = [
            sub for sub in self._marker_dict.values() if sub.island_marker is None
        ]

        # sort subnets by size (descending) and id (ascending)
        subnets = sorted(subnets, key=lambda x: (-x.island_size, x.id))

        subnet_names: dict[int, str] = {}
        subnet_count = 1
        for subnet in subnets:
            if subnet_names.get(subnet.id) is None:
                subnet_names[subnet.id] = f"subnet_{subnet_count}"
                subnet_count += 1

        return subnet_names

    def eval_branch2(self, branch2):
        left_status = branch2["from_status"]
        right_status = branch2["to_status"]

        if left_status and right_status:
            left_node = branch2["from_node"]
            right_node = branch2["to_node"]
            self._eval_branch(left_node, right_node)

    def eval_branch3(self, branch3):
        status1 = branch3["status_1"]
        status2 = branch3["status_2"]
        status3 = branch3["status_2"]
        node1 = branch3["node_1"]
        node2 = branch3["node_2"]
        node3 = branch3["node_3"]

        if status1 and status2:
            self._eval_branch(node1, node2)
        if status1 and status3:
            self._eval_branch(node1, node3)
        if status2 and status3:
            self._eval_branch(node2, node3)

    def _eval_branch(self, left_node: int, right_node: int):
        left_marker = self._get_marker(left_node)
        right_marker = self._get_marker(right_node)

        Marker.merge_marker2(left_marker, right_marker)

    def _get_marker(self, node_id: int) -> Marker:
        marker = self._marker_dict.get(node_id)
        if marker is None:
            marker = self._marker_dict[node_id] = Marker(node_id)
        return marker
