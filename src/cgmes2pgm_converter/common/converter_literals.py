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

from enum import StrEnum

COMPONENT_TYPE = "component_type"


class VoltageMeasType(StrEnum):
    """Enumeration for the voltage measurement types, created by the converter."""

    FIELD = "Field"
    """Actual voltage sensor from the CGMES dataset"""

    SUBSTITUTED_NOM_V = "Substituted_Nom_V"
    """Substituted measurement from nominal voltage"""

    def doc(self):
        return {
            VoltageMeasType.FIELD: "Actual voltage sensor from the CGMES dataset",
            VoltageMeasType.SUBSTITUTED_NOM_V: "Substituted measurement from nominal voltage",
        }[self]


class SymPowerType(StrEnum):
    """Enumeration for the power measurement types, created by the converter."""

    FIELD = "Field"
    """Actual power sensor from the CGMES dataset"""

    P_ZERO = "P_Zero"
    """Field Measurement for P not available, filled with 0"""

    P_FROM_SSH = "P_From_SSH"
    """Missing P value replaced with the SSH value"""

    P_FROM_BALANCE = "P_From_Balance"
    """Missing P value replaced with the balance value of node"""

    Q_ZERO = "Q_Zero"
    """Field Measurement for Q not available, filled with 0"""

    Q_FROM_SSH = "Q_From_SSH"
    """Missing Q value replaced with the SSH value"""

    Q_FROM_BALANCE = "Q_From_Balance"
    """Missing Q value replaced with the balance value of node"""

    MIRRORED = "Mirror"
    """Power sensor mirrored from the other side of the branch"""

    ZERO = "Zero"
    """Substituted measurement (P, Q = 0) for branches/appliances without any power-measurement"""

    SPLIT = "SPLIT"
    """Duplicated measurement for a split branch that was replaced by a source"""

    PASSIVE = "Passive"
    """Substituted measurement (P, Q = 0) for passive nodes"""

    SSH = "SSH"
    """Substituted measurement from SSH-Profile"""

    def doc(self):
        return {
            SymPowerType.FIELD: "Actual power sensor from the CGMES dataset",
            SymPowerType.P_ZERO: "Field Measurement for P not available, filled with 0",
            SymPowerType.P_FROM_SSH: "Missing P value replaced with the SSH value",
            SymPowerType.P_FROM_BALANCE: "Missing P value replaced with the balance value of node",
            SymPowerType.Q_ZERO: "Field Measurement for Q not available, filled with 0",
            SymPowerType.Q_FROM_SSH: "Missing Q value replaces with the SSH value",
            SymPowerType.Q_FROM_BALANCE: "Missing Q value replaced with the balance value of node",
            SymPowerType.MIRRORED: "Power sensor mirrored from the other side of the branch",
            SymPowerType.ZERO: "Meas. (P, Q = 0) for branches/appliances without any power-measurement",
            SymPowerType.SPLIT: "Duplicated measurement for a split branch replaced by a source",
            SymPowerType.PASSIVE: "Substituted measurement (P, Q = 0) for passive nodes",
            SymPowerType.SSH: "Substituted measurement from SSH-Profile",
        }[self]

    @staticmethod
    def just_p_replaced() -> set["SymPowerType"]:
        """Returns a set of SymPowerType values where P is a substituted measurement."""
        return {
            SymPowerType.P_ZERO,
            SymPowerType.P_FROM_SSH,
            SymPowerType.P_FROM_BALANCE,
        }

    @staticmethod
    def just_q_replaced() -> set["SymPowerType"]:
        """Returns a set of SymPowerType values where Q is a substituted measurement."""
        return {
            SymPowerType.Q_ZERO,
            SymPowerType.Q_FROM_SSH,
            SymPowerType.Q_FROM_BALANCE,
        }

    @staticmethod
    def p_and_q_replaced() -> set["SymPowerType"]:
        """Returns a set of SymPowerType values where both P and Q are substituted measurements."""
        return {
            SymPowerType.MIRRORED,
            SymPowerType.ZERO,
            SymPowerType.SPLIT,
            SymPowerType.PASSIVE,
            SymPowerType.SSH,
        }


class NodeType(StrEnum):

    AUX_NODE = "Branch3-AuxiliaryNode"
    """Auxiliary node for branches with 3 terminals (e.g. 3W-Transformer)"""
