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
"""SQL provider selection is explicit, typed, bounded, and frozen after connect."""

import pytest
from orbit_sql_sqlite import SQLiteDatabase
from pydantic import BaseModel

from orbit_sql import DatabaseError, SQLAdapter, SQLAdapterRegistry


class SQLiteConfig(BaseModel):
    """Settings accepted by the local test adapter."""

    path: str


class OtherConfig(BaseModel):
    """Settings deliberately incompatible with the SQLite adapter."""

    value: str


class SQLiteAdapterFixture:
    """Provider adapter demonstrating Core-compatible resource registration."""

    name = "sqlite-test"
    configuration_model = SQLiteConfig

    async def connect(self, configuration: BaseModel) -> SQLiteDatabase:
        """Open the Core SQLite database using adapter-owned validated settings."""
        assert isinstance(configuration, SQLiteConfig)
        return SQLiteDatabase(configuration.path)


async def test_registry_opens_only_the_explicitly_selected_adapter(tmp_path) -> None:
    registry = SQLAdapterRegistry()
    adapter = SQLiteAdapterFixture()
    assert isinstance(adapter, SQLAdapter)
    registry.register(adapter)
    database = await registry.connect("sqlite-test", SQLiteConfig(path=str(tmp_path / "data.db")))
    try:
        row = await database.fetch_one("SELECT 1 AS value")
        assert row is not None and row["value"] == 1
    finally:
        await database.aclose()


async def test_registry_rejects_unknown_adapter_and_mismatched_config() -> None:
    with pytest.raises(DatabaseError) as caught:
        await SQLAdapterRegistry().connect("postgres", SQLiteConfig(path="unused"))
    assert caught.value.code == "database.adapter-not-found"

    registry = SQLAdapterRegistry()
    registry.register(SQLiteAdapterFixture())
    with pytest.raises(TypeError, match="does not match"):
        await registry.connect("sqlite-test", OtherConfig(value="wrong adapter"))


async def test_registry_freezes_after_a_connection_attempt(tmp_path) -> None:
    registry = SQLAdapterRegistry()
    registry.register(SQLiteAdapterFixture())
    database = await registry.connect("sqlite-test", SQLiteConfig(path=str(tmp_path / "data.db")))
    try:
        with pytest.raises(DatabaseError) as caught:
            registry.register(SQLiteAdapterFixture())
        assert caught.value.code == "database.registry-frozen"
    finally:
        await database.aclose()
