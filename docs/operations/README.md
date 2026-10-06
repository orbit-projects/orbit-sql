# Orbit SQL: operations and security

This guide organizes runtime behavior documented by the package. It does not certify production readiness. Verify provider/client versions, permissions, transport security, limits, and failure behavior in the target environment before release.

## Configuration surface

Environment names found in the package README:

The package README does not name `ORBIT_*` variables. Use its typed constructors and application configuration, and confirm exact runtime inputs in the implementation before deployment.

Use the package README's constructor and deployment examples. Store credentials in a secret manager and avoid logging credentials, raw provider errors, request data, or opaque cursors.

## Lifecycle, failure behavior, and limits

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

## Production validation

Validate startup/shutdown cleanup, timeout and cancellation behavior, concurrency and payload bounds where applicable, secret rotation and least-privilege access, data durability, backup/restore, and failover against the selected provider. Do not infer distributed or durable guarantees from an in-process API or fake-client tests.
