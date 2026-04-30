"""权限判断模块（Permissions）。

提供 ABAC（Attribute-Based Access Control）资源级权限检查。
区别于 auth.py 的角色级权限（user vs admin），permissions.py 关注的是：
"当前用户是否有权操作这个具体的资源（文章/评论/Item）？"

三种权限策略对比：
1. check_article_owner：所有者 OR 管理员可操作；非所有者非管理员 → 403 Forbidden
2. check_comment_owner：同 check_article_owner，404 → 403 逻辑
3. check_item_owner：所有者 OR 管理员可操作；非所有者 → 404 Not Found（隐藏资源存在性）

为什么 Item 用 404 而 Article/Comment 用 403？
- Item 更偏"私人物品"，非所有者不应感知到该资源的存在 → 404 更合适
- Article 是公开内容，任何人都知道该文章存在，但只有所有者能修改 → 403 更合适
- Comment 同理，评论是公开可见的，但删除权限于作者和管理员

FastAPI 的依赖注入：这些函数可以直接用作路由的 Dependency，
无需在路由函数体中手动调用。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.db import get_db
from app.db.models.article import Article
from app.db.models.comment import Comment
from app.db.models.item import Item
from app.repositories.article_repo import ArticleRepository
from app.repositories.item_repo import ItemRepository


async def check_article_owner(
    slug: Annotated[str, Path(description="The slug of the article")],
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Article:
    """检查当前用户是否有权修改/删除指定文章。

    权限逻辑：
    1. 文章不存在 → 404
    2. 当前用户是管理员 → 允许（返回 Article 对象，直接注入路由函数）
    3. 当前用户是文章作者 → 允许
    4. 都不是 → 403 Forbidden

    返回的 Article 对象可以直接在路由函数中使用，省去再次查询。
    """
    article = await ArticleRepository(session).get_by_slug(slug)

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # 管理员直接放行
    if user.role == "admin":
        return article

    # 非作者拒绝访问
    if article.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this article",
        )

    return article


async def check_comment_owner(
    comment_id: Annotated[int, Path(description="The ID of the comment")],
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Comment:
    """检查当前用户是否有权删除指定评论。

    权限逻辑（与 check_article_owner 一致）：
    1. 评论不存在 → 404
    2. 管理员 → 允许
    3. 评论作者 → 允许
    4. 都不是 → 403
    """
    from sqlalchemy import select

    result = await session.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if user.role == "admin":
        return comment

    if comment.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this comment",
        )
    return comment


async def check_item_owner(
    item_id: Annotated[int, Path(description="The ID of the item")],
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Item:
    """检查当前用户是否有权查看/修改/删除指定 Item。

    权限逻辑（与 Article 的不同——隐藏存在性）：
    1. Item 不存在 → 404
    2. 管理员 → 允许
    3. Item 所有者 → 允许
    4. 都不是 → 404（而非 403！）

    为什么用 404 而非 403？
    Item 是私人物品型资源，非所有者不应感知到该 Item 是否存在。
    如果用 403，攻击者可以通过"403 = 存在但没权限 vs 404 = 不存在"
    来探测其他用户的资源。统一返回 404 避免这个信息泄露。
    """
    item = await ItemRepository(session).get(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # 管理员或所有者放行，非所有者 → 404（隐藏资源存在性）
    if user.role != "admin" and item.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found")

    return item
