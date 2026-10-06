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
"""Exercise the user-facing Core and SQL composition example as a real ASGI app."""

import json

from orbit_testing import TestClient

from examples.notes_app import create_runtime


async def test_notes_example_runs_crud_through_runtime_and_sqlite() -> None:
    """Core startup, scoped resolution, repository writes, and shutdown compose together."""
    runtime = create_runtime(":memory:")
    async with TestClient(runtime) as client:
        created = await client.request(
            "POST",
            "/notes",
            body=b'{"id":1,"title":"first note"}',
            headers={"content-type": "application/json"},
        )
        listed = await client.request("GET", "/notes")

    assert created.status == 201
    assert json.loads(created.body) == {"id": 1, "title": "first note"}
    assert json.loads(listed.body) == [{"id": 1, "title": "first note"}]
