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
from io import BytesIO

import pandas as pd
from SPARQLWrapper import SPARQLWrapper


class AbstractSparqlDataSource:

    def __init__(self, base_url, prefixes: dict[str, str]):
        self._base_url = base_url
        self._prefixes = prefixes

    @abstractmethod
    def query(self, query: str, add_prefixes: bool = True) -> pd.DataFrame: ...

    @abstractmethod
    def update(self, query: str, add_prefixes: bool = True) -> None: ...

    @abstractmethod
    def drop_graph(self, graph_iri: str) -> None: ...


class SparqlDataSource(AbstractSparqlDataSource):

    def __init__(
        self,
        base_url,
        prefixes: dict[str, str],
        query_endpoint="/query",
        update_endpoint="/update",
    ):
        super().__init__(base_url, prefixes)
        self._wrapper = SPARQLWrapper(
            endpoint=base_url + query_endpoint,
            updateEndpoint=base_url + update_endpoint,
        )
        self._wrapper.addCustomHttpHeader("Accept", "text/csv")
        self._wrapper.setOnlyConneg(True)

    def get_prefixes(self) -> dict[str, str]:
        return self._prefixes

    def _build_prefixes(self) -> str:
        """Builds a string of SPARQL prefixes from the provided dictionary"""
        prefix_str = ""
        for prefix, uri in self._prefixes.items():
            prefix_str += f"PREFIX {prefix}: <{uri}>\n"
        return prefix_str + "\n"

    def query(self, query: str, add_prefixes=True) -> pd.DataFrame:
        """Executes a SPARQL query and returns the result as a pandas DataFrame

        Args:
            query (str): The SPARQL query to execute
            add_prefixes (bool, optional): Add defined Sparql-Prefixes (e.g. xsd:, cim:)
                at the beginning of the query. Defaults to True.

        Returns:
            pd.DataFrame: Result of the query as a DataFrame
        """

        raw = self._execute(query, method="GET", add_prefixes=add_prefixes)
        return pd.read_csv(BytesIO(raw))

    def update(self, query: str, add_prefixes=True) -> None:
        """Executes a SPARQL update query

        Args:
            query (str): The SPARQL update query to execute
            add_prefixes (bool, optional): Add defined Sparql-Prefixes (e.g. xsd:, cim:)
                at the beginning of the query. Defaults to True.
        """

        self._execute(query, method="POST", add_prefixes=add_prefixes)

    def drop_graph(self, graph_iri: str) -> None:
        """Drops a named graph

        Args:
            graph_iri (str): The IRI of the graph to drop
        """

        if graph_iri == "default":
            q = "DROP DEFAULT"
        else:
            q = f"DROP GRAPH <{graph_iri}>"

        self.update(q)

    def format_query(self, string: str, query_params: dict):
        for a, b in query_params.items():
            string = string.replace(a, str(b))
        return string

    def _execute(
        self, query: str, *, method: str = "GET", add_prefixes: bool = True
    ) -> bytes:
        text = (self._build_prefixes() + query) if add_prefixes else query
        self._wrapper.setQuery(text)
        self._wrapper.setMethod(method)

        return self._wrapper.query().response.read()
