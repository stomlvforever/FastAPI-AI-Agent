"""用户资料业务服务。

复用用户仓储，只暴露资料读取和资料更新相关业务逻辑。"""

from app.repositories.user_repo import UserRepository
from app.schemas.profile import ProfileUpdate


class ProfileService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_profile(self, user_id: int):
        """获取用户个人资料。"""
        return await self.repo.get(user_id)

    async def update_profile(self, user_id: int, payload: ProfileUpdate):
        """更新个人资料（只更新提供的字段）。"""
        user = await self.repo.get(user_id)
        if not user:
            return None
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return user  # 没有要更新的字段
        return await self.repo.update(user, data)

