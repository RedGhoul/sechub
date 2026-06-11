"""Raw psycopg connection helpers.

The whole app talks to Postgres through plain SQL over psycopg3 connections —
there's no ORM. Queries return ``dict`` rows (``row_factory=dict_row``) and
writes use ``INSERT ... RETURNING`` for generated ids. Schema changes live as
raw ``.sql`` files under ``migrations/`` and are applied by ``app.migrate``.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings


def dsn() -> str:
    """The libpq DSN for the configured database.

    ``DATABASE_URL`` keeps the SQLAlchemy-style ``postgresql+psycopg://`` form
    for backwards compatibility; libpq/psycopg wants a plain ``postgresql://``
    URL, so strip any ``+driver`` suffix from the scheme.
    """
    url = settings.database_url
    scheme, sep, rest = url.partition("://")
    if sep and "+" in scheme:
        scheme = scheme.split("+", 1)[0]
    return f"{scheme}{sep}{rest}"


def connect() -> psycopg.Connection:
    """Open a new standalone connection with dict rows.

    Used by the long-lived single-connection callers (worker, backfill, CLI)
    that own their connection's lifecycle. The API uses the pool below instead.
    """
    return psycopg.connect(dsn(), row_factory=dict_row)


# Lazily-built so importing this module (e.g. in the worker) never opens a pool.
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """The process-wide connection pool backing the API request path."""
    global _pool
    if _pool is None:
        pool = ConnectionPool(
            dsn(),
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=10,
            open=False,
        )
        pool.open()
        _pool = pool
    return _pool


def close_pool() -> None:
    """Close the pool on shutdown (FastAPI lifespan). Safe if never opened."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_connection() -> Iterator[psycopg.Connection]:
    """FastAPI dependency that yields a pooled, request-scoped connection.

    The pool hands back a clean connection and reclaims it on exit; read
    endpoints never commit, so the (empty) transaction is rolled back when the
    connection is returned to the pool.
    """
    with get_pool().connection() as conn:
        yield conn
