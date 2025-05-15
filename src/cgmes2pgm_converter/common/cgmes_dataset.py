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

import pandas as pd

from .cgmes_literals import CIM_ID_OBJ, Profile
from .sparql_datasource import SparqlDataSource

MAX_ROWS_PER_INSERT = 10000
RDF_PREFIXES = """
        PREFIX cim:    <%s>
        PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
    """


class CgmesDataset(SparqlDataSource):
    """
    CgmesDataset is a class that extends SparqlDataSource to manage and manipulate CGMES datasets
    using SPARQL queries. It provides functionality to handle RDF graphs, insert data from pandas
    DataFrames, and manage profiles within the CGMES dataset.
    Attributes:
        base_url (str): The base URL used to construct URIs for RDF triples.
        cim_namespace (str): The namespace for CIM (Common Information Model) elements.
            - CGMES 2: "http://iec.ch/TC57/2013/CIM-schema-cim16#"
            - CGMES 3: "http://iec.ch/TC57/CIM100#"
        graphs (dict[Profile, str]): A dictionary mapping profiles to their RDF graph URIs.
    """

    def __init__(
        self,
        base_url: str,
        cim_namespace: str,
        graphs: dict[Profile, str] = None,
    ):
        super().__init__(base_url, RDF_PREFIXES % cim_namespace)
        self.base_url = base_url
        self.graphs = graphs or {}
        self.cim_namespace = cim_namespace

        for graph in self.graphs.values():
            if graph.strip() == "":
                raise ValueError("Named Graph cannot be empty.")

        if (Profile.OP in self.graphs) and (Profile.MEAS not in self.graphs):
            self.graphs[Profile.MEAS] = self.graphs[Profile.OP]
        if (Profile.MEAS in self.graphs) and (Profile.OP not in self.graphs):
            self.graphs[Profile.OP] = self.graphs[Profile.MEAS]

    def drop_profile(self, profile: Profile) -> None:
        """Drop the RDF graph associated with the specified profile."""
        self.drop_graph(self.graphs[profile])

    def mrid_to_uri(self, mrid: str) -> str:
        """Convert an mRID (Master Resource Identifier) to a URI format."""
        mrid = mrid.replace('"', "")
        return f"<{self.base_url}/data#_{mrid}>"

    def insert_df(self, df: pd.DataFrame, profile: Profile, include_mrid=True) -> None:
        """Insert a DataFrame into the specified profile.
        The DataFrame must have a column "IdentifiedObject.mRID"
        The column names are used as predicates in the RDF triples.
        Maximum number of rows per INSERT-Statement is defined by MAX_ROWS_PER_INSERT

        Args:
            df (pd.DataFrame): The DataFrame to insert
            profile (Profile): The profile to insert the data into
            include_mrid (bool, optional): Include the mRID in the triples. Defaults to True.
        """

        logging.debug(
            "Inserting %s triples into %s",
            df.shape[0] * df.shape[1],
            self.graphs[profile],
        )

        # Split Dataframe if it has more than MAX_TRIPLES_PER_INSERT rows
        if df.shape[0] > MAX_ROWS_PER_INSERT:
            num_chunks = df.shape[0] // MAX_ROWS_PER_INSERT
            for i in range(num_chunks):
                self._insert_df(
                    df.iloc[i * MAX_ROWS_PER_INSERT : (i + 1) * MAX_ROWS_PER_INSERT],
                    self.graphs[profile],
                    include_mrid,
                )
            if df.shape[0] % MAX_ROWS_PER_INSERT != 0:
                self._insert_df(
                    df.iloc[num_chunks * MAX_ROWS_PER_INSERT :],
                    self.graphs[profile],
                    include_mrid,
                )
        else:
            self._insert_df(df, self.graphs[profile], include_mrid)

    def _insert_df(self, df: pd.DataFrame, graph: str, include_mrid):

        uris = [self.mrid_to_uri(row) for row in df[f"{CIM_ID_OBJ}.mRID"]]
        triples = []
        for col in df.columns:

            if col == f"{CIM_ID_OBJ}.mRID" and not include_mrid:
                continue

            triples += [f"{uri} {col} {row}." for uri, row in zip(uris, df[col])]

        insert_query = f"""
            {self._prefixes}
            INSERT DATA {{
                GRAPH <{graph}> {{
                    {"".join(triples)}
                }}
            }}
        """
        self.update(insert_query, add_prefixes=False)
