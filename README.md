# Orbit SQL

`orbit-sql` defines Orbit's provider-neutral SQL contract and implements SQL repositories and
transaction-scoped units of work. It does not include a database driver. SQLite, MySQL and
PostgreSQL implementations are installed from `orbit-sql-sqlite`, `orbit-sql-mysql` and
`orbit-sql-postgres` respectively.

```bash
pip install orbit-core orbit-data orbit-sql orbit-sql-sqlite
```

Applications use the same async `SQLDatabase`, bounded `SQLRow`, execution metadata and
`SQLTransaction` types for each provider. Queries use positional `$1`, `$2`, … placeholders. Provider
adapters bind those values safely using their native driver conventions. `SQLRepository` accepts
fixed table/column mappings and Pydantic entities; identifiers are validated and quoted, while
runtime values are always bound parameters. `SQLUnitOfWork` scopes repositories to one provider
transaction and commits on normal exit or rolls back on exceptions and cancellation.

Providers may register a lazy resource at `SQL_DATABASE_KEY` through Core's container lifecycle.
The registry selects trusted adapter objects explicitly and never scans entry points or imports
packages automatically. No migrations, ORM, schema discovery, or generated identifiers are implied.

## Documentation

The package-specific guides cover [architecture](docs/architecture/overview.md), [operations and security](docs/operations/README.md), and [development](docs/development/README.md), with [security guidance](docs/security/overview.md). The [documentation index](docs/README.md) links to the full package overview and project policies.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pip install -e ../orbit-sql-sqlite
pytest
ruff check .
mypy
```

This package is pre-alpha and its API is not stable. Unit tests use the separate SQLite adapter;
provider wire behavior and deployment characteristics need validation against live MySQL and
PostgreSQL services. It supports Python 3.11 through 3.14.

Licensed under Apache-2.0.

