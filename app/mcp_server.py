"""DocIntel MCP server.
import os; print("DB URL:", os.environ.get("DATABASE_URL"), flush=True)

This exposes a small set of read-heavy tools over Model Context Protocol so
VS Code / Copilot can inspect documents, schemas, extractions, audit logs,
and analytics from the same backend database used by the FastAPI app.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import desc, func, select, text

from mcp.server.fastmcp import FastMCP

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os

def _get_session():
    db_url = os.environ.get('DATABASE_URL') or 'postgresql+asyncpg://docintel:docintel_secret@127.0.0.1:5432/docintel'
    engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

AsyncSessionLocal = None

async def init_db():
    global AsyncSessionLocal
    AsyncSessionLocal = _get_session()
from app.models import AuditLog, Document, Extraction, Review, Schema, User
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

mcp = FastMCP(
    "DocIntel",
    instructions=(
        "Use these tools to inspect documents, schemas, extractions, reviews, "
        "audit logs, and analytics from DocIntel. Prefer the document and "
        "analytics tools for read-only analysis."
    ),
)


async def _ensure_db() -> None:
    """Ensure the SQLite/PostgreSQL schema exists before serving tools."""
    await init_db()


async def _session():
    async with AsyncSessionLocal() as session:
        yield session


def _safe_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _dt(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


async def _latest_extraction_map(
    db, document_id: str
) -> tuple[Optional[Extraction], Optional[dict[str, Any]]]:
    result = await db.execute(
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(desc(Extraction.version))
        .limit(1)
    )
    extraction = result.scalar_one_or_none()
    if not extraction:
        return None, None

    payload = {
        "id": extraction.id,
        "document_id": extraction.document_id,
        "version": extraction.version,
        "schema_id": extraction.schema_id,
        "fields": _safe_json(extraction.fields, {}),
        "confidence_overall": extraction.confidence_overall,
        "confidence_per_field": _safe_json(extraction.confidence_per_field, {}),
        "llm_model": extraction.model_used,
        "processing_time_ms": extraction.processing_time_ms,
        "status": extraction.status,
        "error": extraction.error,
        "created_at": _dt(extraction.created_at),
    }
    return extraction, payload


@mcp.tool()
async def health() -> dict[str, Any]:
    """Return basic DocIntel backend and MCP server status."""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "database_url": settings.database_url,
    }


@mcp.tool()
async def list_documents(
    status: Optional[str] = None,
    doc_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """List documents with optional filters."""
    async with AsyncSessionLocal() as db:
        q = select(Document)
        if status:
            q = q.where(Document.status == status)
        if doc_type:
            q = q.where(Document.doc_type == doc_type)
        if search:
            q = q.where(Document.name.ilike(f"%{search}%"))
        q = q.order_by(desc(Document.created_at)).limit(limit).offset(offset)

        result = await db.execute(q)
        docs = result.scalars().all()

        total_result = await db.execute(select(func.count(Document.id)))
        total = total_result.scalar() or 0

        items: list[dict[str, Any]] = []
        for doc in docs:
            latest_ext, _ = await _latest_extraction_map(db, doc.id)
            uploader = await db.get(User, doc.uploaded_by)
            items.append(
                {
                    "id": doc.id,
                    "name": doc.name,
                    "original_name": doc.original_name,
                    "doc_type": doc.doc_type,
                    "status": doc.status,
                    "risk_level": doc.risk_level,
                    "schema_id": doc.schema_id,
                    "uploaded_by": doc.uploaded_by,
                    "uploaded_by_name": uploader.name if uploader else None,
                    "confidence": latest_ext.confidence_overall if latest_ext else None,
                    "current_version": latest_ext.version if latest_ext else 1,
                    "created_at": _dt(doc.created_at),
                    "updated_at": _dt(doc.updated_at),
                }
            )

        return {"documents": items, "total": total, "limit": limit, "offset": offset}


@mcp.tool()
async def get_document(document_id: str) -> dict[str, Any]:
    """Return a single document with its latest extractions and reviews."""
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        uploader = await db.get(User, doc.uploaded_by)

        ext_res = await db.execute(
            select(Extraction)
            .where(Extraction.document_id == document_id)
            .order_by(desc(Extraction.version))
        )
        extractions = []
        for extraction in ext_res.scalars().all():
            extractions.append(
                {
                    "id": extraction.id,
                    "document_id": extraction.document_id,
                    "version": extraction.version,
                    "schema_id": extraction.schema_id,
                    "fields": _safe_json(extraction.fields, {}),
                    "confidence_overall": extraction.confidence_overall,
                    "confidence_per_field": _safe_json(extraction.confidence_per_field, {}),
                    "llm_model": extraction.model_used,
                    "processing_time_ms": extraction.processing_time_ms,
                    "status": extraction.status,
                    "error": extraction.error,
                    "created_at": _dt(extraction.created_at),
                }
            )

        rev_res = await db.execute(select(Review).where(Review.document_id == document_id))
        reviews = [
            {
                "id": r.id,
                "document_id": r.document_id,
                "extraction_id": r.extraction_id,
                "status": r.status,
                "decision": r.decision,
                "notes": r.notes,
                "reviewed_at": _dt(r.reviewed_at),
                "reviewed_by": r.reviewed_by,
                "created_at": _dt(r.created_at),
            }
            for r in rev_res.scalars().all()
        ]

        latest_extraction, latest_payload = await _latest_extraction_map(db, document_id)

        return {
            "id": doc.id,
            "name": doc.name,
            "original_name": doc.original_name,
            "doc_type": doc.doc_type,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "mime_type": doc.mime_type,
            "status": doc.status,
            "risk_level": doc.risk_level,
            "schema_id": doc.schema_id,
            "uploaded_by": doc.uploaded_by,
            "uploaded_by_name": uploader.name if uploader else None,
            "confidence": latest_extraction.confidence_overall if latest_extraction else 0.0,
            "current_version": latest_extraction.version if latest_extraction else 1,
            "created_at": _dt(doc.created_at),
            "updated_at": _dt(doc.updated_at),
            "latest_extraction": latest_payload,
            "extractions": extractions,
            "reviews": reviews,
        }


@mcp.tool()
async def list_schemas(doc_type: Optional[str] = None, limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """List extraction schemas."""
    async with AsyncSessionLocal() as db:
        q = select(Schema)
        if doc_type:
            q = q.where(Schema.doc_type == doc_type)
        q = q.order_by(desc(Schema.updated_at)).limit(limit).offset(offset)

        result = await db.execute(q)
        schemas = result.scalars().all()

        total_res = await db.execute(select(func.count(Schema.id)))
        total = total_res.scalar() or 0

        items = []
        for schema in schemas:
            doc_count_res = await db.execute(
                select(func.count(Document.id)).where(Document.schema_id == schema.id)
            )
            items.append(
                {
                    "id": schema.id,
                    "name": schema.name,
                    "doc_type": schema.doc_type,
                    "version": schema.version,
                    "status": schema.status,
                    "definition": _safe_json(schema.definition, {}),
                    "validation_rules": _safe_json(schema.validation_rules, []),
                    "created_by": schema.created_by,
                    "created_at": _dt(schema.created_at),
                    "updated_at": _dt(schema.updated_at),
                    "doc_count": doc_count_res.scalar() or 0,
                }
            )

        return {"schemas": items, "total": total, "limit": limit, "offset": offset}


@mcp.tool()
async def list_extractions(document_id: str) -> list[dict[str, Any]]:
    """Return all extraction versions for a document."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Extraction)
            .where(Extraction.document_id == document_id)
            .order_by(desc(Extraction.version))
        )
        return [
            {
                "id": e.id,
                "document_id": e.document_id,
                "version": e.version,
                "schema_id": e.schema_id,
                "fields": _safe_json(e.fields, {}),
                "confidence_overall": e.confidence_overall,
                "confidence_per_field": _safe_json(e.confidence_per_field, {}),
                "llm_model": e.model_used,
                "processing_time_ms": e.processing_time_ms,
                "status": e.status,
                "error": e.error,
                "created_at": _dt(e.created_at),
            }
            for e in result.scalars().all()
        ]


