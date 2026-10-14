"""Mari's signed activity layout and reconciliation, using synthetic data only."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_utils.transactions import read_pages

from monopoly.banks import BankDetector, Mari, banks
from monopoly.identifiers import MetadataIdentifier
from monopoly.pdf import PdfPage, PdfParser
from monopoly.pipeline import Pipeline
from monopoly.statements import CreditStatement, SafetyCheckError

FIXTURE = Path(__file__).parent / "mari" / "credit"


def test_detection_and_cycle_metadata():
    pages = read_pages(FIXTURE)
    detector = BankDetector(
        SimpleNamespace(raw_text="MARI CREDIT CARD STATEMENT", metadata_identifier=MetadataIdentifier())
    )
    assert detector.detect_bank(banks) is Mari
    pipeline = Pipeline(PdfParser.from_pages(Mari, pages))
    statement = pipeline.extract()
    assert statement.statement_date == datetime(2025, 1, 20)
    assert statement.period_start == datetime(2024, 12, 21)
    rows = pipeline.transform(statement)
    assert [(t.date, t.posting_date, t.amount) for t in rows] == [
        ("2024-12-27", "2024-12-27", 20),
        ("2024-12-31", "2025-01-02", -50),
        ("2025-01-04", "2025-01-05", -25),
    ]
    assert all(t.account == "1234" and t.currency == "SGD" for t in rows)


@pytest.mark.parametrize("amount, expected", [("-1,234.56", -1234.56), ("+12.50", 12.50), ("-0.00", 0)])
def test_explicit_amount_sign(amount, expected):
    statement = CreditStatement([PdfPage(f"05 JAN  04 JAN  SYNTHETIC MERCHANT  {amount}")], "mari", Mari.credit, "")
    tx = statement.get_transactions()[0]
    assert tx.amount == expected
    assert tx.posting_date == "05 JAN"
    assert tx.date == "04 JAN"


def test_missing_purchase_fails_reconciliation():
    pages = read_pages(FIXTURE)
    pages[1] = pages[1].replace("05 JAN        04 JAN            EXAMPLE GROCER                        -25.00", "")
    with pytest.raises(SafetyCheckError):
        Pipeline(PdfParser.from_pages(Mari, pages)).extract()


def test_summary_and_section_headings_are_not_transactions():
    text = "-Purchase-\nCURRENT OUTSTANDING -10.00\n05 JAN 04 JAN MERCHANT -10.00\n-Refund-\n"
    statement = CreditStatement([PdfPage(text)], "mari", Mari.credit, "")
    assert len(statement.get_transactions()) == 1


def test_summary_missing_or_unknown_layout_fails_closed():
    pages = read_pages(FIXTURE)
    pages[0] = pages[0].replace("STATEMENT SUMMARY", "UNSUPPORTED SUMMARY")
    with pytest.raises(SafetyCheckError):
        Pipeline(PdfParser.from_pages(Mari, pages)).extract()


def test_missing_merchant_is_rejected():
    from monopoly.banks.mari.statement import MariCreditStatement

    statement = MariCreditStatement([PdfPage("-Purchase-\n05 JAN 04 JAN          -10.00")], "mari", Mari.credit, "")
    with pytest.raises(SafetyCheckError):
        statement.get_transactions()


def test_positive_refund_and_negative_fee_reconcile():
    text = """STATEMENT PERIOD: 21 DEC 2024 to 20 JAN 2025
STATEMENT SUMMARY
0.00 0.00 5.00 10.00 0.00 0.00 2.00 0.00 7.00
All values in STATEMENT SUMMARY are denoted in SGD
POSTED DATE TRANSACTION DATE DESCRIPTION AMOUNT (SGD)
05 JAN 04 JAN SYNTHETIC PURCHASE -10.00
06 JAN 05 JAN SYNTHETIC REFUND +5.00
07 JAN 06 JAN SYNTHETIC FEE -2.00
"""
    statement = Pipeline(PdfParser.from_pages(Mari, [text])).extract()
    assert [tx.amount for tx in statement.transactions] == [-10, 5, -2]
