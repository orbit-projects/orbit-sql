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
"""Bounded SQL CRUD repositories and transaction-scoped units of work."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import date, datetime, time
from decimal import Decimal
from types import TracebackType
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable
from uuid import UUID

from orbit_data import Repository, RepositoryConflictError, UnitOfWork
from pydantic import BaseModel, ValidationError

from orbit_sql.contracts import (
    SQLDatabase,
    SQLExecution,
    SQLParameters,
    SQLRow,
    SQLTransaction,
    SQLValue,
)
from orbit_sql.errors import DatabaseError

EntityT = TypeVar("EntityT", bound=BaseModel)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_MAX_FIELDS = 256
_MAX_PAGE_SIZE = 10_000


@runtime_checkable
class _SQLExecutor(Protocol):
    """Structural subset shared by SQLDatabase and SQLTransaction."""

    async def execute(self, statement: str, parameters: SQLParameters = ()) -> SQLExecution:
        """Execute one parameterized statement and return its affected-row metadata."""
        raise NotImplementedError

    async def fetch_one(self, statement: str, parameters: SQLParameters = ()) -> SQLRow | None:
        """Fetch at most one row, returning ``None`` when the result is empty."""
        raise NotImplementedError

    async def fetch_all(
        self, statement: str, parameters: SQLParameters = (), *, limit: int = 1_000
    ) -> tuple[SQLRow, ...]:
        """Fetch no more than the explicit row limit from a query."""
        raise NotImplementedError


class SQLRepository(Repository[EntityT, SQLValue], Generic[EntityT]):
    """CRUD repository over one Pydantic entity and a Core SQL executor.

    Table and column identifiers are fixed at construction and strictly validated. All runtime data
    values use bound positional parameters; identifiers never come from request values.
    """

    def __init__(
        self,
        executor: SQLDatabase | SQLTransaction,
        model: type[EntityT],
        *,
        table: str,
        primary_key: str,
        columns: Mapping[str, str] | None = None,
    ) -> None:
        """Bind a typed model to a table with an explicit primary-key field."""
        if not isinstance(executor, _SQLExecutor):
            raise TypeError("executor must implement the Orbit SQL execution contract.")
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise TypeError("model must be a Pydantic BaseModel class.")
        _validate_identifier(table, "table")
        if not isinstance(primary_key, str) or primary_key not in model.model_fields:
            raise ValueError("primary_key must name a field on the entity model.")
        field_names = tuple(model.model_fields)
        if not field_names or len(field_names) > _MAX_FIELDS:
            raise ValueError("SQL entity models must define between 1 and 256 fields.")
        if columns is None:
            column_map = {field: field for field in field_names}
        else:
            if not isinstance(columns, Mapping) or set(columns) != set(field_names):
                raise ValueError("columns must map every model field exactly once.")
            column_map = dict(columns)
        for field_name, column_name in column_map.items():
            if not isinstance(field_name, str) or field_name not in model.model_fields:
                raise ValueError("column mapping contains an unknown model field.")
            _validate_identifier(column_name, "column")
        if len(set(column_map.values())) != len(column_map):
            raise ValueError("SQL column names must be unique.")
        self._executor = executor
        self._model = model
        self._table = table
        self._primary_key = primary_key
        self._columns = column_map
        self._field_names = field_names

    @property
    def model(self) -> type[EntityT]:
        """Return the model associated with this repository."""
        return self._model

    async def get(self, key: SQLValue) -> EntityT | None:
        """Fetch one entity by its key."""
        _sql_value(key)
        statement = (
            f"SELECT {self._select_columns()} FROM {_quote(self._table)} "
            f"WHERE {_quote(self._columns[self._primary_key])} = $1"
        )
        row = await self._executor.fetch_one(statement, (key,))
        return None if row is None else self._decode(row)

    async def list(self, *, limit: int = 100) -> tuple[EntityT, ...]:
        """Return a key-ordered page, rejecting unbounded or invalid page sizes."""
        _validate_limit(limit)
        statement = (
            f"SELECT {self._select_columns()} FROM {_quote(self._table)} "
            f"ORDER BY {_quote(self._columns[self._primary_key])} LIMIT $1"
        )
        rows = await self._executor.fetch_all(statement, (limit,), limit=limit)
        return tuple(self._decode(row) for row in rows)

    async def add(self, entity: EntityT) -> None:
        """Insert an entity; duplicate-key failures remain provider-neutral database errors."""
        values = self._entity_values(entity)
        columns = ", ".join(_quote(self._columns[field]) for field in self._field_names)
        placeholders = ", ".join(f"${index}" for index in range(1, len(values) + 1))
        statement = f"INSERT INTO {_quote(self._table)} ({columns}) VALUES ({placeholders})"
        try:
            await self._executor.execute(statement, values)
        except DatabaseError as exc:
            if exc.code == "database.constraint-conflict":
                raise RepositoryConflictError() from None
            raise

    async def update(self, entity: EntityT) -> bool:
        """Replace all non-key fields and report whether a row with the key existed."""
        values = self._entity_values(entity)
        mutable_fields = tuple(field for field in self._field_names if field != self._primary_key)
        if not mutable_fields:
            raise ValueError("An update requires at least one non-key entity field.")
        assignments = ", ".join(
            f"{_quote(self._columns[field])} = ${index}"
            for index, field in enumerate(mutable_fields, start=1)
        )
        key_position = len(mutable_fields) + 1
        statement = (
            f"UPDATE {_quote(self._table)} SET {assignments} "
            f"WHERE {_quote(self._columns[self._primary_key])} = ${key_position}"
        )
        value_by_field = dict(zip(self._field_names, values, strict=True))
        parameters = tuple(value_by_field[field] for field in mutable_fields) + (
            value_by_field[self._primary_key],
        )
        try:
            result = await self._executor.execute(statement, parameters)
        except DatabaseError as exc:
            if exc.code == "database.constraint-conflict":
                raise RepositoryConflictError() from None
            raise
        return result.rowcount > 0

    async def delete(self, key: SQLValue) -> bool:
        """Delete one entity by key and report whether a row was affected."""
        _sql_value(key)
        statement = (
            f"DELETE FROM {_quote(self._table)} "
            f"WHERE {_quote(self._columns[self._primary_key])} = $1"
        )
        result = await self._executor.execute(statement, (key,))
        return result.rowcount > 0

    def _select_columns(self) -> str:
        """Select configured database columns under the model's Python field names."""
        return ", ".join(
            f"{_quote(self._columns[field])} AS {_quote(field)}" for field in self._field_names
        )

    def _entity_values(self, entity: EntityT) -> SQLParameters:
        """Extract model values and reject nested or nonportable driver values."""
        if not isinstance(entity, self._model):
            raise TypeError("Entity does not match this SQL repository's model.")
        dumped = entity.model_dump(mode="python", by_alias=False)
        if set(dumped) != set(self._field_names):
            raise ValueError("Entity serialization must include each configured model field.")
        return tuple(_sql_value(dumped[field]) for field in self._field_names)

    def _decode(self, row: SQLRow) -> EntityT:
        """Validate a detached SQL row and avoid exposing validation payloads in public errors."""
        try:
            return self._model.model_validate(dict(row))
        except ValidationError:
            raise DatabaseError(
                "database.repository-row-invalid", "Database row does not match its entity model."
            ) from None

    def _bind(self, executor: SQLTransaction) -> SQLRepository[EntityT]:
        """Create a transaction-bound repository with the same immutable mapping."""
        return SQLRepository(
            executor,
            self._model,
            table=self._table,
            primary_key=self._primary_key,
            columns=self._columns,
        )


