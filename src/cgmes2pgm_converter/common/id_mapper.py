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
from typing import ItemsView

from bidict import bidict
from power_grid_model_io.data_types import ExtraInfo


class AbstractCgmesIdMapping:
    """
    Abstract class to map cim:IdentifiedObjects (mrid, name) to PGM IDs
    """

    @abstractmethod
    def add_cgmes_iri(self, cgmes_iri: str, name: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def add_cgmes_iris(self, cgmes_iris, names):
        raise NotImplementedError

    @abstractmethod
    def add_cgmes_term_iri(self, eq_iri, term_iri, name):
        raise NotImplementedError

    @abstractmethod
    def add_cgmes_term_iris(self, eq_iris, term_iris, names):
        raise NotImplementedError

    @abstractmethod
    def get_pgm_id(self, cgmes_iri: str, cgmes_term_iri: str | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_cgmes_iri(self, pgm_id: int) -> str:
        raise NotImplementedError

    def get_name_from_pgm(self, pgm_id: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_name_from_cgmes(self, cgmes_iri: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def items(self) -> ItemsView[str, int]:
        raise NotImplementedError

    @abstractmethod
    def __contains__(self, item: str | int) -> bool:
        raise NotImplementedError


class CgmesPgmIdMapping(AbstractCgmesIdMapping):
    """
    Class to map cim:IdentifiedObjects (mrid, name) to PGM IDs using bidict
    """

    def __init__(self):
        self._idx: int = 1
        self._cgmes_to_pgm: bidict[str, int] = bidict()
        self._cgmes_to_name: dict[str, str] = {}

        self._eq_to_term_to_pgm: dict[str, dict[str, int]] = {}

    def add_cgmes_iri(self, cgmes_iri: str, name: str) -> int:
        if cgmes_iri in self._cgmes_to_pgm:
            raise ValueError(f"{cgmes_iri} already exists")

        self._cgmes_to_pgm[cgmes_iri] = self._idx
        self._cgmes_to_name[cgmes_iri] = name
        self._idx += 1
        return self._idx - 1

    def add_cgmes_iris(self, cgmes_iris, names):
        ids = []
        for cgmes_iri, name in zip(cgmes_iris, names):
            ids.append(self.add_cgmes_iri(cgmes_iri, name))

        return ids

    def add_cgmes_term_iri(self, eq_iri, term_iri, name):
        """Creates a new PGM ID for an equipment IRI in combination with a terminal IRI.

        Usually, a PGM ID for an equipment is sufficient. However, if a branch/transformer
        is to be removed and replaced by two (or three) loads, then the terminal IRI has to
        be considered as well. This is necessary, in order map measurements to the
        newly created loads. Otherwise, the measurement would still refer to the original
        (removed) object.
        """
        new_id = self._idx
        self._idx += 1
        self._eq_to_term_to_pgm.setdefault(eq_iri, {})[term_iri] = new_id

        # also add both ids (concatenated with ",") to the main dictionary so that
        # you can get the corresponding cgmes ids for a pgm id (if needed)
        self._cgmes_to_pgm[eq_iri + "," + term_iri] = new_id
        self._cgmes_to_name[eq_iri + "," + term_iri] = name

        return new_id

    def add_cgmes_term_iris(self, eq_iris, term_iris, names):
        ids = []
        for eq_iri, term_iri, name in zip(eq_iris, term_iris, names):
            ids.append(self.add_cgmes_term_iri(eq_iri, term_iri, name))

        return ids

    def __contains__(self, item: str | int) -> bool:
        if isinstance(item, str):
            return (
                item in self._cgmes_to_pgm.keys()
                or item in self._eq_to_term_to_pgm.keys()
            )
        if isinstance(item, int):
            return item in self._cgmes_to_pgm.inv.keys()

        return False

    def get_pgm_id(self, cgmes_iri: str, cgmes_term_iri: str | None = None) -> int:
        """Get PGM ID for a given CGMES IRI alone or in combination with a terminal IRI"""
        if cgmes_term_iri is None:
            return self._cgmes_to_pgm[cgmes_iri]

        eq_dict = self._eq_to_term_to_pgm.get(cgmes_iri)
        if eq_dict is None:
            # nothing in this dict, check the main dict
            return self._cgmes_to_pgm[cgmes_iri]

        pgm_id = eq_dict.get(cgmes_term_iri)

        if pgm_id is None:
            # if no id for term found, then search again in the main dict with just the eq id
            return self._cgmes_to_pgm[cgmes_iri]

        return pgm_id

    def get_cgmes_iri(self, pgm_id: int) -> str:
        return self._cgmes_to_pgm.inv[pgm_id]

    def get_name_from_pgm(self, pgm_id: int) -> str:
        return self._cgmes_to_name[self.get_cgmes_iri(pgm_id)]

    def get_name_from_cgmes(self, cgmes_iri: str) -> str:
        return self._cgmes_to_name[cgmes_iri]

    def items(self) -> ItemsView[str, int]:
        return self._cgmes_to_pgm.items()

    def build_extra_info(self) -> ExtraInfo:
        """Build extra info for the PGM JSON file,
        containing the related CGMES ID and Name for each PGM ID

        Returns:
            ExtraInfo: Extra Info
        """
        d = {}
        for cgmes_iri, pgm_id in self._cgmes_to_pgm.items():
            d[pgm_id] = {
                "_name": str(self.get_name_from_pgm(pgm_id)),
                "_mrid": cgmes_iri,
            }

        return d
