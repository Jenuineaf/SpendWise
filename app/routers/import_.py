from fastapi import APIRouter, File, UploadFile

from app.core.deps import CurrentUser, DBSession
from app.schemas.import_ import ImportSummary
from app.services import import_service

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/csv", response_model=ImportSummary)
async def import_csv(current_user: CurrentUser, db: DBSession, file: UploadFile = File(...)):
    raw = await file.read()
    return await import_service.import_csv(db, current_user.id, raw)
