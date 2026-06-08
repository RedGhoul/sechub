"""Raw-SQL migration runner.

Applies the ``.sql`` files under ``migrations/`` in filename order, recording
each one in a ``schema_migrations`` table (version + applied-at timestamp) so a
re-run only applies what's new. Each migration runs in its own transaction —
Postgres DDL is transactional, so a failing migration leaves nothing behind.

Run with::

    python -m app.migrate            # apply all pending migrations
    python -m app.migrate --status   # show applied vs pending, apply nothing
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import psycopg

from app.db import connect

log = logging.getLogger("sechub.migrate")

# migrations/ sits next to the app package (backend/migrations).
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _applied_versions(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r["version"] for r in rows}


def _ensure_tracking_table(conn: psycopg.Connection) -> None:
    conn.execute(_CREATE_TRACKING_TABLE)


def _connect() -> psycopg.Connection:
    """A connection in autocommit mode.

    Each migration manages its own transaction via ``conn.transaction()``; that
    only opens a real (committing) transaction block when no implicit one is
    already in progress, so autocommit keeps the reads in ``pending()`` from
    leaving a transaction open that would turn the migration blocks into
    savepoints and silently roll them back.
    """
    conn = connect()
    conn.autocommit = True
    return conn


def pending(conn: psycopg.Connection) -> list[Path]:
    """Migration files not yet recorded in ``schema_migrations``."""
    _ensure_tracking_table(conn)
    applied = _applied_versions(conn)
    return [p for p in _migration_files() if p.name not in applied]


def migrate() -> list[str]:
    """Apply every pending migration. Returns the versions applied this run."""
    conn = _connect()
    applied: list[str] = []
    try:
        for path in pending(conn):
            version = path.name
            sql = path.read_text()
            log.info("applying migration %s", version)
            # One transaction per migration: the DDL and its bookkeeping row
            # commit together or not at all.
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied.append(version)
    finally:
        conn.close()
    if applied:
        log.info("applied %d migration(s): %s", len(applied), ", ".join(applied))
    else:
        log.info("database is up to date; nothing to apply")
    return applied


def _print_status() -> None:
    conn = _connect()
    try:
        _ensure_tracking_table(conn)
        applied = _applied_versions(conn)
        for path in _migration_files():
            mark = "applied" if path.name in applied else "pending"
            print(f"[{mark}] {path.name}")
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="migrate", description="Apply raw-SQL migrations.")
    parser.add_argument(
        "--status", action="store_true", help="show applied/pending migrations and exit"
    )
    args = parser.parse_args()
    if args.status:
        _print_status()
    else:
        migrate()


if __name__ == "__main__":
    main()
