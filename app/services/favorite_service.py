"""收藏业务服务。

负责文章收藏、取消收藏和收藏状态判断。"""

from app.repositories.favorite_repo import FavoriteRepository


class FavoriteService:
    def __init__(self, repo: FavoriteRepository):
        self.repo = repo

    async def add_favorite(self, user_id: int, article_id: int):
        return await self.repo.add(user_id, article_id)

    async def remove_favorite(self, user_id: int, article_id: int):
        return await self.repo.remove(user_id, article_id)

