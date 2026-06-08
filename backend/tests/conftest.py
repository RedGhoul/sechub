"""Shared test fixtures.

The test suite is intentionally offline: the parser tests run against sample
filings on disk and need no database. DB-backed behavior is exercised against a
real Postgres via the migration runner, not in unit tests.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
