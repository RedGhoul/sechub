"""Best-effort parser for Schedule 13D / 13G beneficial-ownership filings.

These schedules have **no standardized structured table** — the primary
document is HTML/text laid out as a "cover page". We extract the issuer name,
CUSIP, aggregate shares, and percent-of-class with regexes against the
text-stripped document. Expect lower fidelity than 13F/Form 4; missing fields
are returned as ``None`` rather than guessed.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from lxml import html as lxml_html

from app.edgar.parsers.dto import SecurityRef, StakeFiling

_CUSIP_RE = re.compile(r"CUSIP\s*(?:No\.?|Number)?\s*[:\-]?\s*([0-9A-Z]{6,9})", re.I)
# Lazily skip past row labels like "(11)" to the number that precedes the "%".
_PCT_RE = re.compile(
    r"Percent\s+of\s+[Cc]lass[^%]{0,80}?([0-9]{1,3}(?:\.[0-9]+)?)\s*%", re.I
)
_SHARES_RE = re.compile(
    r"(?:Aggregate\s+[Aa]mount[^0-9]{0,60}|Aggregate\s+[Nn]umber[^0-9]{0,60})"
    r"([0-9][0-9,]{3,})",
)
_DATE_RE = re.compile(
    r"Date\s+of\s+Event[^0-9]{0,60}([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})", re.I
)


def parse(raw: bytes | str, *, form_type: str, issuer_hint: str = "") -> StakeFiling:
    text = _to_text(raw)

    cusip_match = _CUSIP_RE.search(text)
    cusip = cusip_match.group(1).upper()[:9] if cusip_match else ""

    pct_match = _PCT_RE.search(text)
    percent = float(pct_match.group(1)) if pct_match else None

    shares_match = _SHARES_RE.search(text)
    shares = int(shares_match.group(1).replace(",", "")) if shares_match else None

    return StakeFiling(
        issuer=SecurityRef(cusip=cusip, name=_issuer_name(text) or issuer_hint),
        percent_of_class=percent,
        shares=shares,
        event_date=_event_date(text),
        # 13D = active intent (activist); 13G = passive.
        is_activist=form_type.upper().startswith("SC 13D") or form_type.upper() == "13D",
    )


def _to_text(raw: bytes | str) -> str:
    data = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw
    if "<" in data and ">" in data:
        try:
            return lxml_html.fromstring(data).text_content()
        except Exception:
            return data
    return data


def _issuer_name(text: str) -> str | None:
    m = re.search(r"Name\s+of\s+Issuer[:\s\-]*\n?\s*([A-Z][^\n]{2,80})", text, re.I)
    return m.group(1).strip() if m else None


def _event_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
