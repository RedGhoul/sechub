"""EDGAR URL builders and CIK normalization (pure, no network/DB)."""

from __future__ import annotations

from app.edgar.common import (
    accession_no_dashless,
    filing_dir_url,
    filing_index_json_url,
    format_cik,
    submissions_url,
)


def test_format_cik_zero_pads_plain_integer():
    assert format_cik(1067983) == "0001067983"


def test_format_cik_keeps_already_padded_string():
    assert format_cik("0001067983") == "0001067983"


def test_format_cik_strips_cik_prefix_and_nondigits():
    assert format_cik("CIK0001067983") == "0001067983"
    assert format_cik("0001067983 ") == "0001067983"


def test_accession_no_dashless_removes_dashes():
    assert accession_no_dashless("0000950123-24-012345") == "000095012324012345"


def test_submissions_url_uses_data_host_and_padded_cik():
    assert submissions_url(1067983) == "https://data.sec.gov/submissions/CIK0001067983.json"


def test_filing_dir_url_uses_unpadded_cik_in_path():
    # EDGAR's Archives path uses the *integer* CIK (no leading zeros) plus the
    # dashless accession number.
    url = filing_dir_url("0001067983", "0000950123-24-012345")
    assert url == ("https://www.sec.gov/Archives/edgar/data/1067983/000095012324012345")


def test_filing_index_json_url_appends_index_json():
    url = filing_index_json_url(1067983, "0000950123-24-012345")
    assert url.endswith("/000095012324012345/index.json")
