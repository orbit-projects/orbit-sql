# Orbit SQL: security

`orbit-sql` provides query and repository contracts, not a database connection or security
boundary. Each provider adapter and deployment configures credentials, transport, user permissions,
and storage protection. Read the chosen adapter's security guidance before deployment.

## Query safety

Bind all runtime values through the `SQLParameters` argument. Never interpolate request values into
SQL text. Placeholders bind values only; table names, column names, sort expressions, and other SQL
syntax must come from trusted configuration or a strict allowlist. `SQLRepository` validates its
configured identifiers, but direct `SQLDatabase.execute()` accepts caller-supplied SQL and does not
parse it for injection risks.

Use database accounts with only the permissions the application requires. Separate schema
migration credentials from runtime credentials when the provider supports that operational model.
Do not commit DSNs or passwords, and load them through a deployment secret manager. Configure and
verify TLS for remote providers; this contract package does not configure driver transport.

## Data and diagnostics

SQL results may contain confidential application data. Avoid writing raw query parameters, rows,
credential-bearing connection strings, or provider response bodies into logs, traces, metrics, or
exception reports. Provider adapters should translate driver errors to `DatabaseError` without
embedding secrets or raw SQL; application logging still must avoid adding sensitive context.

Use database-native encryption, encrypted volumes, access-controlled backups, and retention
policies according to the data classification. This package provides no encryption, backup, audit
trail, or deletion guarantees. `SQLRow` detaches values from the driver cursor but does not redact
them.

## Transaction safety

Use explicit transactions for multi-statement invariants. A cancellation or connection loss during
commit can leave the final outcome unknown. Do not blindly retry non-idempotent operations; use
idempotency keys, unique constraints, or reconciliation logic appropriate to the application.
Transactions provide atomicity as implemented by the selected database and its configuration; they
do not imply cross-database transactions or distributed consistency.

For vulnerability reporting, follow the repository [security policy](../../SECURITY.md). Do not
publish exploitable details in public issues.
