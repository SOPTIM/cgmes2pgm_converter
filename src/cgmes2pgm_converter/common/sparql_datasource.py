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

from .timer import Timer


class AbstractSparqlDataSource:

    def __init__(self, base_url, prefixes: str):
        self._base_url = base_url
        self._prefixes = prefixes

    @abstractmethod
    def query(self, query, add_prefixes=True) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def update(self, query, add_prefixes=True) -> None:
        raise NotImplementedError

    @abstractmethod
    def drop_graph(self, graph_name: str) -> None:
        raise NotImplementedError


class SparqlDataSource(AbstractSparqlDataSource):

    def __init__(
        self,
        base_url,
        prefixes: str,
        query_endpoint="/query",
        update_endpoint="/update",
    ):
        super().__init__(base_url, prefixes)
        self._query_wrapper = SPARQLWrapper(
            endpoint=base_url + query_endpoint,
            updateEndpoint=base_url + update_endpoint,
        )
        self._query_wrapper.addCustomHttpHeader("Accept", "text/csv")
        self._query_wrapper.setOnlyConneg(True)

    def query(self, query: str, add_prefixes=True) -> pd.DataFrame:
        """Executes a SPARQL query and returns the result as a pandas DataFrame

        Args:
            query (str): The SPARQL query to execute
            add_prefixes (bool, optional): Add defined Sparql-Prefixes (e.g. xsd:, cim:)
                at the beginning of the query. Defaults to True.

        Returns:
            pd.DataFrame: Result of the query as a DataFrame
        """

        if add_prefixes:
            self._query_wrapper.setQuery(self._prefixes + query)
        else:
            self._query_wrapper.setQuery(query)

        with Timer("\t\tQuery Execution"):
            self._query_wrapper.setMethod("GET")
            qr = self._query_wrapper.query()
        with Timer("\t\tResult Conversion"):
            data = BytesIO(qr.response.read())
            return pd.read_csv(data, sep=",")

    def update(self, query: str, add_prefixes=True) -> None:
        """Executes a SPARQL update query

        Args:
            query (str): The SPARQL update query to execute
            add_prefixes (bool, optional): Add defined Sparql-Prefixes (e.g. xsd:, cim:)
                at the beginning of the query. Defaults to True.
        """

        if add_prefixes:
            self._query_wrapper.setQuery(self._prefixes + query)
        else:
            self._query_wrapper.setQuery(query)

        with Timer("\t\tUpdate Execution"):
            self._query_wrapper.setMethod("POST")
            self._query_wrapper.query()

    def drop_graph(self, graph_name: str) -> None:
        """Drops a named graph

        Args:
            graph_name (str): The relative URL of the graph to drop (self._base_url is prepended)
        """

        drop_query = f"""
            DROP GRAPH <{graph_name}>
        """
        self.update(drop_query)

    def format_query(self, string: str, query_params: dict):
        for a, b in query_params.items():
            string = string.replace(a, str(b))
        return string
