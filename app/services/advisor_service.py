from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import analytics_service, budget_service, category_service
from app.services.llm import get_llm_provider


async def build_spending_summary(db: AsyncSession, user: User) -> str:
    today = date.today()
    trend = await analytics_service.monthly_trend(db, user.id, months=3)
    breakdown = await analytics_service.category_breakdown(db, user.id, today.year, today.month)
    top_merchants = await analytics_service.top_merchants(
        db, user.id, today.year, today.month, limit=5
    )
    budgets = await budget_service.list_budgets(db, user.id, today.year, today.month)
    categories = await category_service.list_categories(db, user.id)
    category_names = {category.id: category.name for category in categories}

    lines = [
        f"User monthly income (self-reported): "
        f"{user.monthly_income if user.monthly_income is not None else 'not set'}",
        "Last 3 months total spend: "
        + ", ".join(f"{p.year}-{p.month:02d}: {p.total}" for p in trend),
        f"This month ({today.year}-{today.month:02d}) spend by category:",
    ]
    for item in breakdown:
        lines.append(
            f"  - {item.category_name}: {item.total} ({item.percent}% of this month's spend)"
        )

    lines.append("Top merchants this month:")
    for merchant in top_merchants:
        lines.append(
            f"  - {merchant.merchant}: {merchant.total} across {merchant.count} transactions"
        )

    lines.append("Budgets this month:")
    for budget in budgets:
        name = category_names.get(budget.category_id, "Unknown category")
        lines.append(
            f"  - {name}: budget {budget.amount}, spent {budget.spent}, "
            f"remaining {budget.remaining} ({budget.percent_used}% used)"
        )

    return "\n".join(lines)


async def ask_advisor(db: AsyncSession, user: User, question: str) -> str:
    summary = await build_spending_summary(db, user)
    system_prompt = (
        "You are SpendWise's budgeting advisor. Answer the user's question using ONLY the "
        "spending data below — never invent numbers. If the data is insufficient to answer "
        "confidently, say so explicitly instead of guessing.\n\n" + summary
    )
    provider = get_llm_provider()
    return await provider.ask(system_prompt, question)
