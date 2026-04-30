"""Redis 缓存演示接口。

提供管理员可用的缓存读写能力，用于验证 Redis 集成和调试缓存状态。"""

from fastapi import APIRouter

from app.api.dependencies.auth import AdminUser
from app.cache.redis import get_redis

router = APIRouter()


@router.get("/cache/{key}")
async def get_cache(key: str, admin: AdminUser):
    # 获取 Redis 连接（仅管理员可操作）
    redis = await get_redis()
    # 读取缓存值
    value = await redis.get(key)
    return {"key": key, "value": value}


@router.post("/cache/{key}")
async def set_cache(key: str, value: str, admin: AdminUser):
    # 获取 Redis 连接（仅管理员可操作）
    redis = await get_redis()
    # 设置缓存并设置过期时间（秒）
    await redis.set(key, value, ex=60)
    return {"key": key, "value": value, "ttl": 60}


