"""Repository 层导出模块。

Repository 层的职责：封装 SQLAlchemy 数据访问操作，让 Service 层和 Route 层
不直接编写 SQL/ORM 查询。遵循"每一层只做一件事"的分层原则。

Repository 模式的优势：
1. 统一数据访问：所有查询集中管理，避免 SQL/ORM 散落在各路由中
2. 可测试性高：Mock Repository 比 Mock 整套 SQLAlchemy Session 容易得多
3. 查询复用：多路由需要相同查询时无需重复编写

导出清单：
- UserRepository     用户数据操作
- ItemRepository     待办事项数据操作
- ArticleRepository  文章数据操作（在 article_repo 模块中，需显式导入）
- CommentRepository  评论数据操作
- TagRepository      标签数据操作
- FavoriteRepository 收藏数据操作
- FollowRepository   关注数据操作
"""

from app.repositories.item_repo import ItemRepository
from app.repositories.user_repo import UserRepository

__all__ = ["UserRepository", "ItemRepository"]
