"""Extraction routes — get, update fields, get validations."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Extraction, Validation, User
from app.schemas import ExtractionOut, ValidationOut, FieldsUpdateRequest, SuccessResponse
from app.middleware.auth import get_current_user
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/extractions", tags=["Extractions"])


@router.get("/document/{doc_id}", response_model=list[ExtractionOut])
async def get_extractions(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Extraction)
        .where(Extraction.document_id == doc_id)
        .order_by(desc(Extraction.version))
    )
    extractions = result.scalars().all()

    out = []
    for e in extractions:
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
        out.append(eout)

    return out


@router.get("/{extraction_id}/validations", response_model=list[ValidationOut])
async def get_validations(
    extraction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Validation)
        .where(Validation.extraction_id == extraction_id)
        .order_by(Validation.passed, desc(Validation.severity))
    )
    return [ValidationOut.model_validate(v) for v in result.scalars().all()]


@router.patch("/{extraction_id}/fields", response_model=SuccessResponse)
async def update_fields(
    extraction_id: str,
    body: FieldsUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Extraction).where(Extraction.id == extraction_id))
    extraction: Extraction | None = result.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    try:
        current_fields = json.loads(extraction.fields) if isinstance(extraction.fields, str) else extraction.fields or {}
    except Exception:
        current_fields = {}

    merged = {**current_fields, **body.fields}

    ver_result = await db.execute(
        select(func.max(Extraction.version)).where(Extraction.document_id == extraction.document_id)
    )
    new_version = (ver_result.scalar() or 0) + 1
    new_id = str(uuid.uuid4())

    new_extraction = Extraction(
        id=new_id,
        document_id=extraction.document_id,
        version=new_version,
        schema_id=extraction.schema_id,
        fields=json.dumps(merged),
        raw_text=extraction.raw_text,
        confidence_overall=extraction.confidence_overall,
        confidence_per_field=(
            extraction.confidence_per_field
            if isinstance(extraction.confidence_per_field, str)
            else json.dumps(extraction.confidence_per_field or {})
        ),
        model_used="human_correction",
        processing_time_ms=0,
        status="completed",
        error=None,
        created_by=current_user.id,
    )
    db.add(new_extraction)

    await write_audit_log(
        db=db,
        user_id=current_user.id,
        user_name=current_user.name,
        action="FIELDS_EDITED",
        resource_type="extraction",
        resource_id=new_id,
        details={"changed_fields": list(body.fields.keys()), "version": new_version},
    )

    await db.commit()
    return SuccessResponse(message=f"Fields saved as version {new_version}")
