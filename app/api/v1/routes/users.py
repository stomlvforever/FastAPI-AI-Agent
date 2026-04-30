"""普通用户接口。

提供用户注册、用户查询等公开或登录用户可用的用户能力。"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.dependencies.auth import AdminUser, CurrentUser
from app.api.dependencies.db import SessionDep
from app.rate_limit.limiter import limiter
from app.repositories.item_repo import ItemRepository
from app.repositories.user_repo import UserRepository
from app.schemas.item import ItemPublic
from app.schemas.user import UserCreate, UserProfileUpdate, UserPublic
from app.services.user_service import UserService

router = APIRouter()


@router.post("/users", response_model=UserPublic, status_code=201)
@limiter.limit("5/minute")  # 注册接口限流：每分钟 5 次
async def register_user(request: Request, response: Response, payload: UserCreate, session: SessionDep):
    # 用户服务：注册新用户
    service = UserService(UserRepository(session))
    existing = await service.get_by_email(payload.email)
    if existing:
        # 邮箱已存在
        raise HTTPException(status_code=400, detail="Email already registered")
    return await service.register_user(payload)


@router.get("/users/me", response_model=UserPublic)
async def read_me(current_user: CurrentUser):
    # 直接返回当前登录用户
    return current_user


@router.put("/users/me", response_model=UserPublic)
async def update_me(
    payload: UserProfileUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Update current user's own profile (full_name / bio / image)."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    repo = UserRepository(session)
    updated = await repo.update(current_user, data)
    await session.commit()
    return updated


@router.get("/users", response_model=list[UserPublic])
async def list_users(session: SessionDep, admin: AdminUser, skip: int = 0, limit: int = 100):
    # 分页查询用户列表（仅管理员可查看所有用户）
    service = UserService(UserRepository(session))
    return await service.list_users(skip=skip, limit=limit)


@router.get("/admin/all-items", response_model=list[ItemPublic])
async def admin_list_all_items(
    session: SessionDep,
    admin: AdminUser,  # <-- This line does ALL the permission checking!
    skip: int = 0,
    limit: int = 100,
):
    """
    Admin-only: list ALL items from ALL users.
    Regular users will get 403 Forbidden.
    """
    from sqlalchemy import select
    from app.db.models.item import Item

    result = await session.execute(
        select(Item).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


