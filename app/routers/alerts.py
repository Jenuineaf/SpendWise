from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.schemas.alert import BudgetAlertRead
from app.services.alert_service import list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[BudgetAlertRead])
async def get_alerts(current_user: CurrentUser, db: DBSession):
    return await list_alerts(db, current_user.id)
