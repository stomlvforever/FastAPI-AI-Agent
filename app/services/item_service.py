"""Item 业务服务。

负责 Item 的创建、更新、删除、查询和资源权限控制。"""

from app.db.models.item import Item
from app.repositories.item_repo import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, repo: ItemRepository):
        self.repo = repo

    async def create_item(self, owner_id: int, payload: ItemCreate):
        return await self.repo.create(
            owner_id,
            payload.title,
            payload.description,
            payload.priority,
            payload.status,
        )

    async def list_items(
        self,
        owner_id: int,
        skip: int = 0,
        limit: int = 100,
        priority: int | None = None,
        status: str | None = None,
        sort_by: str = "priority",
        order: str = "asc",
    ):
        return await self.repo.list_by_owner(
            owner_id,
            skip=skip,
            limit=limit,
            priority=priority,
            status=status,
            sort_by=sort_by,
            order=order,
        )

    async def get_item(self, item_id: int, target_item: Item | None = None):
        """Get item and avoid duplicate SELECT when target_item is provided."""
        return target_item or await self.repo.get(item_id)

    async def update_item(self, item_id: int, payload: ItemUpdate, target_item: Item | None = None):
        """Update item and avoid duplicate SELECT when target_item is provided."""
        item = target_item or await self.repo.get(item_id)
        if not item:
            return None
        data = payload.model_dump(exclude_unset=True)
        return await self.repo.update(item, data)

    async def delete_item(self, item_id: int, target_item: Item | None = None):
        """Delete item and avoid duplicate SELECT when target_item is provided."""
        item = target_item or await self.repo.get(item_id)
        if not item:
            return None
        return await self.repo.delete(item)

