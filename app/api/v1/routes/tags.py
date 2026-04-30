"""标签接口。

提供标签查询、创建和删除能力，并支撑文章和 Item 的标签体系。"""

from fastapi import APIRouter, HTTPException

from app.api.dependencies.auth import AdminUser, CurrentUser
from app.api.dependencies.db import SessionDep
from app.repositories.item_repo import ItemRepository
from app.repositories.tag_repo import TagRepository
from app.schemas.tag import TagCreate, TagPublic
from app.services.tag_service import TagService

router = APIRouter()


# ---------- 标签 CRUD ----------

@router.get("/tags", response_model=list[TagPublic])
async def list_tags(session: SessionDep):
    """获取所有标签（无需登录）。"""
    service = TagService(TagRepository(session))
    return await service.list_tags()


@router.post("/tags", response_model=TagPublic, status_code=201)
async def create_tag(
    payload: TagCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    """创建新标签（需要登录）。如果同名标签已存在，直接返回已有的。"""
    service = TagService(TagRepository(session))
    return await service.create_tag(payload)


@router.delete("/tags/{tag_id}", response_model=TagPublic)
async def delete_tag(
    tag_id: int,
    session: SessionDep,
    admin_user: AdminUser,  # 只有管理员可以删除标签
):
    """删除标签（需要管理员权限）。"""
    service = TagService(TagRepository(session))
    tag = await service.delete_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


# ---------- Item-Tag 关联操作 ----------

@router.post("/items/{item_id}/tags/{tag_id}", status_code=204)
async def add_tag_to_item(
    item_id: int,
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """给自己的 Item 添加一个标签。"""
    # 验证 Item 存在且属于当前用户
    item = await ItemRepository(session).get(item_id)
    if not item or item.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    # 验证 Tag 存在
    tag_repo = TagRepository(session)
    tag = await tag_repo.get(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    service = TagService(tag_repo)
    await service.add_tag_to_item(item_id, tag_id)


@router.delete("/items/{item_id}/tags/{tag_id}", status_code=204)
async def remove_tag_from_item(
    item_id: int,
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """从自己的 Item 移除一个标签。"""
    item = await ItemRepository(session).get(item_id)
    if not item or item.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    service = TagService(TagRepository(session))
    await service.remove_tag_from_item(item_id, tag_id)


@router.get("/items/{item_id}/tags", response_model=list[TagPublic])
async def get_item_tags(
    item_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """获取自己的 Item 所有标签。"""
    item = await ItemRepository(session).get(item_id)
    if not item or item.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    service = TagService(TagRepository(session))
    return await service.get_tags_for_item(item_id)

