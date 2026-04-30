"""Redis 客户端工厂模块。

负责创建、复用和关闭 Redis 连接，并提供统一 get_redis 入口。"""

from typing import Optional

from redis.asyncio import Redis, ConnectionPool

from app.core.config import settings

# 全局 Redis 连接池（生产级配置：最大连接数 + 自动重试）
_pool: Optional[ConnectionPool] = None


async def get_redis() -> Redis:
    # 懒加载 Redis 连接池
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,     # 控制并发连接数，防止耗尽 Redis 资源
            retry_on_timeout=True,  # 开启重试机制（自动重连）
            health_check_interval=30 # 每 30s 检查一次连接健康状态
        )
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    # 关闭 Redis 连接池
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


