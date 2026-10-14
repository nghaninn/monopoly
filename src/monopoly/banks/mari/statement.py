"""Mari summary reconciliation against labelled activity totals."""

import re
from decimal import Decimal

from monopoly.statements import CreditStatement, SafetyCheckError


class MariCreditStatement(CreditStatement):
    def process_match(self, match, context):
        # pdftotext places Mari's merchant on the line immediately above the
        # date/amount row in some PDFs, and inline in others.
        if not match.description.strip():
            previous = context.lines[context.idx - 1].strip() if context.idx else ""
            if not previous or previous.startswith("-") or "DATE" in previous:
                msg = "Mari transaction description is missing"
                raise SafetyCheckError(msg)
            match.description = previous
        if context.idx + 1 < len(context.lines):
            detail = context.lines[context.idx + 1].strip()
            if detail in {"Instant Checkout", "Repayment"}:
                match.description += f" {detail}"
        return match

    def perform_safety_check(self) -> bool:
        # Mari's fixed nine-column summary is distinct from the account summary
        # and disclosure examples. Never reconcile against arbitrary row amounts.
        text = "\n".join(page.raw_text for page in self.pages)
        if "STATEMENT SUMMARY" not in text or "All values in STATEMENT SUMMARY" not in text:
            msg = "Mari statement summary is missing"
            raise SafetyCheckError(msg)
        summary = text.split("STATEMENT SUMMARY", 1)[-1].split("All values", 1)[0]
        values = re.findall(r"(?<![\d.])[\d,]+\.\d{2}(?!\d)", summary)
        if len(values) != 9:  # noqa: PLR2004
            msg = "Unsupported Mari statement summary layout"
            raise SafetyCheckError(msg)
        totals = [Decimal(value.replace(",", "")) for value in values]
        debits = -sum((Decimal(str(tx.amount)) for tx in self.transactions if tx.amount < 0), Decimal(0))
        credit_total = sum((Decimal(str(tx.amount)) for tx in self.transactions if tx.amount > 0), Decimal(0))
        expected_debits = sum((totals[i] for i in (3, 4, 6, 7)), Decimal(0))
        expected_credits = sum((totals[i] for i in (1, 2, 5)), Decimal(0))
        if (
            debits != expected_debits
            or credit_total != expected_credits
            or totals[0] + expected_debits - expected_credits != totals[8]
        ):
            msg = "Mari activity totals do not reconcile with the statement summary"
            raise SafetyCheckError(msg)
        return True
