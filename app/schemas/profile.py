"""用户资料相关 Pydantic Schema。

定义公开资料和个人资料更新响应结构，避免泄露密码等敏感字段。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfilePublic(BaseModel):
    """个人资料响应体：对外展示的用户信息。"""
    id: int
    email: str
    full_name: str | None = None
    bio: str | None = None
    image: str | None = None
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileWithFollow(ProfilePublic):
    """Profile with follow status."""
    following: bool = False


class ProfileUpdate(BaseModel):
    """更新个人资料请求体：所有字段可选。"""
    full_name: str | None = None
    bio: str | None = None
    image: str | None = None

