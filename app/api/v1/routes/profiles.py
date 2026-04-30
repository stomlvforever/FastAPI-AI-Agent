"""用户资料接口。

提供当前用户资料、公开资料和资料更新相关能力。"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.db import SessionDep
from app.core.config import BASE_DIR
from app.core.storage import get_storage_service
from app.repositories.follow_repo import FollowRepository
from app.repositories.user_repo import UserRepository
from app.schemas.profile import ProfilePublic, ProfileUpdate, ProfileWithFollow
from app.services.follow_service import FollowService
from app.services.profile_service import ProfileService

router = APIRouter()

# 允许的图片格式
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# 最大文件大小：2MB
MAX_SIZE = 2 * 1024 * 1024


@router.get("/profile", response_model=ProfilePublic)
async def get_my_profile(
    session: SessionDep,
    current_user: CurrentUser,
):
    """获取当前登录用户的个人资料。"""
    service = ProfileService(UserRepository(session))
    profile = await service.get_profile(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@router.put("/profile", response_model=ProfilePublic)
async def update_my_profile(
    payload: ProfileUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    """更新当前登录用户的个人资料（full_name, bio, image）。"""
    service = ProfileService(UserRepository(session))
    updated = await service.update_profile(current_user.id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.post("/profile/avatar", response_model=ProfilePublic)
async def upload_avatar(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    上传头像图片（通过 StorageService 抽象层）。

    流程：
    1. 校验文件类型和大小
    2. 调用 StorageService.save() 存储文件
    3. 删除旧头像
    4. 更新用户 image 字段
    """
    # 校验文件类型
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: jpg/png/gif/webp",
        )

    # 校验文件大小
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {MAX_SIZE} bytes (2MB)")
    await file.seek(0)

    # 通过抽象层保存文件（local 或 s3，由环境变量决定）
    storage = get_storage_service()
    url = await storage.save(file, folder="avatars")

    # 删除旧头像（忽略失败）
    if current_user.image:
        await storage.delete(current_user.image)

    # 更新数据库
    repo = UserRepository(session)
    await repo.update(current_user, {"image": url})

    service = ProfileService(repo)
    return await service.get_profile(current_user.id)


@router.get("/profiles/{user_id}", response_model=ProfileWithFollow)
async def get_profile(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Get any user's profile with follow status."""
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = FollowService(FollowRepository(session))
    return await service.attach_following_flag(user, current_user.id)


@router.post("/profiles/{user_id}/follow", response_model=ProfileWithFollow)
async def follow_user(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Follow a user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = FollowService(FollowRepository(session))
    await service.follow(current_user.id, user_id)
    user.following = True
    return user


@router.delete("/profiles/{user_id}/follow", response_model=ProfileWithFollow)
async def unfollow_user(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Unfollow a user."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot unfollow yourself")
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = FollowService(FollowRepository(session))
    await service.unfollow(current_user.id, user_id)
    user.following = False
    return user


@router.get("/profiles/{user_id}/followers", response_model=list[ProfileWithFollow])
async def list_followers(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
):
    """List user's followers."""
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = FollowService(FollowRepository(session))
    return await service.list_followers(user_id, current_user.id, skip=skip, limit=limit)


@router.get("/profiles/{user_id}/following", response_model=list[ProfileWithFollow])
async def list_following(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
):
    """List users that a user is following."""
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    service = FollowService(FollowRepository(session))
    return await service.list_following(user_id, current_user.id, skip=skip, limit=limit)

