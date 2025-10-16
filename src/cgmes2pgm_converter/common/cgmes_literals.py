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

from enum import Enum, auto

from strenum import StrEnum

CIM_ID_OBJ = "cim:IdentifiedObject"
CIM_MEAS = "cim:Measurement"


def phase_tap_changer_types(cim_namespace: str):
    """Return a list of all phase tap changer types."""
    return [
        f"{cim_namespace}PhaseTapChanger",
        f"{cim_namespace}PhaseTapChangerTabular",
        f"{cim_namespace}PhaseTapChangerLinear",
        f"{cim_namespace}PhaseTapChangerNonLinear",
        f"{cim_namespace}PhaseTapChangerAsymmetrical",
        f"{cim_namespace}PhaseTapChangerSymmetrical",
    ]


class Profile(StrEnum):
    """Enumeration for the CGMES-profile types."""

    EQ = auto()
    """Equipment profile"""

    SSH = auto()
    """Steady state hypothesis profile"""

    TP = auto()
    """Topology profile"""

    OP = auto()
    """Operational profile"""

    SV = auto()
    """State estimation profile"""

    MEAS = auto()
    """Measurement profile"""

    UNKNOWN = auto()
    """Unknown profile"""

    @staticmethod
    def parse(profile_str: str) -> "Profile":
        if (
            "EquipmentBoundary/" in profile_str
            or "EquipmentBoundary-EU" in profile_str
            or "BoundaryEquipment" in profile_str
        ):
            # no EQ_BD, boundary equipment is just equipment for the EU/ENTSO-E modeling authority set
            return Profile.EQ
        elif "TopologyBoundary" in profile_str or "BoundaryTopology" in profile_str:
            # no TP_BD, boundary topology is just topology for the EU/ENTSO-E modeling authority set
            return Profile.TP
        elif "CoreEquipment" in profile_str or "EquipmentCore" in profile_str:
            return Profile.EQ
        elif "Topology" in profile_str:
            return Profile.TP
        elif "Operation/4.0" in profile_str:
            return Profile.OP
        elif "OperationMeas/4.0" in profile_str:
            return Profile.MEAS
        elif "SteadyStateHypothesis" in profile_str:
            return Profile.SSH
        elif "StateVariables" in profile_str:
            return Profile.SV
        else:
            return Profile.UNKNOWN


class MeasurementValueSource(StrEnum):
    """Enumeration for the measurement value sources."""

    SCADA = auto()
    ICCP = auto()


def convert_unit_multiplier(multiplier, cim_namespace: str) -> float:
    """Returns the factor for the given unit multiplier."""
    prefix = f"{cim_namespace}UnitMultiplier."

    if not multiplier.startswith(prefix):
        raise ValueError(f"Invalid unit multiplier: {multiplier}")

    multiplier_key = multiplier[len(prefix) :]

    multiplier_dict = {
        "y": 1e-24,
        "z": 1e-21,
        "a": 1e-18,
        "f": 1e-15,
        "p": 1e-12,
        "n": 1e-9,
        "micro": 1e-6,
        "m": 1e-3,
        "c": 1e-2,
        "d": 1e-1,
        "none": 1e0,
        "da": 1e1,
        "h": 1e2,
        "k": 1e3,
        "M": 1e6,
        "G": 1e9,
        "T": 1e12,
        "P": 1e15,
        "E": 1e18,
        "Z": 1e21,
        "Y": 1e24,
    }

    if multiplier_key not in multiplier_dict:
        raise ValueError(f"Unknown unit multiplier: {multiplier_key}")
    return multiplier_dict[multiplier_key]
