"""标签业务服务。

负责标签创建、删除、重复校验和标签查询逻辑。"""

from app.repositories.tag_repo import TagRepository
from app.schemas.tag import TagCreate


class TagService:
    def __init__(self, repo: TagRepository):
        self.repo = repo

    async def create_tag(self, payload: TagCreate):
        """创建标签（若同名已存在则返回已有的）。"""
        existing = await self.repo.get_by_name(payload.name)
        if existing:
            return existing
        return await self.repo.create(payload.name)

    async def list_tags(self):
        """获取所有标签。"""
        return await self.repo.list_all()

    async def delete_tag(self, tag_id: int):
        """删除标签：不存在则返回 None。"""
        tag = await self.repo.get(tag_id)
        if not tag:
            return None
        return await self.repo.delete(tag)

    async def add_tag_to_item(self, item_id: int, tag_id: int):
        """给 Item 添加标签。"""
        await self.repo.add_tag_to_item(item_id, tag_id)

    async def remove_tag_from_item(self, item_id: int, tag_id: int):
        """从 Item 移除标签。"""
        await self.repo.remove_tag_from_item(item_id, tag_id)

    async def get_tags_for_item(self, item_id: int):
        """获取 Item 的所有标签。"""
        return await self.repo.get_tags_for_item(item_id)

