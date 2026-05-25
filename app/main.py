"""
DocIntel — AI Document Intelligence Platform
FastAPI Application Entry Point
"""

import app.render_config  # noqa: F401 — patch DB URL for Render
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routes import auth, documents, extractions, schemas, audit, analytics, users
from dotenv import load_dotenv
from pathlib import Path



# load .env from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("docintel")
settings = get_settings()


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting DocIntel in {settings.app_env} mode")
    await init_db()
    yield
    logger.info("DocIntel shutting down")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DocIntel — AI Document Intelligence",
    description="""
## AI Document Intelligence Platform

Upload contracts, invoices, medical records, or reports and get:
- **OCR + AI Extraction** — structured fields with per-field confidence scores
- **Schema Validation** — configurable business rules with pass/warn/fail results
- **Human-in-the-Loop Review** — review queue with approve/reject workflow
- **Versioning** — every edit creates a new extraction version with full diff
- **Audit Logs** — tamper-proof, exportable audit trail for every action
- **Enterprise Security** — JWT auth, RBAC, rate limiting, HIPAA-ready

### Default credentials (development)
| Email | Password | Role |
|---|---|---|
| admin@docintel.ai | Admin123! | admin |
| reviewer@docintel.ai | Review123! | reviewer |
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────
API_PREFIX = "/api"
app.include_router(auth.router,        prefix=API_PREFIX)
app.include_router(documents.router,   prefix=API_PREFIX)
app.include_router(extractions.router, prefix=API_PREFIX)
app.include_router(schemas.router,     prefix=API_PREFIX)
app.include_router(audit.router,       prefix=API_PREFIX)
app.include_router(analytics.router,   prefix=API_PREFIX)
app.include_router(users.router,       prefix=API_PREFIX)


# ── Health & root ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "env": settings.app_env,
    }


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "DocIntel API — visit /docs for the interactive API reference"}
