"""标签相关 Pydantic Schema。

定义标签创建和公开响应结构。"""

from pydantic import BaseModel, ConfigDict


class TagCreate(BaseModel):
    """创建标签请求体：只需要一个标签名。"""
    name: str


class TagPublic(BaseModel):
    """标签响应体：返回 id 和 name。"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

