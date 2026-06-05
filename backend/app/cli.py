"""Small operational CLI: ``python -m app.cli <command>``.

Commands
--------
ingest-filer <cik> [--forms 13F-HR,4] [--limit N]
    Pull and ingest a specific filer's recent filings.
backfill [--forms ...] [--days N]
    Backfill recent days from the EDGAR daily index.
"""

from __future__ import annotations

import argparse
import logging

from app.config import settings
from app.db import SessionLocal
from app.edgar.feed import fetch_filer_history
from app.edgar.indexes import fetch_recent_days
from app.ingest.pipeline import ingest_filing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _ingest_filer(args: argparse.Namespace) -> None:
    wanted = {f.strip() for f in args.forms.split(",") if f.strip()}
    db = SessionLocal()
    count = 0
    try:
        refs = fetch_filer_history(args.cik, forms=wanted)[: args.limit]
        print(f"found {len(refs)} matching filings for CIK {args.cik}")
        for ref in refs:
            if ingest_filing(db, ref) is not None:
                count += 1
    finally:
        db.close()
    print(f"ingested {count} new filings")


def _backfill(args: argparse.Namespace) -> None:
    forms = {f.strip() for f in args.forms.split(",") if f.strip()} or set(settings.watch_forms)
    db = SessionLocal()
    count = 0
    try:
        refs = fetch_recent_days(forms, days=args.days)
        print(f"found {len(refs)} filings across last {args.days} day(s)")
        for ref in refs:
            if ingest_filing(db, ref) is not None:
                count += 1
    finally:
        db.close()
    print(f"ingested {count} new filings")


def main() -> None:
    parser = argparse.ArgumentParser(prog="sechub")
    sub = parser.add_subparsers(dest="command", required=True)

    p_filer = sub.add_parser("ingest-filer", help="ingest a CIK's recent filings")
    p_filer.add_argument("cik")
    p_filer.add_argument("--forms", default="13F-HR")
    p_filer.add_argument("--limit", type=int, default=4)
    p_filer.set_defaults(func=_ingest_filer)

    p_back = sub.add_parser("backfill", help="backfill recent days from the daily index")
    p_back.add_argument("--forms", default="")
    p_back.add_argument("--days", type=int, default=3)
    p_back.set_defaults(func=_backfill)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
