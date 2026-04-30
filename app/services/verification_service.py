"""验证码业务服务（Verification Service）。

负责验证码的生成、Redis 缓存、防刷冷却和一次性校验。

安全设计要点：
1. 随机 TTL 偏置（防缓存雪崩）：基础 TTL + 随机 0~60 秒
2. 冷却期（防刷）：60 秒内同一邮箱不得重复请求
3. 冷却期也有少量随机偏置：防止同一批用户的冷却同时结束
4. 一次性使用：验证成功后立即删除，不能重复用同一验证码
5. 日志记录：每次生成和校验都打日志（含邮箱），但生产环境建议脱敏

Redis Key 结构：
- verify:code:{email} → 验证码字符串（用完即删）
- verify:cd:{email}   → "1"（冷却期标记）
"""

import random
import string

from loguru import logger
from redis.asyncio import Redis

from app.core.config import settings

# Redis Key 前缀常量
_CODE_PREFIX = "verify:code:"      # 验证码存储 key
_COOLDOWN_PREFIX = "verify:cd:"    # 冷却期标记 key


class VerificationService:
    """验证码服务——生成、发送、校验一次性验证码。

    依赖 Redis 作为存储后端，TTL 机制管理过期。
    冷却期通过 Redis EXISTS + TTL 实现，无需额外持久存储。"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.code_length = settings.verify_code_length        # 验证码位数（默认 6）
        self.expire_seconds = settings.verify_code_expire_seconds  # 过期时间（默认 300s）
        self.cooldown_seconds = 60  # 冷却期：同一邮箱 60 秒内不能重复请求

    def _generate_code(self) -> str:
        """生成纯数字验证码——如 '384729'。
        使用 random.choices 而非 random.randint 拼接，保证每一位都是均匀随机。
        k=self.code_length 配置控制位数（默认 6 位）。"""
        return "".join(random.choices(string.digits, k=self.code_length))

    async def send_code(self, email: str) -> str:
        """生成验证码并存入 Redis。

        返回生成的验证码字符串（调用方负责通过邮件发送）。

        防刷机制：
        - 检查冷却期标记 verify:cd:{email} 是否存在
        - 存在 → 抛 ValueError，提示等待剩余秒数
        - 不存在 → 生成验证码，设置冷却期

        TTL 随机偏置：
        - 验证码 TTL：基础值 + randint(0, 60) → 防止大量验证码同时过期
        - 冷却期 TTL：基础值 + randint(0, 5) → 防止冷却批量解除

        Raises:
            ValueError: 冷却期内重复请求
        """
        cd_key = f"{_COOLDOWN_PREFIX}{email}"

        # ---- 防刷：冷却期检查 ----
        if await self.redis.exists(cd_key):
            ttl = await self.redis.ttl(cd_key)  # 获取剩余冷却秒数
            raise ValueError(f"Please wait {ttl} seconds before requesting a new code")

        # ---- 生成验证码 ----
        code = self._generate_code()
        code_key = f"{_CODE_PREFIX}{email}"

        # 存储验证码：基础 TTL + 随机偏置 0-60 秒（防缓存雪崩）
        actual_ttl = self.expire_seconds + random.randint(0, 60)
        await self.redis.set(code_key, code, ex=actual_ttl)

        # 设置冷却期标记：60 秒 + 随机偏置 0-5 秒
        cd_ttl = self.cooldown_seconds + random.randint(0, 5)
        await self.redis.set(cd_key, "1", ex=cd_ttl)

        logger.info(f"[Verify] code generated for {email}: {code} (ttl={actual_ttl}s)")
        return code

    async def verify_code(self, email: str, code: str) -> bool:
        """校验验证码——一次性使用。

        校验成功后立即从 Redis 删除，防止重复使用同一验证码。
        失败时记录告警日志（保留验证码不删除，用户可重试）。

        返回：
        - True：验证成功（验证码已删除）
        - False：验证码不存在或错误
        """
        code_key = f"{_CODE_PREFIX}{email}"
        stored = await self.redis.get(code_key)

        # 验证码不存在（过期或被删除）
        if stored is None:
            logger.warning(f"[Verify] no code found for {email}")
            return False

        # 验证码不匹配（用户输入错误）
        if stored != code:
            logger.warning(f"[Verify] code mismatch for {email}")
            return False

        # 验证成功 → 删除验证码（一次性使用）
        await self.redis.delete(code_key)
        logger.info(f"[Verify] code verified for {email}")
        return True
