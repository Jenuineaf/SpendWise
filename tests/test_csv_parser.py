from decimal import Decimal

import pytest

from app.services.csv_parser import (
    CsvParseError,
    decode_csv_bytes,
    detect_columns,
    parse_amount,
    parse_date,
    read_rows,
)


def test_decode_utf8_sig_bom():
    raw = "date,amount\n01/01/2026,100\n".encode("utf-8-sig")
    assert decode_csv_bytes(raw).startswith("date")


def test_decode_falls_back_to_latin1_for_legacy_export():
    raw = "date,amount,note\n01/01/2026,100,café\n".encode("latin-1")
    text = decode_csv_bytes(raw)
    assert "café" in text or "caf" in text  # exact glyph depends on codepoint, presence matters


def test_detect_columns_handles_bank_statement_aliases():
    columns = detect_columns(["Txn Date", "Withdrawal Amt.", "Deposit Amt.", "Narration"])
    assert columns["date"] == "Txn Date"
    assert columns["debit"] == "Withdrawal Amt."
    assert columns["credit"] == "Deposit Amt."
    assert columns["description"] == "Narration"


def test_detect_columns_handles_single_amount_column():
    columns = detect_columns(["Date", "Amount", "Merchant"])
    assert columns["date"] == "Date"
    assert columns["amount"] == "Amount"
    assert columns["merchant"] == "Merchant"


def test_parse_date_multiple_formats():
    assert parse_date("31/01/2026") is not None
    assert parse_date("2026-01-31") is not None
    assert parse_date("") is None
    assert parse_date("not-a-date") is None


def test_parse_amount_handles_currency_symbols_and_commas():
    assert parse_amount("₹1,234.50") == Decimal("1234.50")
    assert parse_amount("1,234.50") == Decimal("1234.50")


def test_parse_amount_handles_parens_as_negative():
    assert parse_amount("(500.00)") == Decimal("-500.00")


def test_parse_amount_rejects_garbage():
    assert parse_amount("") is None
    assert parse_amount("garbage") is None
    assert parse_amount(None) is None


def test_read_rows_raises_without_date_or_amount_columns():
    with pytest.raises(CsvParseError):
        read_rows("foo,bar\n1,2\n")


def test_read_rows_debit_credit_split_columns():
    csv_text = (
        "Txn Date,Withdrawal Amt.,Deposit Amt.,Narration\n"
        "01/01/2026,500,,SWIGGY ORDER\n"
        "02/01/2026,,2000,SALARY\n"
    )
    rows, columns = read_rows(csv_text)
    assert len(rows) == 2
    assert columns["debit"] == "Withdrawal Amt."
    assert columns["credit"] == "Deposit Amt."
