# Orbit SQL: architecture and boundaries

## Responsibility

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

## Declared dependencies

The following dependency declarations come from the checked-in manifests. Optional groups and development dependencies are called out separately.

### `pyproject.toml`
- `orbit-data>=0.1.0a1,<0.2`
- Optional `dev` group: `pytest>=8,<10`, `pytest-asyncio>=0.24,<2`, `ruff>=0.8,<1`, `mypy>=1.13,<2`.

Declared dependencies do not mean that optional providers or services are bundled with this package.

## Implementation layout

Representative implementation files in this checkout:

- `src/orbit_sql/__init__.py`
- `src/orbit_sql/adapter.py`
- `src/orbit_sql/contracts.py`
- `src/orbit_sql/errors.py`
- `src/orbit_sql/repository.py`

## Public contract and scope

The README does not contain a separately headed architecture section. Its responsibility statement above and the public source files define the implemented scope; this guide adds no behavior beyond that description.

## Boundary rules

Keep provider SDKs, credentials, transports, and provider-specific error translation in provider adapters. Keep reusable capability contracts in the matching capability package and lifecycle orchestration in Core. Apply the relevant layer for this repository and preserve the dependency direction shown above.
