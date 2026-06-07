"""Locate the relevant document(s) within a filing via its ``index.json``.

A single EDGAR filing is a directory of documents. We list it once and pick the
right file per form type rather than guessing filenames.
"""

from __future__ import annotations

from functools import lru_cache

from app.edgar.client import edgar_client
from app.edgar.common import filing_dir_url, filing_index_json_url

# A single filing triggers several ``find_*`` calls (e.g. 13F looks up both the
# primary doc and the information table), each of which would otherwise re-fetch
# the same ``index.json``. Memoizing the listing collapses those into one rate-
# limited request per filing. The cache is keyed on (cik, accession) and a small
# bound is plenty since documents are located right after discovery.
@lru_cache(maxsize=512)
def _list_documents_cached(cik: str, accession: str) -> tuple[dict, ...]:
    data = edgar_client.get_json(filing_index_json_url(cik, accession))
    return tuple(data.get("directory", {}).get("item", []))


def list_documents(cik: str, accession: str) -> list[dict]:
    """Return ``[{name, type, ...}]`` for every document in the filing.

    The underlying ``index.json`` fetch is memoized per (cik, accession) so the
    several locators run for one filing share a single EDGAR request.
    """
    return list(_list_documents_cached(cik, accession))


def doc_url(cik: str, accession: str, name: str) -> str:
    return f"{filing_dir_url(cik, accession)}/{name}"


def find_information_table(cik: str, accession: str) -> str | None:
    """URL of the 13F information-table XML, or None."""
    items = list_documents(cik, accession)
    xmls = [d["name"] for d in items if d.get("name", "").lower().endswith(".xml")]
    # Prefer files whose name signals an info table; never the cover doc.
    for name in xmls:
        low = name.lower()
        if "primary_doc" in low:
            continue
        if "infotable" in low.replace("_", "") or "table" in low or "form13f" in low:
            return doc_url(cik, accession, name)
    # Fallback: the first non-cover XML.
    for name in xmls:
        if "primary_doc" not in name.lower():
            return doc_url(cik, accession, name)
    return None


def find_primary_doc(cik: str, accession: str) -> str | None:
    items = list_documents(cik, accession)
    for d in items:
        if d.get("name", "").lower() == "primary_doc.xml":
            return doc_url(cik, accession, d["name"])
    return None


def find_ownership_xml(cik: str, accession: str) -> str | None:
    """The Form 3/4/5 ownership XML (an .xml that isn't primary_doc)."""
    items = list_documents(cik, accession)
    for d in items:
        name = d.get("name", "")
        low = name.lower()
        if low.endswith(".xml") and "primary_doc" not in low:
            return doc_url(cik, accession, name)
    return None


def find_primary_html(cik: str, accession: str) -> str | None:
    """The main HTML/text document — used for 13D/13G cover-page parsing."""
    items = list_documents(cik, accession)
    candidates = [
        d for d in items if d.get("name", "").lower().endswith((".htm", ".html", ".txt"))
    ]
    if not candidates:
        return None
    # The primary doc is typically the largest HTML document.
    candidates.sort(key=lambda d: int(d.get("size", 0) or 0), reverse=True)
    return doc_url(cik, accession, candidates[0]["name"])
