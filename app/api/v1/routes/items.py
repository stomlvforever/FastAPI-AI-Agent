"""Item 资源接口。

提供 Item 的增删改查、标签关联和当前用户资源权限控制。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.db import SessionDep
from app.core.permissions import check_item_owner
from app.db.models.item import Item
from app.repositories.item_repo import ItemRepository
from app.repositories.user_repo import UserRepository
from app.schemas.item import ItemCreate, ItemPublic, ItemUpdate
from app.services.item_service import ItemService
from app.services.task_dispatch_service import TaskDispatchService

router = APIRouter()


@router.post("/items", response_model=ItemPublic, status_code=201)
async def create_item(
    payload: ItemCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ItemService(ItemRepository(session))
    return await service.create_item(current_user.id, payload)


@router.get("/items", response_model=list[ItemPublic])
async def list_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    priority: int | None = None,
    status: str | None = None,
    sort_by: str = "priority",
    order: str = "asc",
):
    service = ItemService(ItemRepository(session))
    return await service.list_items(
        current_user.id,
        skip=skip,
        limit=limit,
        priority=priority,
        status=status,
        sort_by=sort_by,
        order=order,
    )


@router.get("/items/{item_id}", response_model=ItemPublic)
async def get_item(
    item_id: int,
    target_item: Annotated[Item, Depends(check_item_owner)],
    session: SessionDep,
):
    service = ItemService(ItemRepository(session))
    return await service.get_item(item_id, target_item=target_item)


@router.put("/items/{item_id}", response_model=ItemPublic)
async def update_item(
    item_id: int,
    payload: ItemUpdate,
    target_item: Annotated[Item, Depends(check_item_owner)],
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ItemService(ItemRepository(session))
    is_admin = current_user.role == "admin"
    updated = await service.update_item(item_id, payload, target_item=target_item)
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")

    if is_admin and target_item.owner_id != current_user.id:
        user_repo = UserRepository(session)
        owner = await user_repo.get_by_id(target_item.owner_id)
        if owner:
            TaskDispatchService().queue_notification_email_safe(
                owner.email,
                "Your item has been updated by admin",
                f"Item '{target_item.title}' (ID: {target_item.id}) was updated by administrator.",
            )

    return updated


@router.delete("/items/{item_id}", response_model=ItemPublic)
async def delete_item(
    item_id: int,
    target_item: Annotated[Item, Depends(check_item_owner)],
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ItemService(ItemRepository(session))
    is_admin = current_user.role == "admin"
    deleted = await service.delete_item(item_id, target_item=target_item)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")

    if is_admin and target_item.owner_id != current_user.id:
        user_repo = UserRepository(session)
        owner = await user_repo.get_by_id(target_item.owner_id)
        if owner:
            TaskDispatchService().queue_notification_email_safe(
                owner.email,
                "Your item has been deleted by admin",
                f"Item '{target_item.title}' (ID: {target_item.id}) was deleted by administrator.",
            )

    return deleted

