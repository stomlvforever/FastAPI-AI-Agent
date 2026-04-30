"""文章数据访问层（Article Repository）。

封装 Article 模型的数据库操作：查询、创建、更新、删除、标签关联。

核心查询优化：
文章列表排序直接读取 Article 表中的物化计数字段，例如 favorites_count。
当前用户收藏状态（favorited）仍使用 EXISTS 子查询获取，避免 N+1 查询。

Feed 查询：
通过 JOIN followers 表，筛选"关注者的文章"，再 order by + offset/limit。
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.article import Article
from app.db.models.favorite import Favorite
from app.db.models.follower import Follower
from app.db.models.tag import Tag


class ArticleRepository:
    """文章数据访问层——封装 Article 表的所有数据库操作。

    核心亮点：列表排序读取物化计数字段，避免实时聚合关联表。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 收藏状态子查询构造器
    # ========================================================================

    def _favorited_subquery(self, user_id: int):
        """构造当前用户收藏状态 EXISTS 子查询。

        返回值：
        - favorited: exists 子查询，判断当前用户是否收藏了该文章
          SELECT EXISTS(SELECT 1 FROM favorites WHERE article_id = a.id AND user_id = ?)
        """
        # 当前用户收藏状态：EXISTS(subquery) WHERE article_id = 外层 Article.id AND user_id = ?
        return (
            select(Favorite.user_id)
            .where(
                Favorite.article_id == Article.id,
                Favorite.user_id == user_id,
            )
            .exists()                  # SQL EXISTS 子查询，返回 bool
        )

    def _sort_column(self, sort_by: str):
        """按白名单解析排序字段，非法字段回退到 created_at。"""
        allowed_sort = {
            "created_at": Article.created_at,
            "updated_at": Article.updated_at,
            "title": Article.title,
            "favorites_count": Article.favorites_count,
            "comments_count": Article.comments_count,
            "references_count": Article.references_count,
            "views_count": Article.views_count,
        }
        return allowed_sort.get(sort_by, Article.created_at)

    def _apply_stable_order(self, query, sort_by: str, order: str):
        """应用稳定排序，同值时用 id 兜底，避免分页边界抖动。"""
        sort_column = self._sort_column(sort_by)
        normalized_order = order.lower() if isinstance(order, str) else "desc"
        if normalized_order == "asc":
            return query.order_by(sort_column.asc(), Article.id.asc())
        return query.order_by(sort_column.desc(), Article.id.desc())

    # ========================================================================
    # 查询方法
    # ========================================================================

    async def get(self, article_id: int) -> Article | None:
        """按主键获取文章。"""
        return await self.session.get(Article, article_id)

    async def get_by_slug(self, slug: str) -> Article | None:
        """按 slug 获取文章（用于文章详情页路由 /articles/{slug}）。
        selectinload：一次额外的 IN 查询加载所有关联标签。"""
        result = await self.session.execute(
            select(Article)
            .where(Article.slug == slug)
            .options(selectinload(Article.tags))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_with_favorites(self, slug: str, user_id: int) -> Article | None:
        """按 slug 获取文章 + 当前用户收藏状态。

        这是文章详情页的查询——一次 SQL 返回三组信息：
        1. Article 对象（含 tags）
        2. favorited（当前登录用户是否已收藏，bool）

        使用 label 别名将子查询结果映射到动态属性上：
        读取时用 article.favorited，favorites_count 是 ORM 声明列。
        """
        favorited = self._favorited_subquery(user_id)
        result = await self.session.execute(
            select(
                Article,
                favorited.label("favorited"),
            )
            .where(Article.slug == slug)
            .options(selectinload(Article.tags))
            .execution_options(populate_existing=True)
        )
        row = result.first()
        if not row:
            return None
        # row 是 (Article, bool) 元组
        article, favorited_value = row
        # 将子查询结果注入为动态属性
        article.favorited = bool(favorited_value)
        return article

    async def list(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        tag: str | None = None,
        author_id: int | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> list[Article]:
        """文章列表查询——支持标签过滤、作者过滤、收藏状态、动态排序。

        user_id 用于收藏状态子查询，author_id 用于按作者过滤文章。

        排序白名单防止恶意字段参与 SQL 排序。收藏数、评论数、引用数等指标
        直接读取 Article 表的物化列，不在列表查询中实时统计关联表。
        """
        favorited = self._favorited_subquery(user_id)

        # 基础查询：Article + 当前用户收藏状态 + 预加载标签
        query = (
            select(
                Article,
                favorited.label("favorited"),
            )
            .options(selectinload(Article.tags))
            .execution_options(populate_existing=True)
        )

        # 标签过滤：any() → EXISTS(subquery WHERE tag.name = ?)
        if tag:
            query = query.where(Article.tags.any(Tag.name == tag))

        # 作者过滤
        if author_id is not None:
            query = query.where(Article.author_id == author_id)

        query = self._apply_stable_order(query, sort_by, order).offset(skip).limit(limit)
        result = await self.session.execute(query)

        # 逐行打包：将当前用户收藏状态注入为 Article 的动态属性
        articles: list[Article] = []
        for article, favorited_value in result.all():
            article.favorited = bool(favorited_value)
            articles.append(article)
        return articles

    async def list_feed(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> list[Article]:
        """Feed 查询——当前用户关注的人发表的文章。

        核心逻辑：
        JOIN followers ON followers.following_id = articles.author_id
        WHERE followers.follower_id = ?

        这样只查询"我关注的人"的文章，而非全量文章。

        性能提示：
        followers 表使用联合 PK (follower_id, following_id)，
        WHERE follower_id=? 能走 PK 索引（高效）。
        JOIN 的 following_id 靠 ix_followers_following_id 索引支持。
        """
        favorited = self._favorited_subquery(user_id)

        query = (
            select(
                Article,
                favorited.label("favorited"),
            )
            .join(Follower, Follower.following_id == Article.author_id)
            .where(Follower.follower_id == user_id)
            .options(selectinload(Article.tags))
            .execution_options(populate_existing=True)
        )

        query = self._apply_stable_order(query, sort_by, order).offset(skip).limit(limit)
        result = await self.session.execute(query)

        articles: list[Article] = []
        for article, favorited_value in result.all():
            article.favorited = bool(favorited_value)
            articles.append(article)
        return articles

    async def recalculate_counters(self) -> dict[str, int]:
        """重新统计可校准的文章计数字段。

        当前项目已有 favorites 关联表，所以 favorites_count 可以从真实收藏关系回填。
        项目暂未提供文章评论表和文章引用表，comments_count 与 references_count 先校准为 0。
        views_count 没有独立访问流水表，这里保留现有值。
        """
        article_total = await self.session.scalar(select(func.count(Article.id)))
        favorite_rows = await self.session.execute(
            select(Favorite.article_id, func.count(Favorite.user_id))
            .group_by(Favorite.article_id)
        )
        favorite_counts = [(article_id, int(count)) for article_id, count in favorite_rows.all()]

        await self.session.execute(
            update(Article).values(
                favorites_count=0,
                comments_count=0,
                references_count=0,
            )
        )
        for article_id, count in favorite_counts:
            await self.session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(favorites_count=count)
            )

        await self.session.commit()
        return {
            "articles_checked": int(article_total or 0),
            "favorites_rows_backfilled": len(favorite_counts),
            "comments_rows_backfilled": 0,
            "references_rows_backfilled": 0,
        }

    # ========================================================================
    # 写方法
    # ========================================================================

    async def create(
        self,
        author_id: int,
        title: str,
        slug: str,
        description: str | None,
        body: str,
    ) -> Article:
        """创建新文章。slug 由调用方（Service 层或工具层）生成后传入。"""
        article = Article(
            author_id=author_id,
            title=title,
            slug=slug,
            description=description,
            body=body,
        )
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def update(self, article: Article, data: dict) -> Article:
        """按字典更新文章字段。updated_at 由数据库 onupdate=func.now() 自动刷新。"""
        for key, value in data.items():
            setattr(article, key, value)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def set_tags(self, article: Article, tags: list[Tag]) -> Article:
        """设置文章的标签关联（替换全部标签）。
        SQLAlchemy 的 secondary 关系会自动管理关联表的 INSERT/DELETE。"""
        article.tags = tags
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def delete(self, article: Article) -> Article:
        """删除文章。ORM 的 cascade 设置决定关联表记录是否同步删除。"""
        await self.session.delete(article)
        await self.session.commit()
        return article
