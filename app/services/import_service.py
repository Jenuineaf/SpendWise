import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.category import Category
from app.models.expense import Expense
from app.schemas.import_ import ImportSummary, SkippedRow
from app.services.categorizer import categorize
from app.services.csv_parser import (
    CsvParseError,
    decode_csv_bytes,
    parse_amount,
    parse_date,
    read_rows,
)


async def _fallback_category_id(db: AsyncSession, owner_id: uuid.UUID) -> uuid.UUID:
    result = await db.execute(
        select(Category.id).where(Category.owner_id == owner_id, Category.name.ilike("Other"))
    )
    category_id = result.scalar_one_or_none()
    if category_id is not None:
        return category_id

    result = await db.execute(
        select(Category.id).where(Category.owner_id == owner_id).order_by(Category.name).limit(1)
    )
    category_id = result.scalar_one_or_none()
    if category_id is None:
        raise BadRequestError("No categories exist for this user; create one before importing")
    return category_id


async def import_csv(db: AsyncSession, owner_id: uuid.UUID, raw: bytes) -> ImportSummary:
    try:
        text = decode_csv_bytes(raw)
        rows, columns = read_rows(text)
    except CsvParseError as exc:
        raise BadRequestError(str(exc)) from exc

    fallback_category_id = await _fallback_category_id(db, owner_id)

    imported = 0
    skipped: list[SkippedRow] = []

    for index, row in enumerate(rows, start=2):  # +1 for header, +1 for 1-indexing
        date_value = parse_date(row.get(columns["date"], ""))
        if date_value is None:
            skipped.append(SkippedRow(row_number=index, reason="Unrecognized or missing date"))
            continue

        amount_value: Decimal | None = None
        if "amount" in columns:
            amount_value = parse_amount(row.get(columns["amount"], ""))
        else:
            debit = parse_amount(row.get(columns["debit"], "")) if "debit" in columns else None
            credit = parse_amount(row.get(columns["credit"], "")) if "credit" in columns else None
            if debit:
                amount_value = debit
            elif credit:
                skipped.append(
                    SkippedRow(row_number=index, reason="Credit/income entry, not an expense")
                )
                continue

        if amount_value is None or amount_value <= 0:
            skipped.append(
                SkippedRow(row_number=index, reason="Unrecognized or non-positive amount")
            )
            continue

        description = (
            row.get(columns.get("description", ""), "") if "description" in columns else ""
        )
        merchant_raw = (
            row.get(columns.get("merchant", ""), "") if "merchant" in columns else description
        )
        merchant = (merchant_raw or description or "").strip()[:200] or None

        category_id = await categorize(db, owner_id, f"{merchant or ''} {description}".strip())
        if category_id is None:
            category_id = fallback_category_id

        db.add(
            Expense(
                owner_id=owner_id,
                category_id=category_id,
                amount=amount_value,
                merchant=merchant,
                note=(description or None),
                date=date_value,
            )
        )
        imported += 1

    await db.commit()

    return ImportSummary(
        rows_total=len(rows),
        rows_imported=imported,
        rows_skipped=len(skipped),
        skipped_reasons=skipped,
    )
