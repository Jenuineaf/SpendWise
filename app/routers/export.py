from datetime import date

from fastapi import APIRouter, Query, Response

from app.core.deps import CurrentUser, DBSession
from app.services.export_service import export_expenses_csv
from app.services.pdf_report_service import build_monthly_report_pdf

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/expenses.csv")
async def export_expenses(
    current_user: CurrentUser,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    content = await export_expenses_csv(db, current_user.id, date_from, date_to)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.get("/monthly-report.pdf")
async def export_monthly_report(
    current_user: CurrentUser,
    db: DBSession,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
):
    pdf_bytes = await build_monthly_report_pdf(db, current_user.id, year, month)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=spendwise-report-{year}-{month:02d}.pdf"
        },
    )
