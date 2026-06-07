"""Subject-company CIK extraction from a filing's SGML header (13D/13G join)."""

from __future__ import annotations

from app.edgar.header import parse_subject_cik

# A 13D filed BY Berkshire ABOUT Apple. The subject company's CIK (Apple) must
# win over the filer's CIK (Berkshire), regardless of section order.
HEADER_SUBJECT_FIRST = """<SEC-HEADER>0001067983-24-000123.hdr.sgml : 20240214
ACCESSION NUMBER:\t\t0001067983-24-000123
CONFORMED SUBMISSION TYPE:\tSC 13D
FILED AS OF DATE:\t\t20240214

SUBJECT COMPANY:

\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tAPPLE INC
\t\tCENTRAL INDEX KEY:\t\t\t0000320193

FILED BY:

\tCOMPANY DATA:
\t\tCOMPANY CONFORMED NAME:\t\t\tBERKSHIRE HATHAWAY INC
\t\tCENTRAL INDEX KEY:\t\t\t0001067983
</SEC-HEADER>
"""

HEADER_FILER_FIRST = """<SEC-HEADER>
FILED BY:
\tCOMPANY DATA:
\t\tCENTRAL INDEX KEY:\t\t\t0001067983

SUBJECT COMPANY:
\tCOMPANY DATA:
\t\tCENTRAL INDEX KEY:\t\t\t0000320193
</SEC-HEADER>
"""

HEADER_OLD_SGML = """<SUBMISSION>
<SUBJECT-COMPANY>
<COMPANY-DATA>
<CONFORMED-NAME>APPLE INC
<CIK>0000320193
</COMPANY-DATA>
</SUBJECT-COMPANY>
"""


def test_parses_subject_cik_when_listed_first():
    assert parse_subject_cik(HEADER_SUBJECT_FIRST) == "0000320193"


def test_picks_subject_not_filer_when_filer_listed_first():
    assert parse_subject_cik(HEADER_FILER_FIRST) == "0000320193"


def test_parses_old_sgml_cik_tag():
    assert parse_subject_cik(HEADER_OLD_SGML) == "0000320193"


def test_returns_none_without_subject_company():
    assert parse_subject_cik("ACCESSION NUMBER: 0000000000-00-000000\n") is None
