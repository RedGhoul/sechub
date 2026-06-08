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
    """Open a new connection with dict rows. The caller owns its lifecycle."""
    return psycopg.connect(dsn(), row_factory=dict_row)


def get_connection() -> Iterator[psycopg.Connection]:
    """FastAPI dependency that yields a request-scoped connection.

    Read endpoints never commit; psycopg rolls back the (empty) transaction
    when the connection closes.
    """
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
