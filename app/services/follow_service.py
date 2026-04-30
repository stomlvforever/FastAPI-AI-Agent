"""关注业务服务。

负责关注、取消关注、禁止关注自己等社交关系规则。"""

from app.repositories.follow_repo import FollowRepository


class FollowService:
    def __init__(self, repo: FollowRepository):
        self.repo = repo

    async def is_following(self, follower_id: int, following_id: int) -> bool:
        return await self.repo.is_following(follower_id, following_id)

    async def follow(self, follower_id: int, following_id: int) -> None:
        await self.repo.follow(follower_id, following_id)

    async def unfollow(self, follower_id: int, following_id: int) -> None:
        await self.repo.unfollow(follower_id, following_id)

    async def list_followers(self, user_id: int, current_user_id: int, skip: int = 0, limit: int = 100):
        users = await self.repo.list_followers(user_id, skip=skip, limit=limit)
        following_ids = await self.repo.list_following_ids(current_user_id)
        for user in users:
            user.following = user.id in following_ids
        return users

    async def list_following(self, user_id: int, current_user_id: int, skip: int = 0, limit: int = 100):
        users = await self.repo.list_following(user_id, skip=skip, limit=limit)
        following_ids = await self.repo.list_following_ids(current_user_id)
        for user in users:
            user.following = user.id in following_ids
        return users

    async def attach_following_flag(self, user, current_user_id: int):
        user.following = await self.repo.is_following(current_user_id, user.id)
        return user

