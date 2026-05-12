"""
Document routes — upload, list, detail, update, delete, review.
"""

import json
from pydoc import doc
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, Request, UploadFile, BackgroundTasks, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document, Extraction, Review, User
from app.schemas import (
    DocumentListResponse, DocumentOut, DocumentDetail, DocumentUpdate,
    ReviewRequest, SuccessResponse,
)
from app.middleware.auth import get_current_user, require_role, get_client_ip
from app.services.pipeline import process_document
from app.utils.audit import write_audit_log
from app.config import get_settings

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".jpg", ".jpeg", ".png", ".txt", ".csv"}


# ── Upload ─────────────────────────────────────────────────────────────────────
@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    request: Request,
    files: List[UploadFile] = File(...),
    schema_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    created = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type {ext} not supported")

        size = 0
        saved_name = f"{uuid.uuid4()}{ext}"
        dest = settings.upload_path / saved_name

        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 64):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"File too large (max {settings.max_upload_size_mb}MB)")
                out.write(chunk)
                if settings.s3_bucket_name:
                    from app.services.storage import upload_file
                    upload_file(str(dest), saved_name)
                    dest.unlink(missing_ok=True)
                    file_path_value = saved_name
                else:
                    file_path_value = saved_name

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            name=file.filename,
            original_name=file.filename,
            file_path=file_path_value,
            file_size=size,
            mime_type=file.content_type,
            status="processing",
            schema_id=schema_id,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        await db.flush()

        await write_audit_log(
            db=db, user_id=current_user.id, user_name=current_user.name,
            action="DOCUMENT_UPLOADED", resource_type="document",
            resource_id=doc_id, resource_name=file.filename,
            details={"size": size, "schema_id": schema_id},
            ip_address=get_client_ip(request),
        )
        # Queue background processing
        background_tasks.add_task(
            _run_pipeline_in_background, doc_id, current_user.id
        )
        created.append({"id": doc_id, "name": file.filename, "status": "processing"})

    await db.commit()
    return {"documents": created}


async def _run_pipeline_in_background(document_id: str, user_id: str):
    """Wrapper so background task gets its own DB session."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await process_document(document_id, session, user_id)


# ── List ───────────────────────────────────────────────────────────────────────
@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    status: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None, alias="type"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    total = total_result.scalar()

    # Enrich with uploader name + confidence
    enriched = []
    for doc in docs:
        out = DocumentOut.model_validate(doc)
        user_res = await db.execute(select(User).where(User.id == doc.uploaded_by))
        u = user_res.scalar_one_or_none()
        out.uploaded_by_name = u.name if u else None

        ext_res = await db.execute(
            select(Extraction).where(Extraction.document_id == doc.id).order_by(desc(Extraction.version)).limit(1)
        )
        latest_ext = ext_res.scalar_one_or_none()
        if latest_ext:
            out.confidence = latest_ext.confidence_overall
            out.current_version = latest_ext.version
        enriched.append(out)

    return DocumentListResponse(documents=enriched, total=total, limit=limit, offset=offset)


# ── Detail ─────────────────────────────────────────────────────────────────────
@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── Load document ─────────────────────────────────────
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # ── Load extractions ───────────────────────────────────
    ext_res = await db.execute(
        select(Extraction)
        .where(Extraction.document_id == doc_id)
        .order_by(desc(Extraction.version))
    )
    extractions_raw = ext_res.scalars().all()

    from app.schemas import ExtractionOut
    extractions = []

    for e in extractions_raw:
    # 🔥 FIX: convert FIRST
        try:
            fields = json.loads(e.fields) if isinstance(e.fields, str) else e.fields or {}
        except Exception:
            fields = {}

        try:
            confidence_per_field = (
                json.loads(e.confidence_per_field)
                if isinstance(e.confidence_per_field, str)
                else e.confidence_per_field or {}
            )
        except Exception:
            confidence_per_field = {}

        eout = ExtractionOut.model_validate({
            "id": e.id,
            "document_id": e.document_id,
            "version": e.version,
            "schema_id": e.schema_id,
            "fields": fields,
            "confidence_overall": e.confidence_overall,
            "confidence_per_field": confidence_per_field,
            "llm_model": e.model_used,
            "processing_time_ms": e.processing_time_ms,
            "status": e.status,
            "error": e.error,
            "created_at": e.created_at,
        })

        extractions.append(eout)

    # ── Load reviews ───────────────────────────────────────
    rev_res = await db.execute(select(Review).where(Review.document_id == doc_id))
    reviews_raw = rev_res.scalars().all()

    from app.schemas import ReviewOut
    reviews = [ReviewOut.model_validate(r) for r in reviews_raw]

    # ── SAFE RESPONSE BUILD (NO Pydantic crash) ────────────
    detail = {
        "id": doc.id,
        "name": doc.name or "",
        "original_name": doc.original_name or "",
        "doc_type": doc.doc_type,
        "file_size": doc.file_size or 0,
        "page_count": doc.page_count or 0,
        "mime_type": doc.mime_type,
        "status": doc.status,
        "risk_level": doc.risk_level,
        "schema_id": doc.schema_id,
        "uploaded_by": doc.uploaded_by,
        "uploaded_by_name": None,
        "confidence": 0.0,
        "current_version": 1,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "extractions": [],
        "reviews": [],
    }

    # ── Add uploader name ──────────────────────────────────
    user_res = await db.execute(select(User).where(User.id == doc.uploaded_by))
    u = user_res.scalar_one_or_none()
    detail["uploaded_by_name"] = u.name if u else "Unknown"

    # ── Add extraction info ────────────────────────────────
    if extractions:
        latest = extractions[0]
        detail["confidence"] = float(latest.confidence_overall or 0.0)
        detail["current_version"] = latest.version or 1

    # ── Attach lists ───────────────────────────────────────
    detail["extractions"] = extractions
    detail["reviews"] = reviews

    return detail