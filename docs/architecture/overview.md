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

Successful standalone writes commit before `SQLDatabase.execute()` returns. Group multiple
statements in `database.transaction()` or `SQLUnitOfWork` to get atomic commit/rollback behavior.
If cancellation or connection failure occurs while the database is committing, the outcome may be
unknown; only retry writes that are idempotent or protected by an application-level deduplication
key.

Provider-neutral read routing is an optional `SQLReadRouting` extension. `SQLDatabase` remains
primary-consistent by default. A caller can configure `SQLRepository` to route its reads to
weighted replicas with `SQLReadPreference.REPLICA`; writes and `SQLUnitOfWork` stay on the primary.
The provider enforces read-only transaction semantics and reports missing replicas instead of
silently falling back. Orbit does not classify arbitrary SQL text to decide where a statement is
safe.

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

`SQLDatabase` supplies parameterized `execute`, `fetch_one`, `fetch_all`, transaction, and close
operations. Results are detached immutable `SQLRow` values. Successful standalone writes commit
before `execute()` returns; explicit transaction contexts group statements atomically. `fetch_all`
must reject results beyond the caller's bound rather than returning a partial result.

This package does not parse arbitrary SQL, discover schemas, retry statements, provide an ORM, or
run migrations. Safe parameter binding protects values; callers must keep dynamic identifiers
fixed or validate them against an allowlist. See the separate provider package for driver-specific
timeout, pooling, TLS, and failure behavior.

## Boundary rules

Keep provider SDKs, credentials, transports, and provider-specific error translation in provider adapters. Keep reusable capability contracts in the matching capability package and lifecycle orchestration in Core. Apply the relevant layer for this repository and preserve the dependency direction shown above.
