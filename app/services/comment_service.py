"""评论业务服务。

负责评论创建、删除、资源归属和评论相关业务规则。"""

from app.db.models.comment import Comment
from app.repositories.comment_repo import CommentRepository
from app.schemas.comment import CommentCreate


class CommentService:
    def __init__(self, repo: CommentRepository):
        self.repo = repo

    async def create_comment(self, item_id: int, author_id: int, payload: CommentCreate):
        """创建评论。"""
        return await self.repo.create(item_id, author_id, payload.body)

    async def list_comments(self, item_id: int):
        """获取 Item 下的所有评论。"""
        return await self.repo.list_by_item(item_id)

    async def delete_comment(self, comment_id: int, user_id: int):
        """
        删除评论（只有评论作者本人可以删除）。
        返回 None 表示评论不存在，返回 False 表示没有权限。
        """
        comment = await self.repo.get(comment_id)
        if not comment:
            return None
        if comment.author_id != user_id:
            return False
        return await self.repo.delete(comment)

    async def delete_comment_by_target(self, target_comment: Comment):
        """Delete comment that has passed external permission checks."""
        return await self.repo.delete(target_comment)

