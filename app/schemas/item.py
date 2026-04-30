"""Item 相关 Pydantic Schema。

定义 Item 的创建、更新、公开响应，以及带标签的详情响应结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.tag import TagPublic


class ItemBase(BaseModel):
    title: str
    description: str | None = None
    # 优先级：1=高, 2=中, 3=低（默认低）
    priority: int = 3
    # 状态：pending=待办, done=已完成
    status: str = "pending"


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    status: str | None = None


class ItemPublic(ItemBase):
    id: int
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemPublicWithTags(ItemPublic):
    """带标签列表的 Item 响应体（用于详情接口）。"""
    tags: list[TagPublic] = []
