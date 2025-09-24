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


def calc_theta_k_2w(
    trafo: pd.Series, tapside: int, tapside_rtc: int
) -> tuple[float, float]:
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

    if taptype == "PhaseTapChangerAsymmetrical" and tapside_rtc != 0:
        taptype = "InPhaseAndAsymPST"

    if taptype == "PhaseTapChangerTabular" and tapside_rtc != 0:
        taptype = "InPhaseAndTabularPST"

    match taptype:
        case "PhaseTapChangerTabular":
            theta = _calc_theta_tabular(trafo, tapside)
            k = _calc_k(trafo)
        case "InPhaseAndTabularPST":
            theta = _calc_theta_tabular(trafo, tapside)
            k = calc_k_tabular_in_phase(trafo, tapside, tapside_rtc)
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
        case "InPhaseAndAsymPST":
            theta, k = calc_theta_k_asymmetrical_in_phase(trafo, tapside, tapside_rtc)
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
        tapside_rtc = 0  # TODO: determine tapside_rtc
        return calc_theta_k_2w(trafo, tapside, tapside_rtc)

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


def calc_k_tabular_in_phase(
    trafo,
    tapside,
    tapside_rtc,
):
    ## RTC
    steps_rtc = trafo[f"neutralStep{tapside_rtc}_rtc"] - trafo[f"step{tapside_rtc}_rtc"]
    voltage_increment_rtc = trafo[f"stepSize{tapside_rtc}"]

    u_netz1 = trafo["nomU1"]
    u_netz2 = trafo["nomU2"]
    u_rated1 = trafo["ratedU1"]
    u_rated2 = trafo["ratedU2"]

    k = calc_k_tabular_in_phase2(
        trafo,
        tapside,
        u_netz1,
        u_netz2,
        u_rated1,
        u_rated2,
        voltage_increment_rtc,
        steps_rtc,
    )

    k = 1 / k

    return k


def calc_k_tabular_in_phase2(
    trafo,
    tapside,
    u_netz1,
    u_netz2,
    u_rated1,
    u_rated2,
    voltage_increment_rtc,
    steps_rtc,
):
    w0 = (u_rated2 / u_netz2) / (u_rated1 / u_netz1)
    if tapside == 1:
        w0 = 1 / w0

    ### PST
    tc_ratio1 = trafo["tcRatio1"]
    tc_ratio2 = trafo["tcRatio2"]
    tc_ratio = 1  ## dummy

    if not np.isnan(tc_ratio1):
        tc_ratio = tc_ratio1
        # tc_ratio = 1 / tc_ratio
    elif not np.isnan(tc_ratio2):
        tc_ratio = tc_ratio2
        # tc_ratio = 1 / tc_ratio

    ### RTC

    k_tap = w0 * (1 + (voltage_increment_rtc / 100 * steps_rtc))

    ## COMBINED
    k = k_tap * tc_ratio

    return k


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

    ## from ENTSO-E "Phase Shift Transformers Modelling", chapter 4.2
    theta = 2.0 * np.arctan(0.5 * steps * voltage_increment)

    # TODO: check with an example where tapside == 2
    if tapside == 1:
        theta *= -1

    return theta


def _calc_theta_k_asymmetrical(trafo, tapside):
    steps = trafo[f"step{tapside}"] - trafo[f"neutralStep{tapside}"]
    voltage_increment = trafo[f"stepVoltageIncrement{tapside}"]
    winding_connection_angle = trafo[f"windingConnectionAngle{tapside}"] * deg_to_rad

    u_netz1 = trafo["nomU1"]
    u_netz2 = trafo["nomU2"]
    u_rated1 = trafo["ratedU1"]
    u_rated2 = trafo["ratedU2"]

    theta, k = calc_theta_k_generic(
        rtc_tapside=0,
        rtc_step=0,
        rtc_voltage_increment=0,
        pst_tapside=tapside,
        pst_step=steps,
        pst_voltage_increment=voltage_increment,
        winding_connection_angle=winding_connection_angle / deg_to_rad,
        u_rated1=u_rated1,
        u_rated2=u_rated2,
        u_netz1=u_netz1,
        u_netz2=u_netz2,
    )

    return theta, k


def calc_theta_k_asymmetrical_in_phase(
    trafo,
    tapside,
    tapside_rtc,
):
    ## PST
    steps = trafo[f"step{tapside}"] - trafo[f"neutralStep{tapside}"]

    voltage_increment = trafo[f"stepVoltageIncrement{tapside}"]
    winding_connection_angle = trafo[f"windingConnectionAngle{tapside}"] * deg_to_rad

    ## RTC

    steps_rtc = trafo[f"step{tapside_rtc}_rtc"] - trafo[f"neutralStep{tapside_rtc}_rtc"]
    voltage_increment_rtc = trafo[f"stepSize{tapside_rtc}"]

    u_netz1 = trafo["nomU1"]
    u_netz2 = trafo["nomU2"]
    u_rated1 = trafo["ratedU1"]
    u_rated2 = trafo["ratedU2"]

    theta, k = calc_theta_k_generic(
        rtc_tapside=tapside_rtc,
        rtc_step=steps_rtc,
        rtc_voltage_increment=voltage_increment_rtc,
        pst_tapside=tapside,
        pst_step=steps,
        pst_voltage_increment=voltage_increment,
        winding_connection_angle=winding_connection_angle / deg_to_rad,
        u_rated1=u_rated1,
        u_rated2=u_rated2,
        u_netz1=u_netz1,
        u_netz2=u_netz2,
    )

    return theta, k


def calc_theta_k_generic(
    rtc_tapside,
    rtc_step,
    rtc_voltage_increment,
    pst_tapside,
    pst_step,
    pst_voltage_increment,
    winding_connection_angle,
    u_rated1,
    u_rated2,
    u_netz1,
    u_netz2,
):
    angle = winding_connection_angle * deg_to_rad
    w0 = (u_rated2 / u_netz2) / (u_rated1 / u_netz1)

    #
    # RTC
    #
    if rtc_tapside == 0:
        t_rtc = 1
    else:

        if rtc_tapside == pst_tapside:
            rtc_step = -rtc_step

        nenner_rtc = 1 + ((rtc_step / 100) * rtc_voltage_increment) * complex(
            np.cos(0), np.sin(0)
        )
        t_rtc = w0 / nenner_rtc

    w0 = w0 * abs(t_rtc)

    ## TODO: dependent on rtc_tapside or pst_tapside?
    w0 = 1 / w0

    #
    # PST
    #
    nenner_pst = 1 + ((pst_step / 100) * pst_voltage_increment) * complex(
        np.cos(angle), np.sin(angle)
    )
    t_pst = w0 / nenner_pst

    ## ----------------------

    if rtc_tapside == 0:
        k = abs(t_pst)
        theta = np.angle(t_pst)
    else:
        k = 1 / abs(t_pst)
        theta = -np.angle(t_pst)

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

    ## TODO: determine why reciprocal is better in some cases, but not in all cases
    k = 1 / k

    return k
