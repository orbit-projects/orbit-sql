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
"""Sanitized errors shared by Orbit SQL providers and capability code."""


class DatabaseError(Exception):
    """A database failure that carries a stable code and no vendor diagnostic text."""

    def __init__(self, code: str, message: str) -> None:
        """Create a provider-neutral failure without retaining a driver exception."""
        if not isinstance(code, str) or not code.startswith("database."):
            raise ValueError("Database error code must use the 'database.' namespace.")
        if not isinstance(message, str) or not message:
            raise ValueError("Database error message must be a non-empty string.")
        self.code = code
        self.message = message
        super().__init__(message)


__all__ = ["DatabaseError"]
