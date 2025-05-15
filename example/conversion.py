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

from power_grid_model_io.converters.pgm_json_converter import PgmJsonConverter

from cgmes2pgm_converter import CgmesDataset, CgmesToPgmConverter, ConverterOptions
from cgmes2pgm_converter.common import Profile

BASE_URL = "http://localhost:3030/dataset_name"

dataset = CgmesDataset(
    base_url=BASE_URL,
    # cim_namespace="http://iec.ch/TC57/2013/CIM-schema-cim16#",
    cim_namespace="http://iec.ch/TC57/CIM100#",
    graphs={  # Generated using measurement simulation from cgmes2pgm_suite
        Profile.OP: BASE_URL + "/op",
        Profile.MEAS: BASE_URL + "/meas",
    },
)
options = ConverterOptions(
    only_topo_island=False,
    topo_island_name=None,
)

converter = CgmesToPgmConverter(datasource=dataset, options=options)
input_data, extra_info = converter.convert()

converter = PgmJsonConverter(destination_file="../out/input.json")
converter.save(input_data, extra_info)
