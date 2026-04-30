"""用户 ORM 模型。

定义用户的账户、角色、个人资料以及与其他表的关联关系。

User 是系统的核心实体，其他模型通过外键关联到用户：
- Item.owner_id → User.id（一对多：一个用户拥有多个 Item）
- Article.author_id → User.id（一对多：一个用户发表多篇文章）
- Comment.author_id → User.id（一对多：一个用户发表多条评论）
- Favorite.user_id → User.id（多对多：收藏关系）
- Follower.follower_id / following_id → User.id（多对多：关注关系，自关联）

字段设计：
- email：唯一索引，作为登录凭据
- hashed_password：bcrypt 哈希（非明文）
- role：'user'/'admin'，RBAC 权限模型的核心字段
- is_active：控制账户启用/禁用的开关（用于封禁功能）
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """用户表——系统用户的核心实体。"""

    __tablename__ = "users"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- 基本字段 ----
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # 邮箱：唯一索引（用于登录查找）、不能为空

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # 密码 bcrypt 哈希：256 位以上（60 字符 hex → 存 255 足够）

    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 显示名：可选字段，未设置时显示邮箱

    # ---- Profile 功能扩展字段 ----
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 个人简介：TEXT 类型，支持长文本

    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 头像 URL：可指向本地 / S3 上的图片

    # ---- 状态与角色 ----
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 账户状态：True=正常，False=已封禁（禁用后无法登录）

    role: Mapped[str] = mapped_column(
        String(20), default="user", server_default="user"
    )
    # 角色：user=普通用户，admin=管理员（RBAC 权限模型的基石）

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # 注册时间：数据库自动填入当前时间

    # ============================================================================
    # Relationships（关联关系，非数据库列）
    # ============================================================================

    # 与 Item 的一对多关系（一个用户拥有多个 Item）
    # back_populates="owner"：对应 Item 模型中的 owner 字段，形成双向关联
    items: Mapped[list["Item"]] = relationship("Item", back_populates="owner")

    # 与 Article 的一对多关系（一个用户发表多篇文章）
    articles: Mapped[list["Article"]] = relationship("Article", back_populates="author")

    # 与 Comment 的一对多关系（一个用户发表多条评论）
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="author")
