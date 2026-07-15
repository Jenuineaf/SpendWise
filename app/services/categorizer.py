import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.keyword_rule import CategoryKeywordRule

GLOBAL_KEYWORD_CATEGORY_MAP: dict[str, str] = {
    "swiggy": "Food & Dining",
    "zomato": "Food & Dining",
    "dominos": "Food & Dining",
    "mcdonald": "Food & Dining",
    "kfc": "Food & Dining",
    "starbucks": "Food & Dining",
    "cafe": "Food & Dining",
    "restaurant": "Food & Dining",
    "bigbasket": "Groceries",
    "blinkit": "Groceries",
    "zepto": "Groceries",
    "grofers": "Groceries",
    "dmart": "Groceries",
    "uber": "Transport",
    "ola": "Transport",
    "rapido": "Transport",
    "petrol": "Transport",
    "fuel": "Transport",
    "metro": "Transport",
    "parking": "Transport",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    "nykaa": "Shopping",
    "electricity": "Bills & Utilities",
    "airtel": "Bills & Utilities",
    "jio": "Bills & Utilities",
    "vodafone": "Bills & Utilities",
    "broadband": "Bills & Utilities",
    "recharge": "Bills & Utilities",
    "water bill": "Bills & Utilities",
    "gas bill": "Bills & Utilities",
    "netflix": "Entertainment",
    "hotstar": "Entertainment",
    "spotify": "Entertainment",
    "bookmyshow": "Entertainment",
    "prime video": "Entertainment",
    "pharmacy": "Health",
    "apollo": "Health",
    "hospital": "Health",
    "clinic": "Health",
    "diagnostic": "Health",
    "rent": "Rent",
    "landlord": "Rent",
    "makemytrip": "Travel",
    "irctc": "Travel",
    "indigo": "Travel",
    "goibibo": "Travel",
    "airbnb": "Travel",
    "oyo": "Travel",
}


async def _find_category_by_name(
    db: AsyncSession, owner_id: uuid.UUID, name: str
) -> uuid.UUID | None:
    result = await db.execute(
        select(Category.id).where(Category.owner_id == owner_id, Category.name.ilike(name))
    )
    return result.scalar_one_or_none()


async def categorize(db: AsyncSession, owner_id: uuid.UUID, text: str) -> uuid.UUID | None:
    """Best-effort category guess for imported/free-text expense descriptions.

    Learned per-user overrides always win over the global keyword map, and the
    longest matching keyword wins among overrides (so a more specific override
    beats a broader one).
    """
    text_lower = (text or "").lower()
    if not text_lower:
        return None

    result = await db.execute(
        select(CategoryKeywordRule).where(CategoryKeywordRule.owner_id == owner_id)
    )
    learned = list(result.scalars().all())
    matches = [rule for rule in learned if rule.keyword in text_lower]
    if matches:
        best = max(matches, key=lambda rule: len(rule.keyword))
        return best.category_id

    for keyword, category_name in GLOBAL_KEYWORD_CATEGORY_MAP.items():
        if keyword in text_lower:
            category_id = await _find_category_by_name(db, owner_id, category_name)
            if category_id is not None:
                return category_id

    return None


async def learn_override(
    db: AsyncSession, owner_id: uuid.UUID, merchant: str, category_id: uuid.UUID
) -> None:
    keyword = merchant.strip().lower()
    if not keyword:
        return
    result = await db.execute(
        select(CategoryKeywordRule).where(
            CategoryKeywordRule.owner_id == owner_id, CategoryKeywordRule.keyword == keyword
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        db.add(CategoryKeywordRule(owner_id=owner_id, keyword=keyword, category_id=category_id))
    else:
        rule.category_id = category_id
    await db.commit()
