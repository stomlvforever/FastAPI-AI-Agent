"""评论相关 Pydantic Schema。

定义评论创建请求和公开响应结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CommentCreate(BaseModel):
    """创建评论请求体：只需要评论内容。"""
    body: str


class CommentPublic(BaseModel):
    """评论响应体：返回评论详情。"""
    id: int
    body: str
    item_id: int
    author_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

