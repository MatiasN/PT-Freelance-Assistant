from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.ecb import EcbUnavailable
from app.fiscal.parameters import UnsupportedFiscalYear
from app.routers import calendar, estimates, exchange_rates, payouts


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


async def unsupported_year_handler(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(error)}
    )


async def ecb_unavailable_handler(_: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"ECB Data Portal unavailable: {error}"},
    )


def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(static_dir: str | None = None) -> FastAPI:
    application = FastAPI(
        title="PT Tax Assistant",
        description=(
            "Organisational and calculation ledger for Portuguese Categoria B income. It never "
            "connects to Portal das Finanças or Segurança Social and stores no AT credentials."
        ),
        lifespan=lifespan,
    )
    application.include_router(payouts.router)
    application.include_router(estimates.router)
    application.include_router(calendar.router)
    application.include_router(exchange_rates.router)
    application.add_exception_handler(UnsupportedFiscalYear, unsupported_year_handler)
    application.add_exception_handler(EcbUnavailable, ecb_unavailable_handler)
    application.add_api_route("/api/health", health, methods=["GET"])
    if static_dir:
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return application


app = create_app(get_settings().static_dir)
