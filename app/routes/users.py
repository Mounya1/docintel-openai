"""User management routes (admin only)."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserCreate, UserUpdate, SuccessResponse
from app.services.auth import hash_password
from app.middleware.auth import get_current_user, require_role
from app.utils.audit import write_audit_log

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).order_by(User.name))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already in use")

    initials = "".join(p[0] for p in body.name.split()).upper()[:2]
    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower(),
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role,
        department=body.department,
        avatar_initials=initials,
    )
    db.add(user)
    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="USER_CREATED", resource_type="user",
                          resource_id=user.id, resource_name=body.name)
    await db.commit()
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=SuccessResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name:        user.name = body.name
    if body.role:        user.role = body.role
    if body.department:  user.department = body.department
    if body.mfa_enabled is not None: user.mfa_enabled = body.mfa_enabled

    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="USER_UPDATED", resource_type="user", resource_id=user_id)
    await db.commit()
    return SuccessResponse()


@router.delete("/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False  # Soft delete to preserve audit trail
    await write_audit_log(db=db, user_id=current_user.id, user_name=current_user.name,
                          action="USER_DELETED", resource_type="user", resource_id=user_id)
    await db.commit()
    return SuccessResponse()
