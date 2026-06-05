"""Shared EDGAR URL helpers and small parsing utilities."""

from __future__ import annotations

ARCHIVES = "https://www.sec.gov/Archives/edgar"
DATA = "https://data.sec.gov"


def format_cik(cik: str | int) -> str:
    """Zero-pad a CIK to the 10-digit form EDGAR uses in paths/filenames.

    Accepts ``1067983``, ``"0001067983"``, or ``"CIK0001067983"``.
    """
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    return digits.zfill(10)


def submissions_url(cik: str | int) -> str:
    return f"{DATA}/submissions/CIK{format_cik(cik)}.json"


def accession_no_dashless(accession: str) -> str:
    return accession.replace("-", "")


def filing_dir_url(cik: str | int, accession: str) -> str:
    """Directory holding a filing's documents."""
    return f"{ARCHIVES}/data/{int(format_cik(cik))}/{accession_no_dashless(accession)}"


def filing_index_json_url(cik: str | int, accession: str) -> str:
    """JSON listing of every document in a filing (filenames + types)."""
    return f"{filing_dir_url(cik, accession)}/index.json"
