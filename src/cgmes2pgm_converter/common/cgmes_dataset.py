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
from typing import override

import pandas as pd

from cgmes2pgm_converter.common.cgmes_literals import ProfileInfo

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

fullmodel_base_query = """
    ?fullModel a md:FullModel;
        md:Model.profile ?profile;
        md:Model.scenarioTime ?scenarioTime;
        md:Model.description ?description.

    OPTIONAL {
        ?fullModel a md:FullModel;
            md:Model.modelingAuthoritySet ?_mas.
    }
    BIND(COALESCE(?_mas, "<no modelingAuthoritySet>") AS ?mas)
"""

fullmodel_query = f"""
    SELECT ?fullModel ?profile ?mas ?scenarioTime ?description ?graph
    WHERE {{
        {{
            {fullmodel_base_query}
            BIND("" AS ?graph)
        }}
        UNION {{
            GRAPH ?graph {{  {fullmodel_base_query} }}
        }}
    }}
"""


class NamedGraphs:
    def __init__(self, base_url: str, default_graph: str = "default"):
        self.graphs: dict[Profile, set[str]] = {}
        self._graph_names: dict[str, set[ProfileInfo]] = {}
        self.base_url = base_url
        self.default_graph = default_graph

    def add(
        self, profile_info: ProfileInfo, graph_name: str, updating: bool = False
    ) -> str:
        if profile_info.profile not in self.graphs:
            self.graphs[profile_info.profile] = set()
        if graph_name not in self._graph_names:
            self._graph_names[graph_name] = set()

        if graph_name in self.graphs[profile_info.profile] and not updating:
            logging.warning(
                "Graph %s for profile %s already exists.",
                graph_name,
                f"{profile_info.profile}{'[BD]' if profile_info.boundary else ''}",
            )
        else:
            logging.debug(
                "Adding graph %s for profile %s.",
                graph_name,
                f"{profile_info.profile}{'[BD]' if profile_info.boundary else ''}",
            )
            self.graphs[profile_info.profile].add(graph_name)
            self._graph_names[graph_name].add(profile_info)

        return graph_name

    def remove_profile(self, profile: Profile) -> None:
        names = self.graphs.pop(profile, set())
        for name in names:
            profiles = self._graph_names.get(name)
            if profiles:
                [profiles.discard(pr) for pr in profiles if pr.profile == profile]
                if not profiles:
                    # remove whole entry if no profiles left
                    self._graph_names.pop(name)

    def remove_graph(self, graph_name: str) -> None:
        profile_infos = self._graph_names.pop(graph_name, set())
        for pi in profile_infos:
            graphs = self.graphs.get(pi.profile)
            if graphs:
                graphs.discard(graph_name)
                if not graphs:
                    # remove whole entry if no graphs left
                    self.graphs.pop(pi.profile)

    def determine_graph_name(self, profile: list[Profile], mas: list[str] = []) -> str:

        if len(profile) == 0:
            return self.default_graph

        mas_sorted = sorted(mas)
        norm_mas = "_".join([self.normalize_mas(m) for m in mas_sorted])

        if len(profile) == 1:
            return f"cim:{profile[0].name.upper()}{('_' + norm_mas.upper()) if norm_mas else ''}"
        else:
            profiles_sorted = sorted(profile, key=lambda p: p.name)
            profile_part = "_".join(p.name.upper() for p in profiles_sorted)
            return f"cim:{profile_part}{('_' + norm_mas.upper()) if norm_mas else ''}"

    def get(self, profile: Profile) -> set[str]:
        return self.graphs.get(profile, set())

    def format_for_query(self, profile: Profile) -> str:
        graphs = self.get(profile)
        if len(graphs) == 0:
            return ""
        elif len(graphs) == 1:
            tmp = f"<{list(graphs)[0]}>"
            return tmp
        else:
            tmp = " ".join(f"<{g}>" for g in graphs)
            return tmp

    def normalize_mas(self, mas: str) -> str:
        mas2 = mas.split("//")[-1]
        mas3 = mas2.split("/")[0]
        mas4 = mas3.split(".")
        if len(mas4) == 1:
            return mas4[0]
        elif len(mas4) > 1:
            return mas4[-2]

        return mas


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
        split_profiles (bool): Whether to split profiles into separate graphs
    """

    def __init__(
        self,
        base_url: str,
        cim_namespace: str,
        split_profiles: bool = False,
    ):
        rdf_prefixes = RDF_PREFIXES.copy()
        rdf_prefixes["cim"] = cim_namespace

        super().__init__(base_url, rdf_prefixes)
        self.base_url = base_url
        self.named_graphs = NamedGraphs(base_url)
        self.split_profiles = split_profiles
        self.cim_namespace = cim_namespace

    def update_cim_namespace(self, new_namespace: str) -> bool:
        """Update the CIM namespace in the dataset and RDF prefixes."""
        if new_namespace != self.cim_namespace:
            self.cim_namespace = new_namespace
            self._prefixes["cim"] = new_namespace
            logging.info(f"Updated CIM namespace to: {new_namespace}")
            return True
        else:
            logging.debug("CIM namespace unchanged.")
            pass
        return False

    def drop_profile(self, profile: Profile) -> None:
        """Drop the RDF graph associated with the specified profile."""
        for g in self._get_profile_uri(profile):
            self.drop_graph(g)
        self.named_graphs.remove_profile(profile)

    @override
    def drop_graph(self, graph_iri: str) -> None:
        super().drop_graph(graph_iri)
        self.named_graphs.remove_graph(graph_iri)

    def mrid_to_urn(self, mrid: str) -> str:
        """Convert an mRID (Master Resource Identifier) to its iri in the dataset."""
        mrid = mrid.replace('"', "")
        return f"<urn:uuid:{mrid}>"

    def populate_named_graph_mapping(self):
        # read fullmodels from all graphs
        dataset_profiles = self.query(fullmodel_query)

        named_graphs = self.named_graphs
        for idx, item in dataset_profiles.iterrows():

            graph_name = item["graph"]
            profile_str = item["profile"]
            profile_info = Profile.parse(profile_str)
            if profile_info.profile == Profile.SV and "cgmes2pgm" in graph_name.lower():
                # skip SV graph created by cgmes2pgm libraries itself, in order to
                # not mix original and computed values and make new calculations reproducible
                continue
            if profile_info.profile != Profile.UNKNOWN:
                named_graphs.add(profile_info, graph_name, updating=False)

        if (named_graphs.graphs.get(Profile.OP)) and (
            not named_graphs.graphs.get(Profile.MEAS)
        ):
            named_graphs.graphs[Profile.MEAS] = named_graphs.graphs[Profile.OP]
        if (named_graphs.graphs.get(Profile.MEAS)) and (
            not named_graphs.graphs.get(Profile.OP)
        ):
            named_graphs.graphs[Profile.OP] = named_graphs.graphs[Profile.MEAS]

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
        profile_uris = self._get_profile_uri(profile)
        if len(profile_uris) == 0:
            raise ValueError(
                f"Profile {profile} has no named graph assigned, cannot insert DataFrame."
            )
        elif len(profile_uris) > 1:
            raise ValueError(
                f"Profile {profile} has multiple named graphs assigned, cannot insert DataFrame."
            )

        profile_uri = profile_uris[0]

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

        if graph == "default":
            insert_query = f"""
                INSERT DATA {{
                    {"".join(triples)}
                }}
            """
        else:
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

        profile_uris = self._get_profile_uri(profile)
        if len(profile_uris) == 0:
            raise ValueError(
                f"Profile {profile} has no named graph assigned, cannot insert triples."
            )
        elif len(profile_uris) > 1:
            raise ValueError(
                f"Profile {profile} has multiple named graphs assigned, cannot insert triples."
            )
        profile_uri = profile_uris[0]
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

    def _get_profile_uri(self, profile: Profile | str) -> list[str]:
        if isinstance(profile, Profile):
            return list(self.named_graphs.get(profile))
        else:
            return [profile]
