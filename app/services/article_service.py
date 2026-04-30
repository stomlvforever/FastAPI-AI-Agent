"""文章业务服务。

负责文章 slug 生成、作者权限、标签处理和文章业务规则。"""

from slugify import slugify

from app.db.models.article import Article
from app.repositories.article_repo import ArticleRepository
from app.repositories.tag_repo import TagRepository
from app.schemas.article import ArticleCreate, ArticleUpdate


class ArticleService:
    def __init__(self, repo: ArticleRepository, tag_repo: TagRepository):
        self.repo = repo
        self.tag_repo = tag_repo

    async def _generate_unique_slug(self, title: str, exclude_id: int | None = None) -> str:
        base = slugify(title) or "article"
        slug = base
        suffix = 1
        while True:
            existing = await self.repo.get_by_slug(slug)
            if not existing or (exclude_id is not None and existing.id == exclude_id):
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1

    async def _get_or_create_tags(self, tag_names: list[str]) -> list:
        tags = []
        unique_names = []
        for name in tag_names:
            clean = name.strip()
            if clean and clean not in unique_names:
                unique_names.append(clean)
        for name in unique_names:
            existing = await self.tag_repo.get_by_name(name)
            if existing:
                tags.append(existing)
            else:
                tags.append(await self.tag_repo.create(name))
        return tags

    async def create_article(self, author_id: int, payload: ArticleCreate):
        slug = await self._generate_unique_slug(payload.title)
        article = await self.repo.create(
            author_id=author_id,
            title=payload.title,
            slug=slug,
            description=payload.description,
            body=payload.body,
        )
        if payload.tag_names:
            tags = await self._get_or_create_tags(payload.tag_names)
            article = await self.repo.set_tags(article, tags)
        article.favorites_count = 0
        article.comments_count = 0
        article.references_count = 0
        article.views_count = 0
        article.favorited = False
        return article

    async def list_articles(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        tag: str | None = None,
        author_id: int | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ):
        return await self.repo.list(
            user_id=user_id,
            skip=skip,
            limit=limit,
            tag=tag,
            author_id=author_id,
            sort_by=sort_by,
            order=order,
        )

    async def get_article(self, slug: str, user_id: int):
        return await self.repo.get_with_favorites(slug, user_id)

    async def update_article(
        self,
        slug: str,
        user_id: int,
        payload: ArticleUpdate,
        target_article: Article | None = None,
    ):
        article = target_article or await self.repo.get_by_slug(slug)
        if not article:
            return None
        data = payload.model_dump(exclude_unset=True)
        tag_names = data.pop("tag_names", None)
        if "title" in data:
            data["slug"] = await self._generate_unique_slug(data["title"], exclude_id=article.id)
        article = await self.repo.update(article, data)
        if tag_names is not None:
            tags = await self._get_or_create_tags(tag_names)
            article = await self.repo.set_tags(article, tags)
        return await self.repo.get_with_favorites(article.slug, user_id)

    async def delete_article(self, slug: str, target_article: Article | None = None):
        article = target_article or await self.repo.get_by_slug(slug)
        if not article:
            return None
        return await self.repo.delete(article)

    async def feed(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        order: str = "desc",
    ):
        return await self.repo.list_feed(
            user_id=user_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            order=order,
        )

