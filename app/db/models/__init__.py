"""ORM 模型导出模块。

集中导入所有 ORM 模型类，确保：
1. 所有表定义在应用启动时即注册到 Base.metadata（Alembic 迁移需要完整的 metadata）
2. 关联表（如 item_tags / article_tags）的定义在引用它们的模型之前导入

导入顺序说明：
- Tag 最先导入：因为 item_tags 关联表定义在 tag.py 中，而 Item 模型的 tags 字段引用了该表
- 其余模型按依赖顺序导入（被引用的在前）

__all__ 列表用于 from app.db.models import * 的导出控制。
"""

from app.db.models.tag import Tag  # noqa: F401 - 包含 item_tags 关联表，必须在 Item 之前导入
from app.db.models.comment import Comment  # noqa: F401
from app.db.models.article import Article  # noqa: F401
from app.db.models.favorite import Favorite  # noqa: F401
from app.db.models.follower import Follower  # noqa: F401
from app.db.models.item import Item
from app.db.models.user import User

__all__ = ["User", "Item", "Tag", "Comment", "Article", "Favorite", "Follower"]
