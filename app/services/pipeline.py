"""Document Processing Pipeline"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Document, Extraction, Validation, Review, Schema
from app.services.ocr import extract_text_from_file
from app.services.llm import extract_fields, classify_document
from app.services.validation import validate_extraction
from app.utils.audit import write_audit_log
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def process_document(
    document_id: str,
    db: AsyncSession,
    uploader_id: str = "system",
) -> None:
    """Process a document through the full extraction pipeline."""
    
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    doc: Document = doc_result.scalar_one_or_none()

    if not doc:
        logger.error(f"Document {document_id} not found")
        return

    doc.status = "processing"
    await db.commit()

    file_path = settings.upload_path / doc.file_path

    try:
        # ── Step 1: OCR ─────────────────────────────
        try:
            raw_text, page_count = extract_text_from_file(file_path)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            raw_text = ""
            page_count = 0

        doc.page_count = page_count

        # ── Step 2: Load schema ─────────────────────
        schema_def = None
        if doc.schema_id:
            schema_result = await db.execute(select(Schema).where(Schema.id == doc.schema_id))
            schema_obj = schema_result.scalar_one_or_none()
            if schema_obj:
                try:
                    schema_def = json.loads(schema_obj.definition)
                except Exception:
                    schema_def = None

        # ── Step 3: Classification ──────────────────
        try:
            if not doc.doc_type:
                doc.doc_type, _ = classify_document(raw_text)
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            doc.doc_type = "document"

        # ── Step 4: LLM Extraction ──────────────────
        try:
            extraction_result, processing_ms, confidence = extract_fields(
                text=raw_text,
                schema_definition=schema_def,
                doc_type_hint=doc.doc_type,
            )
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            extraction_result = {"fields": {}, "anomalies": [], "summary": ""}
            processing_ms = 0
            confidence = 0.0

        raw_fields = (extraction_result or {}).get("fields", {})
        anomalies = extraction_result.get("anomalies", [])

        flat_fields = {}
        confidence_per_field = {}

        for key, val in raw_fields.items():
            if isinstance(val, dict) and "value" in val:
                flat_fields[key] = val["value"]
                confidence_per_field[key] = float(val.get("confidence", confidence))
            else:
                flat_fields[key] = val
                confidence_per_field[key] = float(confidence or 0.0)

        # ── Step 5: Version ─────────────────────────
        ver_result = await db.execute(
            select(func.max(Extraction.version)).where(Extraction.document_id == document_id)
        )
        max_ver = ver_result.scalar() or 0
        new_version = max_ver + 1

        # ── Step 6: Save extraction ─────────────────
        extraction_id = str(uuid.uuid4())

        extraction = Extraction(
            id=extraction_id,
            document_id=document_id,
            version=new_version,
            schema_id=doc.schema_id,
            fields=json.dumps(flat_fields or {}),
            raw_text=raw_text[:5000],
            confidence_overall=float(confidence or 0.0),
            confidence_per_field=json.dumps(confidence_per_field or {}),
            model_used="gpt-4o",
            processing_time_ms=processing_ms,
            status="completed",
            created_by=uploader_id,
        )

        db.add(extraction)
        await db.flush()

        # ── Step 7: Validation ──────────────────────
        try:
            validation_results = validate_extraction(
                extracted_fields=flat_fields,
                schema_definition=schema_def,
                anomalies=anomalies,
                overall_confidence=confidence,
            )
            
            if validation_results:
                for result in validation_results:
                    validation = Validation(
                        id=str(uuid.uuid4()),
                        extraction_id=extraction_id,
                        rule_name=result.rule_name,
                        rule_description=result.rule_description,
                        passed=result.passed,
                        severity=result.severity,
                        message=result.message,
                    )
                    db.add(validation)
                await db.flush()
            
        except Exception as e:
            logger.warning(f"Validation failed: {e}")

        # ── Step 8: Update document status ──────────
        doc.status = "completed"
        doc.extraction_id = extraction_id
        doc.overall_confidence = float(confidence or 0.0)
        
        # Risk level based on confidence
        if confidence >= 85:
            doc.risk_level = "low"
        elif confidence >= 70:
            doc.risk_level = "medium"
        else:
            doc.risk_level = "high"

        await db.commit()

        # ── Step 9: Audit log ───────────────────────
        try:
            await write_audit_log(
                db=db,
                action="document_processed",
                resource_type="document",
                resource_id=document_id,
                details={
                    "extraction_id": extraction_id,
                    "confidence": confidence,
                    "processing_ms": processing_ms,
                    "page_count": page_count,
                },
                user_id=uploader_id,
            )
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        logger.info(f"✓ Document {document_id} processed successfully (confidence: {confidence}%)")

    except Exception as e:
        logger.error(f"Pipeline crashed: {e}", exc_info=True)
        doc.status = "failed"
        doc.error_message = str(e)[:500]
        await db.commit()
