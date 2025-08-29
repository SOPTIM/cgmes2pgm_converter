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

MAX_TRIPLES_PER_INSERT = 10000

RDF_PREFIXES = {
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "md": "http://iec.ch/TC57/61970-552/ModelDescription/1#",
    "dm": "http://iec.ch/TC57/61970-552/DifferenceModel/1#",
}


class CgmesDataset(SparqlDataSource):
    """
    CgmesDataset is a class that extends SparqlDataSource to manage and manipulate CGMES datasets
    using SPARQL queries. It provides functionality to handle RDF graphs, insert data from pandas
    DataFrames, and manage profiles within the CGMES dataset.
    Attributes:
        base_url (str): The base URL of the dataset
        cim_namespace (str): The namespace for CIM (Common Information Model) elements
            - CGMES 2: "http://iec.ch/TC57/2013/CIM-schema-cim16#"
            - CGMES 3: "http://iec.ch/TC57/CIM100#"
        graphs (dict[Profile, str]): A dictionary mapping profiles to their RDF graph URIs
    """

    def __init__(
        self,
        base_url: str,
        cim_namespace: str,
        graphs: dict[Profile, str] | None = None,
    ):
        rdf_prefixes = RDF_PREFIXES.copy()
        rdf_prefixes["cim"] = cim_namespace

        super().__init__(base_url, rdf_prefixes)
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
        self.drop_graph(self._get_profile_uri(profile))

    def mrid_to_urn(self, mrid: str) -> str:
        """Convert an mRID (Master Resource Identifier) to its iri in the dataset."""
        mrid = mrid.replace('"', "")
        return f"<urn:uuid:{mrid}>"

    def query(
        self, query: str, add_prefixes=True, remove_uuid_base_uri=True
    ) -> pd.DataFrame:
        result = super().query(query, add_prefixes)
        if remove_uuid_base_uri:
            # Remove the base URI from all IRIs (if wanted) -> helps to keep the output clean
            prefix = self.base_url + "#"
            for col in result.select_dtypes(include="object"):
                result[col] = result[col].str.replace(f"^{prefix}", "", regex=True)
        return result

    def insert_df(
        self, df: pd.DataFrame, profile: Profile | str, include_mrid=True
    ) -> None:
        """Insert a DataFrame into the specified profile.
        The DataFrame must have a column "IdentifiedObject.mRID"
        The column names are used as predicates in the RDF triples.
        Maximum number of rows per INSERT-Statement is defined by MAX_TRIPLES_PER_INSERT

        Args:
            df (pd.DataFrame): The DataFrame to insert
            profile (Profile | str): The profile or URI of the graph to insert the DataFrame into.
            include_mrid (bool, optional): Include the mRID in the triples. Defaults to True.
        """
        profile_uri = self._get_profile_uri(profile)

        logging.debug(
            "Inserting %s triples into %s",
            df.shape[0] * df.shape[1],
            profile_uri,
        )

        max_rows_per_insert = MAX_TRIPLES_PER_INSERT // df.shape[1]

        # Split Dataframe if it has more than MAX_TRIPLES_PER_INSERT rows
        if df.shape[0] > max_rows_per_insert:
            num_chunks = df.shape[0] // max_rows_per_insert
            for i in range(num_chunks):
                self._insert_df(
                    df.iloc[i * max_rows_per_insert : (i + 1) * max_rows_per_insert],
                    profile_uri,
                    include_mrid,
                )
            if df.shape[0] % max_rows_per_insert != 0:
                self._insert_df(
                    df.iloc[num_chunks * max_rows_per_insert :],
                    profile_uri,
                    include_mrid,
                )
        else:
            self._insert_df(df, profile_uri, include_mrid)

    def _insert_df(self, df: pd.DataFrame, graph: str, include_mrid):

        uris = [self.mrid_to_urn(row) for row in df[f"{CIM_ID_OBJ}.mRID"]]
        triples = []
        for col in df.columns:

            if col == f"{CIM_ID_OBJ}.mRID" and not include_mrid:
                continue

            triples += [f"{uri} {col} {row}." for uri, row in zip(uris, df[col])]

        insert_query = f"""
            INSERT DATA {{
                GRAPH <{graph}> {{
                    {"".join(triples)}
                }}
            }}
        """
        self.update(insert_query)

    def insert_triples(
        self, triples: list[tuple[str, str, str]], profile: Profile | str
    ):
        """Insert a list of RDF triples into the dataset.
        Args:
            triples (list[str]): A list of RDF triples in the format "subject predicate object".
            profile (Profile | str): The profile or URI of the graph to insert the triples into.
        """

        # Split triples if they exceed MAX_TRIPLES_PER_INSERT
        if len(triples) > MAX_TRIPLES_PER_INSERT:
            num_chunks = len(triples) // MAX_TRIPLES_PER_INSERT
            for i in range(num_chunks):
                self._insert_triples(
                    triples[
                        i * MAX_TRIPLES_PER_INSERT : (i + 1) * MAX_TRIPLES_PER_INSERT
                    ],
                    profile,
                )
            if len(triples) % MAX_TRIPLES_PER_INSERT != 0:
                self._insert_triples(
                    triples[num_chunks * MAX_TRIPLES_PER_INSERT :], profile
                )
        else:
            self._insert_triples(triples, profile)

    def _insert_triples(
        self, triples: list[tuple[str, str, str]], profile: Profile | str
    ):

        profile_uri = self._get_profile_uri(profile)
        triples_str = []

        for subject, predicate, obj in triples:
            triples_str.append(f"{subject} {predicate} {obj}.")

        if profile_uri == "default":
            insert_query = f"""
            INSERT DATA {{
                    {"\n\t\t".join(triples_str)}
            }}
        """
        else:
            insert_query = f"""
                INSERT DATA {{
                    GRAPH <{profile_uri}> {{
                        {"\n\t\t".join(triples_str)}
                    }}
                }}
            """
        self.update(insert_query)

    def _get_profile_uri(self, profile: Profile | str) -> str:
        return self.graphs[profile] if isinstance(profile, Profile) else profile
