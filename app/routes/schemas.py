"""Schema CRUD routes."""

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Schema, Document, User
from app.schemas import SchemaOut, SchemaCreate, SchemaUpdate, SuccessResponse
from app.middleware.auth import get_current_user, require_role
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/schemas", tags=["Schemas"])


@router.get("/", response_model=list[SchemaOut])
async def list_schemas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Schema).order_by(Schema.name))
    schemas = result.scalars().all()
    out = []
    for s in schemas:
        sout = _parse_schema(s)
        count_res = await db.execute(select(func.count(Document.id)).where(Document.schema_id == s.id))
        sout.doc_count = count_res.scalar() or 0
        out.append(sout)
    return out


@router.get("/{schema_id}", response_model=SchemaOut)
async def get_schema(
    schema_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Schema not found")
    return _parse_schema(s)


@router.post("/", response_model=SchemaOut, status_code=201)
async def create_schema(
    body: SchemaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    schema = Schema(
        id=str(uuid.uuid4()),
        name=body.name,
        doc_type=body.doc_type,
        version=body.version,
        definition=json.dumps(body.definition),
        validation_rules=json.dumps(body.validation_rules),
        created_by=current_user.id,
    )
    db.add(schema)
    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="SCHEMA_CREATED", resource_type="schema",
                          resource_id=schema.id, resource_name=body.name)
    await db.commit()
    return _parse_schema(schema)


@router.put("/{schema_id}", response_model=SuccessResponse)
async def update_schema(
    schema_id: str,
    body: SchemaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "editor")),
):
    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Schema not found")

    if body.name:             s.name = body.name
    if body.version:          s.version = body.version
    if body.definition:       s.definition = json.dumps(body.definition)
    if body.validation_rules: s.validation_rules = json.dumps(body.validation_rules)
    if body.status:           s.status = body.status

    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="SCHEMA_UPDATED", resource_type="schema", resource_id=schema_id)
    await db.commit()
    return SuccessResponse()


@router.delete("/{schema_id}", response_model=SuccessResponse)
async def delete_schema(
    schema_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Schema not found")

    await db.delete(s)
    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="SCHEMA_DELETED", resource_type="schema", resource_id=schema_id)
    await db.commit()
    return SuccessResponse()


def _parse_schema(s: Schema) -> SchemaOut:
    out = SchemaOut.model_validate(s)
    out.definition = json.loads(s.definition) if isinstance(s.definition, str) else s.definition
    out.validation_rules = json.loads(s.validation_rules) if s.validation_rules else []
    return out
