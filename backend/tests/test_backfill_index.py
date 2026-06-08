"""Full-index parsing and quarter-range generation for the backfill."""

from __future__ import annotations

from datetime import date

from app.edgar.full_index import EDGAR_EPOCH_YEAR, quarters_in_range
from app.edgar.index_parse import parse_form_index

SAMPLE_IDX = """Description:           Master Index of EDGAR Dissemination Feed by Form Type

Form Type    Company Name                          CIK         Date Filed   File Name
---------------------------------------------------------------------------------------
13F-HR       BERKSHIRE HATHAWAY INC                1067983     2024-02-14   edgar/data/1067983/0000950123-24-012345.txt
13F-HR/A     SOME FUND LLC                         1234567     2024-02-15   edgar/data/1234567/0000950123-24-099999.txt
4            DOE JOHN                              7654321     2024-02-16   edgar/data/7654321/0000950123-24-088888.txt
8-K          IGNORED CORP                          9999999     2024-02-17   edgar/data/9999999/0000950123-24-077777.txt
"""


def test_parse_filters_to_requested_forms_and_amendments():
    refs = parse_form_index(SAMPLE_IDX, {"13F-HR"})
    # The base 13F-HR and its /A amendment both match; Form 4 and 8-K do not.
    assert {r.form_type for r in refs} == {"13F-HR", "13F-HR/A"}


def test_parse_extracts_fields():
    [ref] = parse_form_index(SAMPLE_IDX, {"4"})
    assert ref.cik == "0007654321"  # zero-padded to 10
    assert ref.accession_no == "0000950123-24-088888"
    assert ref.filer_name == "DOE JOHN"
    assert ref.filed_at == date(2024, 2, 16)


def test_parse_ignores_unrequested_forms():
    assert parse_form_index(SAMPLE_IDX, {"NPORT-P"}) == []


def test_quarters_in_range_bounds_to_until():
    # Through May 2024 -> Q1 and Q2 only (Q3 starts in July).
    qs = quarters_in_range(2024, until=date(2024, 5, 1))
    assert qs == [(2024, 1), (2024, 2)]


def test_quarters_in_range_clamps_to_edgar_epoch():
    qs = quarters_in_range(1980, until=date(1993, 12, 31))
    assert qs[0] == (EDGAR_EPOCH_YEAR, 1)
    assert qs[-1] == (1993, 4)
