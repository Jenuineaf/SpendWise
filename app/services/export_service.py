import csv
import io
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.expense_service import list_expenses

_PAGE_SIZE = 500


async def export_expenses_csv(
    db: AsyncSession, owner_id: uuid.UUID, date_from: date | None, date_to: date | None
) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "category_id", "amount", "merchant", "note"])

    page = 1
    while True:
        items, total = await list_expenses(db, owner_id, page, _PAGE_SIZE, None, date_from, date_to)
        for expense in items:
            writer.writerow(
                [
                    expense.date,
                    expense.category_id,
                    expense.amount,
                    expense.merchant or "",
                    expense.note or "",
                ]
            )
        if page * _PAGE_SIZE >= total:
            break
        page += 1

    return buffer.getvalue()
