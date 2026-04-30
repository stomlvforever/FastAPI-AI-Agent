"""用户相关 Pydantic Schema。

区分注册请求、公开用户响应、普通用户资料更新和管理员资料更新结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str
    # role is not in UserCreate - new users are always "user"
    # Only a DB admin or migration can set role to "admin"


class UserPublic(UserBase):
    id: int
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """普通用户更新自己的资料（只允许改这些字段）"""
    full_name: str | None = None
    bio: str | None = None
    image: str | None = None


class AdminUserProfileUpdate(BaseModel):
    """管理员更新任意用户的资料"""
    full_name: str | None = None
    email: EmailStr | None = None
    bio: str | None = None
    image: str | None = None
    role: str | None = None
