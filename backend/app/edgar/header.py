"""Recover a filing's subject company (the issuer) from its SGML header.

13D/13G cover pages don't expose the issuer's CIK, but every EDGAR submission
has a machine-readable header that names the ``SUBJECT COMPANY`` (the issuer the
schedule is about) separately from who ``FILED BY`` it (the beneficial owner).
We read the small ``-index-headers.html`` file and pull the subject company's
CIK so a stake can be joined to its issuer exactly, instead of by name.

Best-effort: if the header is missing or unparseable (e.g. very old filings),
callers fall back to CUSIP/name resolution.
"""

from __future__ import annotations

import re

from app.edgar.client import edgar_client
from app.edgar.common import filing_dir_url, format_cik

# Anchor on the SUBJECT COMPANY section, then take the first CIK after it so we
# never pick up the FILED BY (beneficial owner) block by mistake.
_SUBJECT_RE = re.compile(r"SUBJECT[\s-]+COMPANY", re.I)
_CIK_LABEL_RE = re.compile(r"CENTRAL\s+INDEX\s+KEY\s*:?\s*([0-9]{1,10})", re.I)
# Old EDGAR SGML uses opening-only tags: "<CIK>0000320193" with no closing tag.
_CIK_TAG_RE = re.compile(r"<CIK>\s*([0-9]{1,10})", re.I)


def index_headers_url(cik: str, accession: str) -> str:
    return f"{filing_dir_url(cik, accession)}/{accession}-index-headers.html"


def parse_subject_cik(header_text: str) -> str | None:
    """Extract the SUBJECT COMPANY's CIK from a filing's SGML header text."""
    anchor = _SUBJECT_RE.search(header_text)
    if anchor is None:
        return None
    tail = header_text[anchor.end():]
    match = _CIK_LABEL_RE.search(tail) or _CIK_TAG_RE.search(tail)
    return format_cik(match.group(1)) if match else None


def fetch_subject_cik(cik: str, accession: str) -> str | None:
    """Fetch and parse a filing's header; return the issuer CIK or ``None``."""
    try:
        text = edgar_client.get_text(index_headers_url(cik, accession))
    except Exception:
        return None
    return parse_subject_cik(text)
