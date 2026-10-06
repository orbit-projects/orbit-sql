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
"""Runnable Notes API composed from Orbit Core, orbit-data, and orbit-sql."""

from __future__ import annotations

import os

from orbit import Application, ApplicationConfig, Service, ServiceDescriptor
from orbit.asgi import Request, Response
from orbit.runtime import Runtime
from orbit_data import Repository
from pydantic import BaseModel, ConfigDict

from orbit_sql import SQLRepository, SQL_DATABASE_KEY
from orbit_sql_sqlite import SQLiteConfig, SQLitePlugin


class Note(BaseModel):
    """A note entity whose identity and title are validated at the HTTP boundary."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    id: int
    title: str


class NoteSchema(Service):
    """Create the local schema during Core's managed application initialization."""

    descriptor = ServiceDescriptor(name="note-schema")

    def __init__(self, application: Application) -> None:
        """Retain the owning application so initialization resolves its managed SQL resource."""
        self._application = application

    async def initialize(self) -> None:
        """Initialize the example table before the application begins serving requests."""
        database = await self._application.container.aresolve(SQL_DATABASE_KEY)
        await database.execute(
            'CREATE TABLE IF NOT EXISTS "notes" ("id" INTEGER PRIMARY KEY, "title" TEXT NOT NULL)'
        )


def create_runtime(database_path: str = ":memory:") -> Runtime:
    """Build the Notes app and let Core own the separately installed SQLite provider."""
    application = Application(ApplicationConfig(name="notes-example"))
    application.plugins.register(SQLitePlugin(SQLiteConfig(path=database_path)))
    application.register(NoteSchema(application))

    @application.router.route(
        "/notes",
        method="POST",
        name="notes-create",
        request_model=Note,
        response_model=Note,
    )
    async def create_note(request: Request) -> Response:
        """Store one validated note using the provider-neutral repository contract."""
        note = request.validated_body
        database = await request.container.aresolve(SQL_DATABASE_KEY)
        repository: Repository[Note, int] = SQLRepository(
            database, Note, table="notes", primary_key="id"
        )
        await repository.add(note)
        return Response.json(note.model_dump(), status=201)

    @application.router.route("/notes", method="GET", name="notes-list")
    async def list_notes(request: Request) -> Response:
        """Return a bounded list through the common repository API."""
        database = await request.container.aresolve(SQL_DATABASE_KEY)
        repository: Repository[Note, int] = SQLRepository(
            database, Note, table="notes", primary_key="id"
        )
        notes = await repository.list(limit=100)
        return Response.json([note.model_dump() for note in notes])

    return Runtime(application)


runtime = create_runtime(os.environ.get("ORBIT_NOTES_DB", ":memory:"))
