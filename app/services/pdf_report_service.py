import io
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import analytics_service, budget_service, category_service


def _styled_table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ]
        )
    )
    return table


async def build_monthly_report_pdf(
    db: AsyncSession, owner_id: uuid.UUID, year: int, month: int
) -> bytes:
    breakdown = await analytics_service.category_breakdown(db, owner_id, year, month)
    top_merchants = await analytics_service.top_merchants(db, owner_id, year, month, limit=10)
    budgets = await budget_service.list_budgets(db, owner_id, year, month)
    categories = {c.id: c.name for c in await category_service.list_categories(db, owner_id)}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"SpendWise Monthly Report — {year}-{month:02d}", styles["Title"]),
        Spacer(1, 16),
    ]

    total_spent = (
        sum((item.total for item in breakdown), start=type(breakdown[0].total)(0))
        if breakdown
        else 0
    )
    story.append(Paragraph(f"Total spent: {total_spent}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Spending by category", styles["Heading2"]))
    category_rows = [["Category", "Amount", "% of month"]] + [
        [item.category_name, str(item.total), f"{item.percent}%"] for item in breakdown
    ]
    story.append(_styled_table(category_rows))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Budgets", styles["Heading2"]))
    budget_rows = [["Category", "Budget", "Spent", "Remaining", "% used"]] + [
        [
            categories.get(budget.category_id, "Unknown"),
            str(budget.amount),
            str(budget.spent),
            str(budget.remaining),
            f"{budget.percent_used}%",
        ]
        for budget in budgets
    ]
    story.append(_styled_table(budget_rows))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Top merchants", styles["Heading2"]))
    merchant_rows = [["Merchant", "Amount", "Transactions"]] + [
        [merchant.merchant, str(merchant.total), str(merchant.count)] for merchant in top_merchants
    ]
    story.append(_styled_table(merchant_rows))

    doc.build(story)
    return buffer.getvalue()
