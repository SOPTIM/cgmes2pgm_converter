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

from dataclasses import dataclass, field
from typing import Literal

from power_grid_model import ComponentType


@dataclass
class DefaultSigma:
    """Sets the sigma for PQ measurements, if sigma is missing.

    Attributes:
        sigma (float): The default sigma value.
        discrete (dict[float, float]): A default sigma value per voltage level.
            Dictionary mapping a Voltage (kV) to a sigma value (MW).
    """

    sigma: float = 10.0
    discrete: dict[float, float] = field(
        default_factory=lambda: {380.0: 30.0, 220.0: 20.0}
    )

    def get_sigma(self, voltage_level: float) -> float:
        """Get the sigma value for a given voltage level."""
        return self.discrete.get(voltage_level, self.sigma)


@dataclass
class SshSubstitutionOptions:
    """
    Generate measurements for generators and loads
    without an existing power measurement using SSH values.

    Attributes:
        enable (bool): Whether to use SSH values for substitution.
        sigma (float): The default sigma value for the substituted measurements (MW).
    """

    enable: bool = False
    sigma: float = 20 * 1e6


@dataclass
class UMeasurementSubstitutionOptions:
    """
    Options to generate voltage measurements based on the voltage level of a node.
    The measured value is calculated as: u_meas = nominal_voltage * nomv_to_measv_factor

    Attributes:
        enable (bool): Whether to use nominal voltage levels for substitution.
        sigma (float): The default sigma value for the substituted measurements (kV).
        nomv_to_measv_factor (float): Measured values are multiplied by this factor.
        discrete_meas (dict[float, float]): A default measurement value per voltage level.
            Dictionary mapping a Voltage (kV) to a measurement value (kV).
        discrete_sigma (dict[float, float]): A default sigma value per voltage level.
            Dictionary mapping a Voltage (kV) to a sigma value (kV).
    """

    enable: bool = False
    sigma: float = 100
    nomv_to_measv_factor: float = 1.05
    discrete_meas: dict[float, float] = field(
        default_factory=lambda: {380.0: 410.0, 220.0: 231.0}
    )
    discrete_sigma: dict[float, float] = field(default_factory=dict)

    def map_v(self, nominal_voltage_v: float) -> tuple[float, float]:
        meas_kv, sigma_kv = self.map_kv(nominal_voltage_v / 1e3)
        return meas_kv * 1e3, sigma_kv * 1e3

    def map_kv(self, nominal_voltage_kv: float) -> tuple[float, float]:
        discrete_sigma = self.discrete_sigma.get(nominal_voltage_kv, self.sigma)
        discrete_meas = self.discrete_meas.get(nominal_voltage_kv, None)

        if discrete_meas:
            return discrete_meas, discrete_sigma

        return (
            nominal_voltage_kv * self.nomv_to_measv_factor,
            discrete_sigma,
        )


@dataclass
class PassiveNodeOptions:
    """Options to create loads at passive nodes (nodes without any appliance).
    These loads are create with power-measurements with P=Q=0.

    Attributes:
        enable (bool): Whether to create loads at passive nodes.
        sigma (float): The sigma value for the substituted measurements (MW).
        appliance_type (ComponentType): The type of appliance to create.
            Can be either sym_gen or sym_load.
    """

    enable: bool = False
    sigma: float = 30
    appliance_type: Literal[ComponentType.sym_gen, ComponentType.sym_load] = (
        ComponentType.sym_gen
    )

    @staticmethod
    def _get_appliance_type(passive_node_enable, appliance):
        if passive_node_enable:
            if appliance is None:
                raise ValueError(
                    "If passive nodes are enabled, the appliance type must be specified."
                )
            if appliance not in [ComponentType.sym_gen, ComponentType.sym_load]:
                raise ValueError(
                    "The appliance type must be either 'sym_gen' or 'sym_load'."
                )
        return appliance


@dataclass
class QFromIOptions:
    """Options to create a Q measurement from the I measurement at a shunt.

    Attributes:
        enable (bool): Whether to create a Q measurement from the I measurement.
        sigma (float): The sigma value for the substituted measurements (MW).
    """

    enable: bool = False
    sigma: float = 20


@dataclass
class MeasSub:
    enable: bool = False
    sigma: float = 20
    sigma_factor: float = 1.0

    def __copy__(self):
        return MeasSub(self.enable, self.sigma, self.sigma_factor)


@dataclass
class BranchMeasurements:
    mirror: MeasSub = field(default_factory=MeasSub)
    zero_cut_branch: MeasSub = field(default_factory=MeasSub)
    zero_cut_source: MeasSub = field(default_factory=MeasSub)


@dataclass
class IncompleteMeasurements:
    use_ssh: MeasSub = field(default_factory=MeasSub)
    use_balance: MeasSub = field(default_factory=MeasSub)


@dataclass
class MeasurementSubstitutionOptions:
    """
    Options for creating additional measurements for state estimation.

    Attributes:
        default_sigma_pq (DefaultSigma):
            Default sigma for PQ measurements if sigma is missing.
        use_ssh (SshSubstitutionOptions):
            Options for using SSH values for substitution.
        use_nominal_voltages (UMeasurementSubstitutionOptions):
            Options for using nominal voltages for substitution.
        passive_nodes (PassiveNodeOptions):
            Options for creating loads at passive nodes.
        imeas_used_for_qcalc (QFromIOptions):
            Options for creating Q measurements from I measurements.
        branch_measurements (BranchMeasurements):
            Options for creating additional branch measurements.
        incomplete_measurements (IncompleteMeasurements):
            Options for handling incomplete measurements.
    """

    default_sigma_pq: DefaultSigma = field(default_factory=DefaultSigma)
    use_nominal_voltages: UMeasurementSubstitutionOptions = field(
        default_factory=UMeasurementSubstitutionOptions
    )
    use_ssh: SshSubstitutionOptions = field(default_factory=SshSubstitutionOptions)
    passive_nodes: PassiveNodeOptions = field(default_factory=PassiveNodeOptions)
    imeas_used_for_qcalc: QFromIOptions = field(default_factory=QFromIOptions)
    branch_measurements: BranchMeasurements = field(default_factory=BranchMeasurements)
    incomplete_measurements: IncompleteMeasurements = field(
        default_factory=IncompleteMeasurements
    )
