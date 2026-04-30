"""关注 ORM 模型。

定义用户之间的关注关系（Follow）——这是一个自关联的对称关系模型：
- follower_id：关注者（主动关注他人的用户）
- following_id：被关注者（被他人关注的用户）

设计要点：
1. 联合主键 (follower_id, following_id)：保证同一用户不会重复关注同一个人
2. PK 索引只覆盖左前缀 follower_id：
   - "我关注了谁" → WHERE follower_id=? 走 PK 索引（快）
   - "谁关注了我"（粉丝列表）→ WHERE following_id=? 不走 PK 索引
   - Feed 查询的 JOIN → ON following_id=? 不走 PK 索引
   → 所以显式创建了 ix_followers_following_id 索引
3. 此表用途：
   - 关注/取消关注操作
   - 粉丝列表（followers）
   - 关注列表（following）
   - Feed 流（关注者的文章聚合）
"""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Follower(Base):
    """关注关联表——记录用户之间的社交关注关系。"""

    __tablename__ = "followers"

    # ---- 联合主键 ----
    follower_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # 关注者：ondelete="CASCADE" 删除用户时清理其关注关系

    following_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # 被关注者：ondelete="CASCADE" 删除用户时清理其被关注关系

    # ---- 表级约束 ----
    # 显式索引：PK 索引是 (follower_id, following_id)，
    # 对 following_id 的查询（粉丝列表 / Feed JOIN）需要单独索引
    __table_args__ = (
        Index("ix_followers_following_id", "following_id"),
    )
