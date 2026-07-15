import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

DATE_HEADERS = {"date", "txn date", "transaction date", "value date", "posting date", "txndate"}
AMOUNT_HEADERS = {"amount", "amount (inr)", "amount(inr)", "transaction amount", "amt"}
DEBIT_HEADERS = {"debit", "withdrawal", "withdrawal amt", "withdrawal amt.", "debit amount", "dr"}
CREDIT_HEADERS = {"credit", "deposit", "deposit amt", "deposit amt.", "credit amount", "cr"}
DESCRIPTION_HEADERS = {
    "narration",
    "description",
    "particulars",
    "details",
    "remarks",
    "transaction remarks",
}
MERCHANT_HEADERS = {"merchant", "payee", "beneficiary"}

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%m/%d/%Y",
    "%d/%m/%y",
]


class CsvParseError(Exception):
    pass


def decode_csv_bytes(raw: bytes) -> str:
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise CsvParseError("Could not decode file with any supported encoding")


def _normalize(header: str) -> str:
    return header.strip().lower()


def detect_columns(fieldnames: list[str]) -> dict[str, str]:
    columns: dict[str, str] = {}
    for original in fieldnames:
        if not original:
            continue
        norm = _normalize(original)
        if norm in DATE_HEADERS and "date" not in columns:
            columns["date"] = original
        elif norm in AMOUNT_HEADERS and "amount" not in columns:
            columns["amount"] = original
        elif norm in DEBIT_HEADERS and "debit" not in columns:
            columns["debit"] = original
        elif norm in CREDIT_HEADERS and "credit" not in columns:
            columns["credit"] = original
        elif norm in DESCRIPTION_HEADERS and "description" not in columns:
            columns["description"] = original
        elif norm in MERCHANT_HEADERS and "merchant" not in columns:
            columns["merchant"] = original
    return columns


def parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    for token in ("₹", "Rs.", "Rs", "INR", ","):
        text = text.replace(token, "")
    text = text.strip()
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def read_rows(csv_text: str) -> tuple[list[dict], dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise CsvParseError("CSV has no header row")

    columns = detect_columns(list(reader.fieldnames))
    if "date" not in columns:
        raise CsvParseError("Could not detect a date column")
    if "amount" not in columns and "debit" not in columns and "credit" not in columns:
        raise CsvParseError("Could not detect an amount/debit/credit column")

    rows = list(reader)
    return rows, columns
