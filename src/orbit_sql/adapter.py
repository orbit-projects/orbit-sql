# Copyright 2026-present Orbit Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Explicit selection of trusted SQL provider adapters."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from orbit_sql.contracts import SQLDatabase
from orbit_sql.errors import DatabaseError

_ADAPTER_NAME = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_MAX_ADAPTERS = 64
SQL_DATABASE_KEY = "orbit.database.sql"
"""Shared Core container key for a configured ``SQLDatabase`` capability."""


@runtime_checkable
class SQLAdapter(Protocol):
    """Contract implemented by an optional package that opens an Orbit SQL database."""

    @property
    def name(self) -> str:
        """Return a stable lowercase selection name such as ``postgres``."""

    @property
    def configuration_model(self) -> type[BaseModel]:
        """Return the Pydantic model accepted by this provider adapter."""

    async def connect(self, configuration: BaseModel) -> SQLDatabase:
        """Open and return a resource implementing Orbit's SQLDatabase contract."""


class SQLAdapterRegistry:
    """Bounded explicit registry; it never imports packages or scans entry points."""

    def __init__(self) -> None:
        """Create an empty registry for trusted adapter objects supplied by the application."""
        self._adapters: dict[str, SQLAdapter] = {}
        self._frozen = False

    @property
    def adapters(self) -> Mapping[str, SQLAdapter]:
        """Return an immutable snapshot of registered adapters."""
        return MappingProxyType(dict(self._adapters))

    def register(self, adapter: SQLAdapter) -> None:
        """Register one valid adapter before the first connection attempt."""
        if self._frozen:
            raise DatabaseError("database.registry-frozen", "SQL adapter registry is frozen.")
        if not isinstance(adapter, SQLAdapter):
            raise TypeError("Adapter must implement SQLAdapter.")
        name = adapter.name
        if not isinstance(name, str) or not _ADAPTER_NAME.fullmatch(name):
            raise ValueError(
                "Adapter name must be a lowercase identifier of at most 63 characters."
            )
        config_model = adapter.configuration_model
        if not isinstance(config_model, type) or not issubclass(config_model, BaseModel):
            raise TypeError("Adapter configuration_model must be a Pydantic model class.")
        if name in self._adapters:
            raise DatabaseError("database.adapter-duplicate", "SQL adapter name is duplicated.")
        if len(self._adapters) >= _MAX_ADAPTERS:
            raise DatabaseError("database.adapter-limit", "SQL adapter capacity is reached.")
        self._adapters[name] = adapter

    async def connect(self, name: str, configuration: BaseModel) -> SQLDatabase:
        """Validate provider settings and connect through the explicitly selected adapter."""
        if not isinstance(name, str) or not _ADAPTER_NAME.fullmatch(name):
            raise ValueError(
                "Adapter name must be a lowercase identifier of at most 63 characters."
            )
        adapter = self._adapters.get(name)
        if adapter is None:
            raise DatabaseError("database.adapter-not-found", "SQL adapter is not registered.")
        if not isinstance(configuration, adapter.configuration_model):
            raise TypeError("Configuration does not match the selected SQL adapter.")
        self._frozen = True
        database = await adapter.connect(configuration)
        if not isinstance(database, SQLDatabase):
            raise DatabaseError(
                "database.adapter-contract", "Adapter returned an invalid resource."
            )
        return database


__all__ = ["SQLAdapter", "SQLAdapterRegistry", "SQL_DATABASE_KEY"]
