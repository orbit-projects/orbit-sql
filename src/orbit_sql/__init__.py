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
"""SQL repository and provider-adapter capabilities for Orbit."""

from orbit_sql.adapter import SQL_DATABASE_KEY, SQLAdapter, SQLAdapterRegistry
from orbit_sql.contracts import (
    SQLDatabase,
    SQLExecution,
    SQLParameters,
    SQLRow,
    SQLTransaction,
    SQLValue,
)
from orbit_sql.errors import DatabaseError
from orbit_sql.repository import SQLRepository, SQLUnitOfWork

__all__ = [
    "SQLAdapter",
    "SQLAdapterRegistry",
    "SQL_DATABASE_KEY",
    "SQLDatabase",
    "SQLExecution",
    "SQLParameters",
    "SQLRow",
    "SQLTransaction",
    "SQLValue",
    "DatabaseError",
    "SQLRepository",
    "SQLUnitOfWork",
]
