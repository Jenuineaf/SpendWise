from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import AppException
from app.routers import (
    advisor,
    alerts,
    analytics,
    auth,
    budgets,
    categories,
    expenses,
    export,
    import_,
    recurring,
    savings_goals,
)
from app.services.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(categories.router, prefix=settings.API_V1_PREFIX)
app.include_router(expenses.router, prefix=settings.API_V1_PREFIX)
app.include_router(budgets.router, prefix=settings.API_V1_PREFIX)
app.include_router(recurring.router, prefix=settings.API_V1_PREFIX)
app.include_router(import_.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(advisor.router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX)
app.include_router(savings_goals.router, prefix=settings.API_V1_PREFIX)
app.include_router(export.router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.is_dir():
    # Mounted last so it never shadows the API routes or /health above —
    # Starlette matches routes in registration order.
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
