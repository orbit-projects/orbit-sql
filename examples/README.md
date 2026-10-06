# Runnable Core and SQL example

This small Notes API demonstrates the actual package chain:

```text
Orbit Core (application, ASGI, lifecycle, resource ownership)
    → orbit-data (repository contract)
        → orbit-sql (typed SQL repository and SQL contract)
            → orbit-sql-sqlite (SQLite provider)
```

The application code lives in [`notes_app.py`](notes_app.py). It uses no ORM, separate web
framework, or PostgreSQL driver. SQLite is Core's local baseline; the PostgreSQL adapter remains
an optional package and is not required to run this example.

From the `orbit-sql` workspace, install the checked-out packages and Core's development host:

```bash
python -m pip install -e '../orbit-core[development-server]' -e ../orbit-data -e . -e ../orbit-sql-sqlite
python -m uvicorn notes_app:runtime --app-dir examples --reload
```

The default database is in-memory, so each process starts empty. To keep data in a local file, set
`ORBIT_NOTES_DB=notes.db`; choose a writable directory yourself because Core does not create
directories or select a production backup policy.

Create and list a note from another terminal:

```bash
curl -i -X POST http://127.0.0.1:8000/notes \
  -H 'Content-Type: application/json' \
  -d '{"id":1,"title":"First note"}'
curl http://127.0.0.1:8000/notes
```

The request and entity use a strict Pydantic model. Core owns resource lifecycle and closes the
SQLite worker during application shutdown; `orbit-sql-sqlite` owns the SQL connection and
`orbit-sql` owns repository mapping and bound SQL values. The sample has no authentication,
migrations, or production deployment policy. Keep it
on localhost; do not expose it publicly without adding the appropriate separately installed
security and deployment integrations.

The example is exercised by `tests/test_notes_example.py` using the separately installed
`orbit-testing` ASGI client. In the `orbit-sql` development checkout, install that workspace before
the package's development requirements, then run:

```bash
python -m pip install -e ../orbit-testing
python -m pip install -e '.[dev]'
python -m pytest tests/test_notes_example.py
```
