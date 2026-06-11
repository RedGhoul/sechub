"""Quarter-over-quarter 13F diff: classify each position as NEW/ADD/TRIM/EXIT/HOLD.

When a new 13F is ingested we compare the filer's positions for the new period
against their most recent *prior* period and write ``holding_change`` rows. These
power the "what did they buy/sell this quarter" view.
"""

from __future__ import annotations

from datetime import date

import psycopg


def _positions_for_period(
    conn: psycopg.Connection, filer_id: int, period: date
) -> dict[int, tuple[int, int]]:
    """Map security_id -> (shares, value) for the filer's *latest* 13F filing for
    ``period``.

    A 13F-HR/A amendment re-files under the same period; the common
    "restatement" type re-states the full information table, so summing across
    every filing for the period would double every position (and emit bogus ADD
    rows). We therefore read only the most recently filed table that actually
    carries holdings."""
    rows = conn.execute(
        """SELECT h.security_id, h.shares, h.value
             FROM holding h
            WHERE h.filing_id = (
                  SELECT f.id
                    FROM filing f
                   WHERE f.filer_id = %s AND f.period_of_report = %s
                     AND EXISTS (SELECT 1 FROM holding hx WHERE hx.filing_id = f.id)
                   ORDER BY f.filed_at DESC, f.id DESC
                   LIMIT 1
            )""",
        (filer_id, period),
    ).fetchall()
    agg: dict[int, tuple[int, int]] = {}
    for r in rows:
        cur = agg.get(r["security_id"], (0, 0))
        agg[r["security_id"]] = (cur[0] + (r["shares"] or 0), cur[1] + (r["value"] or 0))
    return agg


def _prior_period(conn: psycopg.Connection, filer_id: int, period: date) -> date | None:
    row = conn.execute(
        """SELECT period_of_report
             FROM filing
            WHERE filer_id = %s
              AND form_type LIKE '13F%%'
              AND period_of_report < %s
              AND period_of_report IS NOT NULL
            ORDER BY period_of_report DESC
            LIMIT 1""",
        (filer_id, period),
    ).fetchone()
    return row["period_of_report"] if row else None


def compute_changes(conn: psycopg.Connection, filer_id: int, period: date) -> int:
    """(Re)compute holding_change rows for one filer+period. Returns row count."""
    prior = _prior_period(conn, filer_id, period)
    current = _positions_for_period(conn, filer_id, period)
    previous = _positions_for_period(conn, filer_id, prior) if prior else {}

    # Clear any prior computation for idempotency.
    conn.execute(
        "DELETE FROM holding_change WHERE filer_id = %s AND period = %s",
        (filer_id, period),
    )

    rows: list[tuple] = []
    for sec_id in set(current) | set(previous):
        cur_shares, cur_value = current.get(sec_id, (0, 0))
        prev_shares, prev_value = previous.get(sec_id, (0, 0))
        action = _classify(prev_shares, cur_shares)
        if action == "HOLD" and cur_shares == prev_shares:
            continue  # nothing changed; skip noise
        pct = None
        if prev_shares:
            pct = round((cur_shares - prev_shares) / prev_shares * 100, 4)
        rows.append(
            (
                filer_id,
                sec_id,
                period,
                prior,
                action,
                cur_shares - prev_shares,
                cur_value - prev_value,
                pct,
            )
        )

    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO holding_change
                   (filer_id, security_id, period, prev_period, action,
                    shares_delta, value_delta, pct_change)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                rows,
            )
    return len(rows)


def _classify(prev_shares: int, cur_shares: int) -> str:
    if prev_shares == 0 and cur_shares > 0:
        return "NEW"
    if cur_shares == 0 and prev_shares > 0:
        return "EXIT"
    if cur_shares > prev_shares:
        return "ADD"
    if cur_shares < prev_shares:
        return "TRIM"
    return "HOLD"
