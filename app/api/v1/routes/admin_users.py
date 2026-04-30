"""管理员用户管理接口。

提供管理员查询、创建、删除、禁用、重置密码和资料更新等用户治理能力。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.dependencies.auth import AdminUser
from app.api.dependencies.db import SessionDep
from app.core.security import get_password_hash
from app.repositories.user_repo import UserRepository
from app.schemas.user import AdminUserProfileUpdate, UserPublic
from app.services.task_dispatch_service import TaskDispatchService

router = APIRouter()


class UserRoleUpdate(BaseModel):
    role: str


class UserStatusUpdate(BaseModel):
    is_active: bool


class AdminResetPassword(BaseModel):
    new_password: str


@router.put("/users/{user_id}/role", response_model=UserPublic)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    session: SessionDep,
    admin: AdminUser,
):
    """Admin: update user role."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await repo.update(user, {"role": payload.role})
    return updated_user


@router.put("/users/{user_id}/status", response_model=UserPublic)
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    session: SessionDep,
    admin: AdminUser,
):
    """Admin: ban or unban user and queue notification email."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await repo.update(user, {"is_active": payload.is_active})

    status_msg = "activated" if payload.is_active else "deactivated (banned)"
    subject = f"Your account has been {status_msg}"
    content = f"Your account status has been changed to: {status_msg} by administrator."
    TaskDispatchService().queue_notification_email_safe(updated_user.email, subject, content)

    return updated_user


@router.put("/users/{user_id}/reset-password", response_model=UserPublic)
async def reset_user_password(
    user_id: int,
    payload: AdminResetPassword,
    session: SessionDep,
    admin: AdminUser,
):
    """Admin: force reset user password and queue notification email."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = get_password_hash(payload.new_password)
    updated_user = await repo.update(user, {"hashed_password": hashed_password})

    TaskDispatchService().queue_notification_email_safe(
        updated_user.email,
        "Your password has been reset by admin",
        "Your password has been reset by administrator. Please login with the new password.",
    )

    return updated_user


@router.put("/users/{user_id}/profile", response_model=UserPublic)
async def update_user_profile(
    user_id: int,
    payload: AdminUserProfileUpdate,
    session: SessionDep,
    admin: AdminUser,
):
    """Admin: update any user's profile (full_name, email, bio, image, role)."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # 若要改邮箱，检查是否被占用
    if "email" in data:
        existing = await repo.get_by_email(data["email"])
        if existing and existing.id != user_id:
            raise HTTPException(status_code=409, detail="Email already in use")

    # 若要改角色，限制合法值
    if "role" in data and data["role"] not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")

    updated_user = await repo.update(user, data)
    await session.commit()
    return updated_user