class SQLUnitOfWork(UnitOfWork):
    """Bind registered repositories to one Core transaction for atomic composition."""

    def __init__(
        self,
        database: SQLDatabase,
        repositories: Sequence[SQLRepository[Any]],
    ) -> None:
        """Register repositories; the database connection is acquired only on context entry."""
        if not isinstance(database, SQLDatabase):
            raise TypeError("database must implement Orbit's SQLDatabase contract.")
        if isinstance(repositories, (str, bytes)) or not isinstance(repositories, Sequence):
            raise TypeError("repositories must be a sequence of SQLRepository instances.")
        detached = tuple(repositories)
        if not detached or any(not isinstance(repo, SQLRepository) for repo in detached):
            raise ValueError("At least one SQLRepository is required.")
        if len({repo.model for repo in detached}) != len(detached):
            raise ValueError("Only one repository per model can be registered in a unit of work.")
        if any(repo._executor is not database for repo in detached):
            raise ValueError("Repositories and unit of work must share the same SQLDatabase.")
        self._database = database
        self._repositories = {repo.model: repo for repo in detached}
        self._context: AbstractAsyncContextManager[SQLTransaction] | None = None
        self._transaction: SQLTransaction | None = None
        self._active = False

    async def __aenter__(self) -> SQLUnitOfWork:
        """Open one Core transaction and make repositories available within this scope."""
        if self._active:
            raise RuntimeError("SQLUnitOfWork cannot be entered more than once at a time.")
        context = self._database.transaction()
        transaction = await context.__aenter__()
        self._context = context
        self._transaction = transaction
        self._active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Delegate commit or rollback to Core, then invalidate transaction-bound access."""
        context = self._context
        if not self._active or context is None:
            raise RuntimeError("SQLUnitOfWork is not active.")
        try:
            try:
                return await context.__aexit__(exc_type, exc, traceback)
            except DatabaseError as error:
                if error.code == "database.constraint-conflict":
                    raise RepositoryConflictError() from None
                raise
        finally:
            self._transaction = None
            self._context = None
            self._active = False

    def repository(self, model: type[EntityT]) -> SQLRepository[EntityT]:
        """Return a repository bound to the active transaction for ``model``."""
        if not self._active or self._transaction is None:
            raise RuntimeError("Repositories are available only inside an active SQLUnitOfWork.")
        repository = self._repositories.get(model)
        if repository is None:
            raise KeyError("No SQL repository is registered for this entity model.")
        return repository._bind(self._transaction)


def _validate_identifier(value: object, kind: str) -> None:
    """Restrict SQL identifiers to portable ASCII names before quoting them."""
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"SQL {kind} must be a portable ASCII identifier of at most 63 characters."
        )


def _quote(value: str) -> str:
    """Quote an identifier using syntax shared by SQLite and PostgreSQL."""
    return f'"{value}"'


def _validate_limit(limit: int) -> None:
    """Require a finite positive repository page size within Core's SQL bound."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_PAGE_SIZE:
        raise ValueError(f"Repository limit must be between 1 and {_MAX_PAGE_SIZE}.")


def _sql_value(value: object) -> SQLValue:
    """Accept only portable finite scalars supported by the Core SQL contract."""
    if value is None or isinstance(value, (bool, int, str, bytes, date, datetime, time, UUID)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise ValueError("SQL floating-point values must be finite.")
    if isinstance(value, Decimal):
        if value.is_finite():
            return value
        raise ValueError("SQL decimal values must be finite.")
    raise TypeError("Entity fields must serialize to Core's portable SQL scalar types.")


__all__ = ["SQLRepository", "SQLUnitOfWork"]
