"""Audit log routes — list, export CSV."""

import json, csv, io
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogListResponse, AuditLogOut
from app.middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "reviewer")),
):
    q = select(AuditLog)
    if user_id:       q = q.where(AuditLog.user_id == user_id)
    if action:        q = q.where(AuditLog.action == action)
    if resource_type: q = q.where(AuditLog.resource_type == resource_type)
    if search:
        q = q.where(
            AuditLog.user_name.ilike(f"%{search}%") |
            AuditLog.action.ilike(f"%{search}%") |
            AuditLog.resource_name.ilike(f"%{search}%")
        )
    q = q.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    result = await db.execute(q)
    logs = result.scalars().all()

    total_res = await db.execute(select(func.count(AuditLog.id)))
    total = total_res.scalar()

    return AuditLogListResponse(
        logs=[_parse_log(l) for l in logs],
        total=total, limit=limit, offset=offset,
    )


@router.get("/export", response_class=StreamingResponse)
async def export_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10_000)
    )
    logs = result.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp", "User", "Action", "Resource Type", "Resource Name", "Details", "IP"])
    for l in logs:
        writer.writerow([l.created_at, l.user_name, l.action, l.resource_type, l.resource_name, l.details or "", l.ip_address or ""])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


@router.get("/actions")
async def distinct_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
    return [r[0] for r in result.all()]


def _parse_log(l: AuditLog) -> AuditLogOut:
    out = AuditLogOut.model_validate(l)
    out.details = json.loads(l.details) if l.details else None
    return out
