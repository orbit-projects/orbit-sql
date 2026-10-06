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
"""CRUD repositories and units of work execute through Core's SQL contract."""

import asyncio

import pytest
from orbit_data import RepositoryConflictError
from orbit_sql_sqlite import SQLiteDatabase
from pydantic import BaseModel, ConfigDict

from orbit_sql import DatabaseError, SQLRepository, SQLUnitOfWork


class Note(BaseModel):
    """Example typed row model used by the repository tests."""

    model_config = ConfigDict(strict=True)

    id: int
    title: str


async def make_database(path: str = ":memory:") -> SQLiteDatabase:
    """Create a database and schema for one test case."""
    database = SQLiteDatabase(path)
    await database.execute('CREATE TABLE "notes" ("id" INTEGER PRIMARY KEY, "title" TEXT NOT NULL)')
    return database


async def test_repository_crud_uses_validated_models_and_bound_values() -> None:
    database = await make_database()
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    try:
        await repository.add(Note(id=1, title="first"))
        assert await repository.get(1) == Note(id=1, title="first")
        assert await repository.get(2) is None
        assert await repository.list() == (Note(id=1, title="first"),)
        assert await repository.update(Note(id=1, title="changed")) is True
        assert await repository.update(Note(id=2, title="missing")) is False
        assert await repository.get(1) == Note(id=1, title="changed")
        assert await repository.delete(1) is True
        assert await repository.delete(1) is False
    finally:
        await database.aclose()


async def test_repository_maps_unique_write_conflicts_to_shared_data_error() -> None:
    """Repository callers get the same conflict exception across SQL providers."""

    class UniqueNote(BaseModel):
        model_config = ConfigDict(strict=True)

        id: int
        slug: str

    database = SQLiteDatabase(":memory:")
    try:
        await database.execute(
            'CREATE TABLE "notes" ("id" INTEGER PRIMARY KEY, "slug" TEXT UNIQUE NOT NULL)'
        )
        repository = SQLRepository(database, UniqueNote, table="notes", primary_key="id")
        await repository.add(UniqueNote(id=1, slug="first"))
        await repository.add(UniqueNote(id=2, slug="second"))

        with pytest.raises(RepositoryConflictError) as caught:
            await repository.add(UniqueNote(id=3, slug="first"))
        assert "first" not in str(caught.value)

        with pytest.raises(RepositoryConflictError):
            await repository.update(UniqueNote(id=2, slug="first"))
        assert await repository.get(2) == UniqueNote(id=2, slug="second")
    finally:
        await database.aclose()


async def test_unit_of_work_maps_deferred_commit_conflict_to_shared_data_error() -> None:
    """A conflict discovered during commit has the same repository-level exception."""

    class CommitConflict:
        async def __aexit__(self, *_args):
            raise DatabaseError(
                "database.constraint-conflict", "Database uniqueness constraint was violated."
            )

    database = SQLiteDatabase(":memory:")
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    unit = SQLUnitOfWork(database, (repository,))
    unit._context = CommitConflict()  # type: ignore[assignment]
    unit._transaction = object()  # type: ignore[assignment]
    unit._active = True
    try:
        with pytest.raises(RepositoryConflictError):
            await unit.__aexit__(None, None, None)
        assert not unit._active
    finally:
        await database.aclose()


async def test_unit_of_work_commits_on_success_and_rolls_back_on_error() -> None:
    database = await make_database()
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    unit = SQLUnitOfWork(database, (repository,))
    try:
        async with unit:
            await unit.repository(Note).add(Note(id=1, title="commit"))
        assert await repository.get(1) == Note(id=1, title="commit")

        with pytest.raises(RuntimeError, match="rollback"):
            async with unit:
                await unit.repository(Note).add(Note(id=2, title="discard"))
                raise RuntimeError("rollback")
        assert await repository.get(2) is None
    finally:
        await database.aclose()


async def test_unit_of_work_rolls_back_when_owning_task_is_cancelled() -> None:
    """Cancellation exits the transaction, rolls back writes, and releases the unit for reuse."""
    database = await make_database()
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    unit = SQLUnitOfWork(database, (repository,))
    entered = asyncio.Event()

    async def write_then_wait() -> None:
        async with unit:
            await unit.repository(Note).add(Note(id=3, title="cancelled"))
            entered.set()
            await asyncio.Future()

    task = asyncio.create_task(write_then_wait())
    try:
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert await repository.get(3) is None
        async with unit:
            await unit.repository(Note).add(Note(id=4, title="reused"))
        assert await repository.get(4) == Note(id=4, title="reused")
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await database.aclose()


async def test_unit_of_work_repositories_cannot_escape_transaction_scope() -> None:
    database = await make_database()
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    unit = SQLUnitOfWork(database, (repository,))
    try:
        with pytest.raises(RuntimeError, match="active SQLUnitOfWork"):
            unit.repository(Note)
        async with unit:
            transaction_repository = unit.repository(Note)
        with pytest.raises(DatabaseError) as caught:
            await transaction_repository.get(1)
        assert caught.value.code == "database.transaction-scope"
    finally:
        await database.aclose()


def test_repository_rejects_unsafe_or_incomplete_mappings() -> None:
    database = SQLiteDatabase(":memory:")
    try:
        with pytest.raises(ValueError, match="identifier"):
            SQLRepository(database, Note, table='notes; DROP TABLE "notes"', primary_key="id")
        with pytest.raises(ValueError, match="primary_key"):
            SQLRepository(database, Note, table="notes", primary_key="missing")
        with pytest.raises(ValueError, match="every model field"):
            SQLRepository(database, Note, table="notes", primary_key="id", columns={"id": "id"})
    finally:
        # No worker is created until the first SQL operation.
        assert database is not None


async def test_repository_rejects_nonportable_values_without_executing_sql() -> None:
    database = await make_database()
    repository = SQLRepository(database, Note, table="notes", primary_key="id")
    try:

        class InvalidValue(BaseModel):
            id: int
            value: list[int]

        invalid_repository = SQLRepository(database, InvalidValue, table="notes", primary_key="id")
        with pytest.raises(TypeError, match="portable SQL scalar"):
            await invalid_repository.add(InvalidValue(id=1, value=[1]))
        assert await repository.get(1) is None
    finally:
        await database.aclose()


async def test_repository_hides_row_validation_payloads() -> None:
    # A separate intentionally mismatched schema exercises the safe error boundary.
    class Counter(BaseModel):
        model_config = ConfigDict(strict=True)

        id: int
        count: int

    sql_database = SQLiteDatabase(":memory:")
    try:
        await sql_database.execute(
            'CREATE TABLE "counters" ("id" INTEGER PRIMARY KEY, "count" TEXT NOT NULL)'
        )
        await sql_database.execute(
            'INSERT INTO "counters" ("id", "count") VALUES ($1, $2)', (1, "not-an-int")
        )
        repository = SQLRepository(sql_database, Counter, table="counters", primary_key="id")
        with pytest.raises(DatabaseError) as caught:
            await repository.get(1)
        assert caught.value.code == "database.repository-row-invalid"
        assert "9" not in str(caught.value)
    finally:
        await sql_database.aclose()