@mcp.tool()
async def list_audit_logs(limit: int = 50, offset: int = 0, action: Optional[str] = None) -> dict[str, Any]:
    """List recent audit log entries."""
    async with AsyncSessionLocal() as db:
        q = select(AuditLog)
        if action:
            q = q.where(AuditLog.action == action)
        q = q.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
        result = await db.execute(q)
        logs = result.scalars().all()

        total_res = await db.execute(select(func.count(AuditLog.id)))
        total = total_res.scalar() or 0

        return {
            "logs": [
                {
                    "id": l.id,
                    "user_id": l.user_id,
                    "user_name": l.user_name,
                    "action": l.action,
                    "resource_type": l.resource_type,
                    "resource_id": l.resource_id,
                    "resource_name": l.resource_name,
                    "details": _safe_json(l.details, None),
                    "ip_address": l.ip_address,
                    "created_at": _dt(l.created_at),
                }
                for l in logs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@mcp.tool()
async def analytics_overview() -> dict[str, Any]:
    """Return the same high-level analytics that power the dashboard."""
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count(Document.id)))).scalar() or 0
        status_res = await db.execute(select(Document.status, func.count(Document.id)).group_by(Document.status))
        by_status = {row[0]: row[1] for row in status_res.all()}
        type_res = await db.execute(select(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type))
        by_type = {(row[0] or "unknown"): row[1] for row in type_res.all()}
        conf_res = await db.execute(select(func.avg(Extraction.confidence_overall)).where(Extraction.status == "completed"))
        avg_conf = round(float(conf_res.scalar() or 0), 1)
        pending_rev = (await db.execute(select(func.count(Review.id)).where(Review.status == "pending"))).scalar() or 0
        ms_res = await db.execute(select(func.avg(Extraction.processing_time_ms)))
        avg_secs = round(float(ms_res.scalar() or 0) / 1000, 1)

        daily_res = await db.execute(text("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM documents
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY day
        """))
        last_7 = [{"day": str(row[0]), "count": row[1]} for row in daily_res.all()]

        high_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall >= 90))
        med_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall.between(70, 89.99)))
        low_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall < 70))

        return {
            "total_documents": total,
            "by_status": by_status,
            "by_type": by_type,
            "avg_confidence": avg_conf,
            "pending_review": pending_rev,
            "avg_processing_seconds": avg_secs,
            "last_7_days": last_7,
            "confidence_distribution": {
                "high": high_res.scalar() or 0,
                "medium": med_res.scalar() or 0,
                "low": low_res.scalar() or 0,
            },
        }


@mcp.tool()
async def summarize_document(document_id: str) -> dict[str, Any]:
    """Summarize a document using its latest extraction and metadata."""
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        latest_extraction, latest_payload = await _latest_extraction_map(db, document_id)

        summary_parts = [
            f"Document name: {doc.name}",
            f"Original name: {doc.original_name}",
            f"Type: {doc.doc_type or 'unknown'}",
            f"Status: {doc.status}",
            f"Risk level: {doc.risk_level or 'unknown'}",
        ]

        if latest_payload:
            summary_parts.append(f"Latest extraction version: {latest_payload['version']}")
            summary_parts.append(f"Confidence: {latest_payload['confidence_overall']}%")
            fields = latest_payload.get("fields") or {}
            if isinstance(fields, dict) and fields:
                summary_parts.append("Extracted fields:")
                for key, value in list(fields.items())[:12]:
                    summary_parts.append(f"- {key}: {value}")

        return {
            "document_id": doc.id,
            "summary": "\n".join(summary_parts),
            "latest_extraction": latest_payload,
        }


@mcp.tool()
async def ask_document(document_id: str, question: str) -> dict[str, Any]:
    """Answer a question about a document using its latest extraction data."""
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        latest_extraction, latest_payload = await _latest_extraction_map(db, document_id)
        fields = (latest_payload or {}).get("fields") or {}

        if not latest_payload:
            return {
                "document_id": doc.id,
                "question": question,
                "answer": "No extraction is available for this document yet.",
            }

        question_lower = question.lower()

        if "payment" in question_lower and isinstance(fields, dict):
            for key, value in fields.items():
                if "payment" in str(key).lower():
                    return {
                        "document_id": doc.id,
                        "question": question,
                        "answer": str(value),
                        "source": f"field:{key}",
                    }

        if "date" in question_lower and isinstance(fields, dict):
            for key, value in fields.items():
                if "date" in str(key).lower() or "expiry" in str(key).lower() or "expiration" in str(key).lower():
                    return {
                        "document_id": doc.id,
                        "question": question,
                        "answer": str(value),
                        "source": f"field:{key}",
                    }

        if "who" in question_lower or "signed" in question_lower:
            for key, value in fields.items():
                if "sign" in str(key).lower() or "approved_by" in str(key).lower():
                    return {
                        "document_id": doc.id,
                        "question": question,
                        "answer": str(value),
                        "source": f"field:{key}",
                    }

        return {
            "document_id": doc.id,
            "question": question,
            "answer": "I found the document and latest extraction, but I could not match the question to a specific field.",
            "available_fields": list(fields.keys())[:25] if isinstance(fields, dict) else [],
            "latest_extraction": latest_payload,
        }


async def _startup() -> None:
    logging.basicConfig(level=logging.INFO)
    await _ensure_db()


def main() -> None:
    import asyncio

    asyncio.run(_startup())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()