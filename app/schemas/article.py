"""文章相关 Pydantic Schema。

定义文章创建、更新和公开响应的数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.tag import TagPublic


class ArticleBase(BaseModel):
    title: str
    description: str | None = None
    body: str
    tag_names: list[str] = []


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None
    tag_names: list[str] | None = None


class ArticlePublic(BaseModel):
    id: int
    title: str
    slug: str
    description: str | None = None
    body: str
    author_id: int
    created_at: datetime
    updated_at: datetime
    tags: list[TagPublic] = []
    favorites_count: int = 0
    comments_count: int = 0
    references_count: int = 0
    views_count: int = 0
    favorited: bool = False

    model_config = ConfigDict(from_attributes=True)
