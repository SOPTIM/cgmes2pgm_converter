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

from abc import abstractmethod

import numpy as np
import pandas as pd

from ...component import AbstractPgmComponentBuilder


class AbstractTransformerBuilder(AbstractPgmComponentBuilder):

    _query = """
        SELECT ?tr ?name ?_term ?trEnd ?node ?b ?connectionType ?g ?r ?x ?_tratio ?_tstep ?ratedS ?ratedU ?nomU ?connected ?tapchanger ?highStep ?lowStep ?neutralStep ?neutralU ?normalStep ?step ?stepSize ?endNumber ?taptype ?topoIsland
        WHERE {

        {
            SELECT ?tr (COUNT(?_trEnd) as ?n) (SAMPLE(?_name) as ?name)
            WHERE {
            ?tr a cim:PowerTransformer;
                $IN_SERVICE
                # cim:Equipment.inService "true";
                cim:IdentifiedObject.name ?_name.

            ?_trEnd a cim:PowerTransformerEnd;
                    cim:PowerTransformerEnd.PowerTransformer ?tr.
            }
            GROUP BY ?tr
            HAVING (?n = $WINDING_COUNT)
        }


        ?trEnd a cim:PowerTransformerEnd;
                cim:PowerTransformerEnd.PowerTransformer ?tr;
                cim:TransformerEnd.Terminal ?_term;
                cim:TransformerEnd.endNumber ?endNumber;
                cim:PowerTransformerEnd.b ?_b;
                cim:PowerTransformerEnd.r ?_r;
                cim:PowerTransformerEnd.x ?_x;
                cim:PowerTransformerEnd.ratedU ?ratedU.

        OPTIONAL {?trEnd cim:PowerTransformerEnd.connectionKind ?connectionType.}
        OPTIONAL {?trEnd cim:PowerTransformerEnd.g ?_g. }
        OPTIONAL {?trEnd cim:PowerTransformerEnd.ratedS ?ratedS.}

        OPTIONAL {
            ?_ratiotapchanger a ?_ratiotap_type;
                                cim:RatioTapChanger.TransformerEnd ?trEnd;
                                cim:RatioTapChanger.stepVoltageIncrement ?stepSize;
                                cim:TapChanger.step ?step;
                                cim:TapChanger.normalStep ?normalStep;
                                cim:TapChanger.neutralStep ?neutralStep;
                                cim:TapChanger.highStep ?highStep;
                                cim:TapChanger.lowStep ?lowStep;
                                cim:TapChanger.neutralU ?neutralU.

            ?svTap cim:SvTapStep.TapChanger ?_ratiotapchanger;
                cim:SvTapStep.position ?svStep.

            OPTIONAL {
                ?_ratiotapchanger cim:RatioTapChanger.RatioTapChangerTable ?_table.

                ?_tpoint cim:RatioTapChangerTablePoint.RatioTapChangerTable ?_table;
                        cim:TapChangerTablePoint.b ?_tb;
                        cim:TapChangerTablePoint.g ?_tg;
                        cim:TapChangerTablePoint.r ?_tr;
                        cim:TapChangerTablePoint.x ?_tx;
                        cim:TapChangerTablePoint.ratio ?_tratio;
                        cim:TapChangerTablePoint.step ?_tstep.
                filter(xsd:float(?_tstep) = xsd:float(?svStep))
            }
        }

        ## use values (delta in percent) from table point to compute the real rxgb values
        BIND((xsd:double(?_r) * (1 + xsd:double(?_tr) / 100)) as ?_rCorr)
        BIND((xsd:double(?_x) * (1 + xsd:double(?_tx) / 100)) as ?_xCorr)
        BIND((xsd:double(?_b) * (1 + xsd:double(?_tb) / 100)) as ?_bCorr)
        BIND((xsd:double(?_g) * (1 + xsd:double(?_tg) / 100)) as ?_gCorr)

        BIND(COALESCE(?_rCorr, ?_r) as ?r)
        BIND(COALESCE(?_xCorr, ?_x) as ?x)
        BIND(COALESCE(?_bCorr, ?_b) as ?b)
        BIND(COALESCE(?_gCorr, ?_g) as ?g)

        OPTIONAL {
            ?_phasetapchanger a ?_phasetap_type;
                                cim:PhaseTapChanger.TransformerEnd ?trEnd.
        }


        ?_term cim:Terminal.TopologicalNode ?node;
            cim:ACDCTerminal.connected ?connected.

        ?node cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nomU.

        OPTIONAL {
            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?node.
        }

        BIND(COALESCE(?_phasetapchanger, ?_ratiotapchanger) as ?tapchanger)
        BIND(COALESCE(?_phasetap_type, ?_ratiotap_type) as ?taptype)

        }
        ORDER BY ?tr ?endNumber
    """

    _pst_query = """
        SELECT
            ?tr ?name ?_term ?trEnd ?node ?connectionType
            ?r ?x ?g ?b ?tcRatio ?tcStep ?tcAngle
            ?ratedS ?ratedU ?nomU ?connected ?endNumber
            ?tapchanger
            ?lowStep ?highStep ?neutralStep ?normalStep ?step ?svStep ?neutralU
            ?stepPhaseShift ?xMax ?stepVoltageIncrement ?windingConnectionAngle ?taptype
            ?topoIsland
        WHERE {

        {
            SELECT ?tr (COUNT(?_trEnd) as ?n) (SAMPLE(?_name) as ?name) (SAMPLE(?_ptc) as ?ptc)
            WHERE {
            ?tr a cim:PowerTransformer;
                $IN_SERVICE
                # cim:Equipment.inService "true";
                cim:IdentifiedObject.name ?_name.

                ?_trEnd a cim:PowerTransformerEnd;
                    cim:PowerTransformerEnd.PowerTransformer ?tr.

                optional {?_ptc cim:PhaseTapChanger.TransformerEnd ?_trEnd.}
            }
            GROUP BY ?tr
            HAVING (bound(?ptc) && ?n = $WINDING_COUNT)
        }


        ?trEnd a cim:PowerTransformerEnd;
                cim:PowerTransformerEnd.PowerTransformer ?tr;
                cim:TransformerEnd.Terminal ?_term;
                cim:TransformerEnd.endNumber ?endNumber;
                cim:PowerTransformerEnd.b ?_b;
                cim:PowerTransformerEnd.r ?_r;
                cim:PowerTransformerEnd.x ?_x;
                cim:PowerTransformerEnd.ratedU ?ratedU.

        OPTIONAL {?trEnd cim:PowerTransformerEnd.connectionKind ?connectionType.}
        OPTIONAL {?trEnd cim:PowerTransformerEnd.g ?_g. }
        OPTIONAL {?trEnd cim:PowerTransformerEnd.ratedS ?ratedS.}

        OPTIONAL {
            ?tapchanger a ?_ratiotap_type;
                                cim:PhaseTapChanger.TransformerEnd ?trEnd;
                                cim:TapChanger.step ?step;
                                cim:TapChanger.normalStep ?normalStep;
                                cim:TapChanger.neutralStep ?neutralStep;
                                cim:TapChanger.highStep ?highStep;
                                cim:TapChanger.lowStep ?lowStep;
                                cim:TapChanger.neutralU ?neutralU.

            ?svTap cim:SvTapStep.TapChanger ?tapchanger;
                cim:SvTapStep.position ?svStep.

            # Phase Tap Changer Tablular
            OPTIONAL {
                ?tapchanger cim:PhaseTapChangerTabular.PhaseTapChangerTable ?_table.

                ?_tpoint cim:PhaseTapChangerTablePoint.PhaseTapChangerTable ?_table;
                         cim:TapChangerTablePoint.step ?tcStep;
                         cim:PhaseTapChangerTablePoint.angle ?tcAngle.

                OPTIONAL { ?_tpoint cim:TapChangerTablePoint.ratio ?tcRatio. }
                OPTIONAL { ?_tpoint cim:TapChangerTablePoint.ratio ?_tr. }
                OPTIONAL { ?_tpoint cim:TapChangerTablePoint.ratio ?_tx. }
                OPTIONAL { ?_tpoint cim:TapChangerTablePoint.ratio ?_tg. }
                OPTIONAL { ?_tpoint cim:TapChangerTablePoint.ratio ?_tb. }

                filter(xsd:float(?tcStep) = xsd:float(?svStep))
            }

            # Phase Tap Changer Linear
            OPTIONAL {
                ?tapchanger cim:PhaseTapChangerLinear.stepPhaseShiftIncrement ?stepPhaseShift;
                            cim:PhaseTapChangerLinear.xMax ?xMax.
            }

            # Phase Tap Changer Non Linear
            OPTIONAL {
                ?tapchanger cim:PhaseTapChangerNonLinear.voltageStepIncrement ?stepVoltageIncrement;
                            cim:PhaseTapChangerNonLinear.xMax ?xMax.
                OPTIONAL { ?tapchanger cim:PhaseTapChangerAsymmetrical.windingConnectionAngle ?windingConnectionAngle. }
            }
        }

        ## use values (delta in percent) from table point to compute the real rxgb values
        BIND((xsd:double(?_r) * (1 + xsd:double(?_tr) / 100)) as ?_rCorr)
        BIND((xsd:double(?_x) * (1 + xsd:double(?_tx) / 100)) as ?_xCorr)
        BIND((xsd:double(?_b) * (1 + xsd:double(?_tb) / 100)) as ?_bCorr)
        BIND((xsd:double(?_g) * (1 + xsd:double(?_tg) / 100)) as ?_gCorr)

        BIND(COALESCE(?_rCorr, ?_r) as ?r)
        BIND(COALESCE(?_xCorr, ?_x) as ?x)
        BIND(COALESCE(?_bCorr, ?_b) as ?b)
        BIND(COALESCE(?_gCorr, ?_g, 0) as ?g)

        BIND(COALESCE(?_phasetap_type, ?_ratiotap_type) as ?_taptype)
        BIND(STRAFTER(STR(?_taptype), "#") AS ?taptype)

        ?_term cim:Terminal.TopologicalNode ?node;
            cim:ACDCTerminal.connected ?connected.

        ?node cim:TopologicalNode.BaseVoltage/cim:BaseVoltage.nominalVoltage ?nomU.

        OPTIONAL {
            $TOPO_ISLAND
            #?topoIsland cim:IdentifiedObject.name "Network";
            #            cim:TopologicalIsland.TopologicalNodes ?node.
        }
        }
        ORDER BY ?tr ?endNumber
    """

    @abstractmethod
    def winding_count(self) -> int:
        raise NotImplementedError

    def _get_pst_result(self) -> pd.DataFrame:
        """Returns Query Result for PST Transformers.

        Returns:
            pd.DataFrame: Query Result
        """

        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?node"),
            "$WINDING_COUNT": str(self.winding_count()),
        }
        q = self._replace(self._pst_query, args)
        res = self._source.query(q)

        return self._process_query_result(res)

    def _get_query_result(self) -> pd.DataFrame:
        """Returns Query Result for Transformer.
        Columns are named as per _queryColNames,
        with trailing number for each side (eg. trEnd1, trEnd2, ...)

        Returns:
            pd.DataFrame: Query Result
        """

        args = {
            "$IN_SERVICE": self._in_service(),
            "$TOPO_ISLAND": self._at_topo_island_node("?node"),
            "$WINDING_COUNT": str(self.winding_count()),
        }
        q = self._replace(self._query, args)
        res = self._source.query(q)

        return self._process_query_result(res)

    def _process_query_result(self, res: pd.DataFrame) -> pd.DataFrame:
        """
        Merges rows of the transformer query result for each transformer end
        into one row for each transformer.
        The column names are suffixed with the respective end number (e.g. trEnd1, trEnd2).

        Args:
            res (pd.DataFrame): Query result, each row represents one transformer end
        """

        if res.shape[0] % self.winding_count() != 0:
            raise ValueError("Query result does not match winding count")

        indices = np.arange(0, res.shape[0], self.winding_count())

        # Concatenate horizontally
        result = pd.concat(
            [
                res.iloc[indices + i].reset_index(drop=True)
                for i in range(self.winding_count())
            ],
            axis=1,
        )

        result.columns = [
            f"{col}{i}"
            for i in range(1, self.winding_count() + 1)
            for col in res.columns
        ]

        ## remove transformers that are connected to nodes outside of a topologicalIsland
        ## (only if looking at islands is configured)
        options = self._converter_options
        if options.only_topo_island is True or options.topo_island_name is not None:
            tp1 = result["topoIsland1"]
            tp2 = result["topoIsland2"]

            n1 = tp1.isnull()
            n2 = tp2.isnull()

            n12 = np.logical_or(n1, n2)

            if self.winding_count() == 3:
                tp3 = result["topoIsland3"]
                n3 = tp3.isnull()
                n12 = np.logical_or(n12, n3)

            result = result[~n12]
            result = result.reset_index(
                drop=True
            )  # Required for right shape in initialize_array

        return result

    def _adjust_tap_minmax_for_negative_tap_size(self, row):
        tmp = row["tap_min"]
        row["tap_min"] = row["tap_max"]
        row["tap_max"] = tmp
        row["tap_size"] *= -1
