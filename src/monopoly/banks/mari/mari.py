import re

from monopoly.banks.base import BankBase
from monopoly.config import StatementConfig
from monopoly.constants import EntryType
from monopoly.identifiers import TextIdentifier

from .statement import MariCreditStatement


class Mari(BankBase):
    """MariBank Singapore credit statements with signed SGD activity amounts."""

    name = "mari"

    credit = StatementConfig(
        currency="SGD",
        statement_type=EntryType.CREDIT,
        # The schema's period_end is the cycle end, not the next day's issue date.
        statement_date_pattern=re.compile(r"STATEMENT PERIOD:\s*\d{2} [A-Z]{3} \d{4}\s+to\s+(\d{2} [A-Z]{3} \d{4})"),
        period_start_pattern=re.compile(r"STATEMENT PERIOD:\s*(\d{2} [A-Z]{3} \d{4})"),
        account_pattern=re.compile(r"ACCOUNT:\s*(?P<account>[\d*]+)"),
        header_pattern=re.compile(r"POSTED DATE\s+TRANSACTION DATE\s+DESCRIPTION\s+AMOUNT \(SGD\)"),
        transaction_pattern=re.compile(
            r"^\s*(?P<posting_date>\d{2} [A-Z]{3})\s+"
            r"(?P<transaction_date>\d{2} [A-Z]{3})\s+"
            r"(?P<description>.*?)\s+(?P<amount>[+-][\d,]+\.\d{2})\s*$"
        ),
        transaction_date_format="%d %b",
        # Mari already prints '-' on purchases and '+' on repayments/refunds.
        transaction_auto_direction=False,
    )

    identifiers = [[TextIdentifier("MARI CREDIT CARD STATEMENT")]]
    statement_configs = [credit]
    statement_classes = {EntryType.CREDIT: MariCreditStatement}
