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
        select(Extraction).where(Extraction.document_id == doc_id).order_by(desc(Extraction.version))
    )
    extractions = result.scalars().all()
    out = []
    for e in extractions:
        eout = ExtractionOut.model_validate(e)
        eout.fields = json.loads(e.fields) if e.fields else None
        eout.confidence_per_field = json.loads(e.confidence_per_field) if e.confidence_per_field else None
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
    extraction: Extraction = result.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    # Merge new fields over existing
    current_fields = json.loads(extraction.fields) if extraction.fields else {}
    merged = {**current_fields, **body.fields}

    # Create a new version
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
        confidence_per_field=extraction.confidence_per_field,
        model_used="human_correction",
        processing_time_ms=0,
        status="completed",
        created_by=current_user.id,
    )
    db.add(new_extraction)

    await write_audit_log(
        db=db, user_id=current_user.id, user_name=current_user.name,
        action="FIELDS_EDITED", resource_type="extraction",
        resource_id=new_id,
        details={"changed_fields": list(body.fields.keys()), "version": new_version},
    )
    await db.commit()
    return SuccessResponse(message=f"Fields saved as version {new_version}")
