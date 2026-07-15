from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.schemas.advisor import AdvisorAnswer, AdvisorQuestion
from app.services.advisor_service import ask_advisor

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/ask", response_model=AdvisorAnswer)
async def ask(data: AdvisorQuestion, current_user: CurrentUser, db: DBSession):
    answer = await ask_advisor(db, current_user, data.question)
    return AdvisorAnswer(answer=answer)
