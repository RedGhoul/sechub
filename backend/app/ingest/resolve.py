"""Get-or-create helpers for the shared Filer and Security entities.

Centralized so every parser/pipeline path dedupes identically. Securities are
keyed by the best identifier available (CUSIP > ticker > issuer CIK). Each
helper returns the row as a plain ``dict``.
"""

from __future__ import annotations

import psycopg

from app.edgar.parsers.dto import SecurityRef


def get_or_create_filer(
    conn: psycopg.Connection, cik: str, name: str, kind: str = "institution"
) -> dict:
    filer = conn.execute("SELECT * FROM filer WHERE cik = %s", (cik,)).fetchone()
    if filer is None:
        return conn.execute(
            "INSERT INTO filer (cik, name, kind) VALUES (%s, %s, %s) RETURNING *",
            (cik, name or cik, kind),
        ).fetchone()
    if name and filer["name"] != name:
        filer = conn.execute(
            "UPDATE filer SET name = %s WHERE id = %s RETURNING *", (name, filer["id"])
        ).fetchone()
    return filer


def _security_key(ref: SecurityRef, ticker: str | None, issuer_cik: str | None) -> str:
    if ref.cusip:
        return ref.cusip
    if ticker:
        return f"TICKER:{ticker}"
    if issuer_cik:
        return f"CIK:{issuer_cik}"
    # Last resort: name-based, so distinct unnamed issuers don't collapse.
    return f"NAME:{ref.name[:24]}"


def get_or_create_security(
    conn: psycopg.Connection,
    ref: SecurityRef,
    *,
    ticker: str | None = None,
    issuer_cik: str | None = None,
) -> dict:
    key = _security_key(ref, ticker, issuer_cik)
    sec = conn.execute("SELECT * FROM security WHERE key = %s", (key,)).fetchone()
    if sec is None:
        return conn.execute(
            """INSERT INTO security (key, cusip, name, ticker, issuer_cik)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (key, ref.cusip or None, ref.name or key, ticker, issuer_cik),
        ).fetchone()

    # Enrich a thin existing row when a richer filing arrives.
    updates: dict[str, str] = {}
    if ticker and not sec["ticker"]:
        updates["ticker"] = ticker
    if ref.cusip and not sec["cusip"]:
        updates["cusip"] = ref.cusip
    if issuer_cik and not sec["issuer_cik"]:
        updates["issuer_cik"] = issuer_cik
    if ref.name and (not sec["name"] or sec["name"] == key):
        updates["name"] = ref.name
    if updates:
        assignments = ", ".join(f"{col} = %s" for col in updates)
        sec = conn.execute(
            f"UPDATE security SET {assignments} WHERE id = %s RETURNING *",
            (*updates.values(), sec["id"]),
        ).fetchone()
    return sec
