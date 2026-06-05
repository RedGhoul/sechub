"""Locate the relevant document(s) within a filing via its ``index.json``.

A single EDGAR filing is a directory of documents. We list it once and pick the
right file per form type rather than guessing filenames.
"""

from __future__ import annotations

from app.edgar.client import edgar_client
from app.edgar.common import filing_dir_url, filing_index_json_url


def list_documents(cik: str, accession: str) -> list[dict]:
    """Return ``[{name, type, ...}]`` for every document in the filing."""
    data = edgar_client.get_json(filing_index_json_url(cik, accession))
    return data.get("directory", {}).get("item", [])


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
