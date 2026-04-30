"""文章接口。

提供文章创建、查询、详情、更新、删除、收藏统计和权限控制入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import AdminUser, CurrentUser
from app.api.dependencies.db import SessionDep
from app.core.permissions import check_article_owner
from app.db.models.article import Article
from app.repositories.article_repo import ArticleRepository
from app.repositories.favorite_repo import FavoriteRepository
from app.repositories.tag_repo import TagRepository
from app.repositories.user_repo import UserRepository
from app.schemas.article import ArticleCreate, ArticlePublic, ArticleUpdate
from app.schemas.favorite import FavoriteArticleResponse
from app.services.article_service import ArticleService
from app.services.favorite_service import FavoriteService
from app.services.task_dispatch_service import TaskDispatchService

router = APIRouter()


@router.post("/articles", response_model=ArticlePublic, status_code=201)
async def create_article(
    payload: ArticleCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    return await service.create_article(current_user.id, payload)


@router.get("/articles", response_model=list[ArticlePublic])
async def list_articles(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
    tag: str | None = None,
    author_id: int | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
):
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    return await service.list_articles(
        current_user.id,
        skip=skip,
        limit=limit,
        tag=tag,
        author_id=author_id,
        sort_by=sort_by,
        order=order,
    )


@router.post("/articles/counters/recalculate")
async def recalculate_article_counters(
    session: SessionDep,
    _admin: AdminUser,
):
    """管理员手动校准文章物化计数字段。"""
    return await ArticleRepository(session).recalculate_counters()


@router.get("/articles/{slug}", response_model=ArticlePublic)
async def get_article(
    slug: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    article = await service.get_article(slug, current_user.id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.put("/articles/{slug}", response_model=ArticlePublic)
async def update_article(
    slug: str,
    payload: ArticleUpdate,
    target_article: Annotated[Article, Depends(check_article_owner)],
    session: SessionDep,
    current_user: CurrentUser,
):
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    updated = await service.update_article(
        slug,
        current_user.id,
        payload,
        target_article=target_article,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found")
    return updated


@router.delete("/articles/{slug}", response_model=ArticlePublic)
async def delete_article(
    slug: str,
    target_article: Annotated[Article, Depends(check_article_owner)],
    session: SessionDep,
    current_user: CurrentUser,
):
    """Delete an article (owner or admin only)."""
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    deleted = await service.delete_article(slug, target_article=target_article)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")

    if current_user.role == "admin" and target_article.author_id != current_user.id:
        user_repo = UserRepository(session)
        author = await user_repo.get_by_id(target_article.author_id)
        if author:
            TaskDispatchService().queue_notification_email_safe(
                author.email,
                "Your article has been deleted by admin",
                f"Your article '{target_article.title}' was deleted by administrator due to moderation.",
            )

    return deleted


@router.post("/articles/{slug}/favorite", response_model=FavoriteArticleResponse)
async def favorite_article(
    slug: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    article_repo = ArticleRepository(session)
    article = await article_repo.get_by_slug(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    await FavoriteService(FavoriteRepository(session)).add_favorite(current_user.id, article.id)
    service = ArticleService(article_repo, TagRepository(session))
    return await service.get_article(slug, current_user.id)


@router.delete("/articles/{slug}/favorite", response_model=FavoriteArticleResponse)
async def unfavorite_article(
    slug: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    article_repo = ArticleRepository(session)
    article = await article_repo.get_by_slug(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    await FavoriteService(FavoriteRepository(session)).remove_favorite(current_user.id, article.id)
    service = ArticleService(article_repo, TagRepository(session))
    return await service.get_article(slug, current_user.id)


@router.get("/feed", response_model=list[ArticlePublic])
async def get_feed(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    order: str = "desc",
):
    service = ArticleService(ArticleRepository(session), TagRepository(session))
    return await service.feed(
        current_user.id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order,
    )

