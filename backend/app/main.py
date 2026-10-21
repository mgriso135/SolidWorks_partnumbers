from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .api import admin, auth, generate, integrations, items, rules
from .config import settings
from .db import SessionLocal, engine, init_db
from .seed import seed_demo_data
from .services.errors import GenerationError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create_tables:
        init_db()
    if settings.seed_demo:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title="PartCode API",
    version="1.0.0",
    description="Centralized part numbering and coding rules for CAD, PDM and ERP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GenerationError)
async def generation_error_handler(_request: Request, exc: GenerationError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.as_detail()})


app.include_router(auth.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(items.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "service": "partcode", "version": app.version}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": "PartCode",
        "api": "/api",
        "docs": "/docs",
    }


_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/app", StaticFiles(directory=_dist, html=True), name="frontend")
