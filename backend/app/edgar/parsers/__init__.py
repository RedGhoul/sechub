"""Form-specific parsers.

Each parser operates on **raw document bytes/text** (no network), so it can be
unit-tested offline against committed sample filings. The ingest pipeline is
responsible for locating and fetching the right document within a filing.
"""
