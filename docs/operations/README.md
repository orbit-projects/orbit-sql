# Orbit SQL: operations

`orbit-sql` defines a common async API; a database driver is installed separately. Select the
provider package explicitly for the deployment, for example:

```bash
python -m pip install orbit-core orbit-data orbit-sql orbit-sql-sqlite
```

Use `orbit-sql-mysql` or `orbit-sql-postgres` when the application needs those server databases.
Provider-specific credentials, TLS settings, timeouts, pooling, and live-service requirements are
documented by each adapter package.

## Compose repositories and transactions

Bind runtime values with positional `$1`, `$2`, … parameters. Place table and column names in
trusted application configuration; placeholders do not bind identifiers. `SQLRepository` validates
configured identifiers and binds entity values. `SQLUnitOfWork` groups repository operations in a
single database transaction.

Successful direct writes commit before `SQLDatabase.execute()` returns. Use
`async with database.transaction()` or `SQLUnitOfWork` for multi-statement atomic work. On normal
exit the transaction commits; on an exception or cancellation the adapter rolls it back according
to the provider's cleanup semantics. If cancellation or connection failure occurs during commit,
the final write outcome can be unknown. Reconcile before retrying a non-idempotent operation and
use an application-level deduplication key when retries can repeat effects.

`fetch_all()` is bounded and rejects excess rows instead of returning a partial result. Select a
limit that fits the endpoint's memory and latency budget; use database-side filtering and pagination
for larger datasets. `SQLRow` is detached from driver cursors, but row values can still contain
sensitive application data.

## Read-replica routing

Reads use the primary by default. To route one repository's `get()` and `list()` calls to weighted
replicas, configure it with `read_preference=SQLReadPreference.REPLICA`. The provider must enforce
read-only behavior and raises a provider-neutral error if replicas are not configured; it never
silently sends a requested replica read to the primary. Repository inserts, updates, and deletes
continue to use the primary. Replica reads can lag writes, so use the default primary preference
for read-your-writes paths. `SQLUnitOfWork` requires primary-configured repositories because its
transaction remains pinned to the primary.

## Resource lifecycle

Provider adapters can register `SQL_DATABASE_KEY` through Core's resource container. Prefer that
managed plugin path when using Core so shutdown closes the database resource. For manual adapter
registration, explicitly await `aclose()` in a `finally` block or use the adapter's supported
context manager. Do not share a database instance across event loops unless its provider explicitly
documents that behavior.

The registry accepts explicitly registered adapter objects; it does not search Python entry
points or import packages automatically. This keeps optional drivers out of applications that do
not install them.

## Failure and security handling

Adapters map driver failures to `DatabaseError` codes with provider-neutral messages. Do not log
raw SQL parameters or returned personal data. Bind values rather than interpolating them into SQL;
validate any dynamic identifier against a fixed allowlist. Provider credentials, transport TLS,
database permissions, and encryption at rest remain provider and deployment responsibilities.

## Validation boundary

The `orbit-sql` suite validates repository behavior and in-process compositions. It does not prove
database durability, backup/restore, failover, TLS, server permission configuration, or version
compatibility. Run each provider's documented tests against disposable services before release and
keep production data out of tests.
