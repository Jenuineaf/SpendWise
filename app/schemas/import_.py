from pydantic import BaseModel


class SkippedRow(BaseModel):
    row_number: int
    reason: str


class ImportSummary(BaseModel):
    rows_total: int
    rows_imported: int
    rows_skipped: int
    skipped_reasons: list[SkippedRow]
