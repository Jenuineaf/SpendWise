from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppException
from app.routers import auth, budgets, categories, expenses, recurring
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


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
