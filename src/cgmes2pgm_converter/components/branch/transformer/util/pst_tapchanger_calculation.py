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

import logging

import numpy as np
import pandas as pd

# calculations from ENTSO-E Phase Shift Transformers Modelling
# α: tapAngle
# r: ratio
# ∂u: voltageStepIncrement
# θ: windingConnectionAngle

deg_to_rad = np.pi / 180


def calc_theta_k_2w(trafo: pd.Series, tapside: int) -> tuple[float, float]:
    """Calculates theta and k for a 2-winding transformer
    based on the tapchanger type.

    Args:
        trafo (pd.Series): Transformer data
        tapside (int): Tap side (1 or 2)
    Returns:
        tuple: theta and k
    """
    theta, k = 0.0, 1.0
    taptype = trafo[f"taptype{tapside}"]

    match taptype:
        case "PhaseTapChangerTabular":
            theta = _calc_theta_tabular(trafo, tapside)
            k = _calc_k(trafo)
        case "PhaseTapChangerLinear":
            theta = _calc_theta_linear(trafo, tapside)
            k = _calc_k(trafo)
        case "PhaseTapChangerSymmetrical":
            theta = _calc_theta_symmetrical(trafo, tapside)
            k = _calc_k(trafo)
        case "PhaseTapChangerAsymmetrical":
            logging.warning("Found Transformer with a PhaseTapChangerAsymmetrical.")
            logging.warning("\tElectrical Parameters may be inaccurate.")
            theta, k = _calc_theta_k_asymmetrical(trafo, tapside)
        case "PhaseTapChanger" | "PhaseTapChangerNonLinear":
            logging.warning(
                "Tapchanger type %s for transformer %s is an abstract class",
                taptype,
                trafo["name1"],
            )
        case _:
            logging.warning(
                "Unknown tapchanger type %s for transformer %s",
                taptype,
                trafo["name1"],
            )

    return theta, k


def calc_theta_k_3w(trafo, tapside, current_side):
    """Calculates theta and k for a 3-winding transformer

    Args:
        trafo (pd.Series): Transformer data
        tapside (int): Tap side of the transformer
        current_side (int): Current side of the transformer

    Returns:
        tuple: theta and k
    """
    if tapside == current_side:
        return calc_theta_k_2w(trafo, tapside)

    # The current 2w is a trafo without a tapchanger
    return 0.0, _calc_k(trafo)


def _calc_theta_tabular(trafo, tapside):

    # --- Shift theta ---
    tc_angle1 = trafo["tcAngle1"]
    tc_angle2 = trafo["tcAngle2"]

    tc_angle = tc_angle1 if not np.isnan(tc_angle1) else tc_angle2

    theta = tc_angle * deg_to_rad

    if tapside == 2:
        theta *= -1

    return theta


def _calc_theta_linear(trafo, tapside):
    # s = n-n_0
    # α = s * ∂α
    # r = 1

    steps = trafo[f"neutralStep{tapside}"] - trafo[f"step{tapside}"]
    shift_per_step = trafo[f"stepPhaseShift{tapside}"] * deg_to_rad
    theta = steps * shift_per_step

    # TODO: check with an example where tapside == 2
    if tapside == 1:
        theta *= -1

    return theta


def _calc_theta_symmetrical(trafo, tapside):
    # s = n-n_0
    # α = 2 * atan(0.5 * s * ∂u)
    # r = 1
    steps = trafo[f"neutralStep{tapside}"] - trafo[f"step{tapside}"]
    voltage_increment = trafo[f"stepVoltageIncrement{tapside}"]
    theta = 2.0 * np.arctan(0.5 * steps * voltage_increment)

    # TODO: check with an example where tapside == 2
    if tapside == 1:
        theta *= -1

    return theta


def _calc_theta_k_asymmetrical(trafo, tapside):
    # s = n-n_0
    # z = s * ∂u * sin(θ)
    # tan(α) = (z)/(1 + s * ∂u * cos(θ))
    # 1/r = √[z^2 + (1 + z)^2]

    steps = trafo[f"neutralStep{tapside}"] - trafo[f"step{tapside}"]
    voltage_increment = trafo[f"stepVoltageIncrement{tapside}"]
    winding_connection_angle = trafo[f"windingConnectionAngle{tapside}"] * deg_to_rad

    z = steps * voltage_increment * np.sin(winding_connection_angle)

    theta = np.arctan(
        z / (1 + steps * voltage_increment * np.cos(winding_connection_angle))
    )

    # FIXME: Both calculations produce inaccurate results
    # k = 1 / np.sqrt(z**2 + (1 + z) ** 2)
    k = _calc_k(trafo)

    if tapside == 1:
        theta *= -1

    # return 0.0, 1.0
    return theta, k


def _calc_k(trafo):
    nominal_ratio_ = trafo["nomU1"] / trafo["nomU2"]
    rated_u1_ = trafo["ratedU1"]
    rated_u2_ = trafo["ratedU2"]

    tc_ratio1 = trafo["tcRatio1"]
    tc_ratio2 = trafo["tcRatio2"]

    corr_u1_ = rated_u1_
    corr_u2_ = rated_u2_
    if not np.isnan(tc_ratio1):
        corr_u1_ *= tc_ratio1
    elif not np.isnan(tc_ratio2):
        corr_u2_ *= tc_ratio2
    k = (corr_u1_ / corr_u2_) / nominal_ratio_

    return k
