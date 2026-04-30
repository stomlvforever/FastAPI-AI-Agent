"""评论接口。

提供评论查询、创建和删除能力，并衔接评论服务层和权限控制。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.db import SessionDep
from app.core.permissions import check_comment_owner
from app.db.models.comment import Comment
from app.repositories.comment_repo import CommentRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.user_repo import UserRepository
from app.schemas.comment import CommentCreate, CommentPublic
from app.services.comment_service import CommentService
from app.services.task_dispatch_service import TaskDispatchService

router = APIRouter()


@router.get("/items/{item_id}/comments", response_model=list[CommentPublic])
async def list_comments(
    item_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    item = await ItemRepository(session).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    service = CommentService(CommentRepository(session))
    return await service.list_comments(item_id)


@router.post("/items/{item_id}/comments", response_model=CommentPublic, status_code=201)
async def create_comment(
    item_id: int,
    payload: CommentCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    item = await ItemRepository(session).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    service = CommentService(CommentRepository(session))
    return await service.create_comment(item_id, current_user.id, payload)


@router.delete("/items/{item_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    item_id: int,
    comment_id: int,
    target_comment: Annotated[Comment, Depends(check_comment_owner)],
    session: SessionDep,
    current_user: CurrentUser,
):
    # Keep nested route semantics: comment must belong to this item path.
    if target_comment.item_id != item_id:
        raise HTTPException(status_code=404, detail="Comment not found")

    service = CommentService(CommentRepository(session))
    result = await service.delete_comment_by_target(target_comment)
    if not result:
        raise HTTPException(status_code=404, detail="Comment not found")

    is_admin = current_user.role == "admin"
    is_owner = target_comment.author_id == current_user.id
    if is_admin and not is_owner:
        user_repo = UserRepository(session)
        author = await user_repo.get_by_id(target_comment.author_id)
        if author:
            TaskDispatchService().queue_notification_email_safe(
                author.email,
                "Your comment has been deleted by admin",
                f"Your comment on Item #{item_id} was deleted by administrator due to moderation.",
            )

    return None

