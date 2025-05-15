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

from .abstract_transformer import AbstractTransformerBuilder


class Abstract2WTransformerBuilder(AbstractTransformerBuilder):

    def winding_count(self) -> int:
        return 2

    def _validate_transformer_data(self, data: pd.DataFrame):

        for _, transformer in data.iterrows():

            # r, x, g, b, should be on side with TransformerEnd.endNumber=1
            if (transformer["r1"] == 0 and transformer["r2"] != 0) or (
                transformer["x1"] == 0 and transformer["x2"] != 0
            ):
                logging.warning(
                    "Transformer %s: found r, x on side 2 but expected them on side 1",
                    transformer["name1"],
                )
                logging.warning("Electrical parameters in PGM-Data may be incorrect.")

            # EndNumber 1 should be high voltage side
            if transformer["ratedU1"] < transformer["ratedU2"]:
                logging.warning(
                    "Transformer %s: Side with EndNumber=1 should be high voltage side",
                    transformer["name1"],
                )
                logging.warning("Electrical parameters in PGM-Data may be incorrect.")

    @staticmethod
    def calc_trafo2w_params(sn, u_rated, r, x, g, b):
        """Calculate parameters for 2 winding transformer.

        Args:
            sn: Rated power [VA]
            u_rated: Rated voltage [V]
            r: Resistance [Ohm]
            x: Reactance [Ohm]
            g: Conductance [S]
            b: Susceptance [S]

        Returns:
            tuple: (uk, pk, i0, p0)
                uk: relative short circuit voltage [-]
                pk: short circuit power [W]
                i0: relative no load current [-]
                p0: no load iron loss [W]
        """

        ## `uk` must be between 0 and 1, restrict to values to valid range
        uk_ = np.sign(x) * np.sqrt(r**2 + x**2) * sn / (u_rated**2)
        uk__ = np.where(uk_ < 1.0, uk_, 0.99)
        uk = np.where(uk__ != 0.0, uk__, 0.01)

        # `pk` must be positive, use the absolute value of `r`
        #  can be negative in EquivalentBranches
        pk = np.abs(r) * (sn**2) / (u_rated**2)

        i0 = np.sqrt(g**2 + b**2) * (u_rated**2) / sn
        p0 = g * (u_rated**2)
        return uk, pk, i0, p0
