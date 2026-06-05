"""Discover new filings: the real-time ``getcurrent`` feed and per-filer history.

These functions only *discover* filings (returning lightweight refs); fetching
and parsing the documents happens in the ingest pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from lxml import etree

from app.edgar.client import edgar_client
from app.edgar.common import format_cik, submissions_url

BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass(frozen=True)
class FilingRef:
    """A discovered filing, before its documents are fetched."""

    cik: str
    filer_name: str
    accession_no: str
    form_type: str
    filed_at: date


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(value[: len(fmt) + 2].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def fetch_recent(form_type: str, count: int = 100) -> list[FilingRef]:
    """Poll the EDGAR real-time feed for the most recent filings of a type.

    Uses ``browse-edgar?action=getcurrent`` which lists filings as they hit
    EDGAR — this is how SecHub sees filings "as soon as they come out".
    """
    url = (
        f"{BROWSE}?action=getcurrent&type={form_type}"
        f"&company=&dateb=&owner=include&count={count}&output=atom"
    )
    return _parse_current_atom(edgar_client.get_bytes(url))


def _parse_current_atom(raw: bytes) -> list[FilingRef]:
    root = etree.fromstring(raw)
    refs: list[FilingRef] = []
    for entry in root.findall("a:entry", _ATOM_NS):
        title = entry.findtext("a:title", default="", namespaces=_ATOM_NS) or ""
        updated = entry.findtext("a:updated", default="", namespaces=_ATOM_NS)
        link_el = entry.find("a:link", _ATOM_NS)
        href = link_el.get("href") if link_el is not None else ""

        # getcurrent titles look like: "13F-HR - BERKSHIRE HATHAWAY INC (0001067983) (Filer)"
        form_type = title.split(" - ", 1)[0].strip() if " - " in title else ""
        cik = _cik_from_href(href)
        accession = _accession_from_href(href)
        name = _name_from_title(title)
        if not accession:
            continue
        refs.append(
            FilingRef(
                cik=cik,
                filer_name=name,
                accession_no=accession,
                form_type=form_type,
                filed_at=_parse_date(updated) or date.today(),
            )
        )
    return refs


def _cik_from_href(href: str) -> str:
    # .../data/1067983/000095012324012345/0000950123-24-012345-index.htm
    parts = href.split("/data/")
    if len(parts) > 1:
        return format_cik(parts[1].split("/")[0])
    return ""


def _accession_from_href(href: str) -> str:
    for token in href.split("/"):
        if token.endswith("-index.htm") or token.endswith("-index.html"):
            return token.rsplit("-index", 1)[0]
    return ""


def _name_from_title(title: str) -> str:
    if " - " not in title:
        return title.strip()
    rest = title.split(" - ", 1)[1]
    # strip trailing "(CIK) (Filer)" decorations
    return rest.split(" (")[0].strip()


def fetch_filer_history(cik: str, forms: set[str] | None = None) -> list[FilingRef]:
    """All recent filings for one CIK from the submissions JSON API.

    Optionally filtered to ``forms``. Used for targeted per-filer ingestion
    (e.g. "pull Berkshire's latest 13F").
    """
    data = edgar_client.get_json(submissions_url(cik))
    name = data.get("name", "")
    recent = data.get("filings", {}).get("recent", {})
    accessions = recent.get("accessionNumber", [])
    form_types = recent.get("form", [])
    dates = recent.get("filingDate", [])

    refs: list[FilingRef] = []
    for acc, form, filed in zip(accessions, form_types, dates):
        if forms and form not in forms:
            continue
        refs.append(
            FilingRef(
                cik=format_cik(cik),
                filer_name=name,
                accession_no=acc,
                form_type=form,
                filed_at=_parse_date(filed) or date.today(),
            )
        )
    return refs
