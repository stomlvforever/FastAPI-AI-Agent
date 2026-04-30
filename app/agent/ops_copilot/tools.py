"""Ops Copilot 的工具定义与执行模块。

职责：将后端业务能力包装为 OpenAI Function Calling 工具，并在执行前做权限校验。

架构设计：
- ToolParameter / ToolType / ToolDefinition：工具元数据的数据类
- ADMIN_ONLY_TOOLS：管理员专属工具的集合（普通用户不可见、不可用）
- ToolExecutor：工具执行器，持有所有 Repository 实例，提供 30+ 工具函数
- get_tools_schema()：生成 OpenAI Function Calling 所需的 tools JSON

权限模型：
- 管理员：所有工具可用（用户管理、系统监控、缓存操作、批量邮件等）
- 普通用户：只能使用查询和个人内容管理类工具
- 权限检查在 check_tool_permission() 中完成，失败抛 PermissionError
- 部分工具内部还有资源所有权检查（如 update_item 检查 owner_id）

设计要点：
- 工具名显式硬编码在 ADMIN_ONLY_TOOLS 集合中（白名单模式，比起黑名单更安全）
- 工具执行函数直接操作 Repository，不经过 Service 层（保持 Agent 工具的高性能和直接性）
- 敏感操作（封禁/删除/密码重置）自动通过 Celery 发送通知邮件
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepository
from app.repositories.article_repo import ArticleRepository
from app.repositories.comment_repo import CommentRepository
from app.repositories.item_repo import ItemRepository
from app.repositories.tag_repo import TagRepository
from app.repositories.follow_repo import FollowRepository
from app.repositories.favorite_repo import FavoriteRepository
from app.db.models.user import User
from app.services.article_service import ArticleService
from app.services.user_service import UserService
from app.services.task_dispatch_service import TaskDispatchService
from app.cache.redis import get_redis
from app.core.metrics import metrics
from app.core.config import settings


# ============================================================================
# 工具元数据数据类
# ============================================================================


@dataclass
class ToolParameter:
    """工具参数定义——描述一个 Function Calling 参数的元数据。

    字段：
    - name:        参数名（对应 OpenAI schema 中 properties 的 key）
    - type:        JSON Schema 类型（"string" | "integer" | "array" 等）
    - description: 参数描述（会直接显示在 OpenAI 的 tool description 中）
    - required:    是否必填
    - enum:        可选值枚举（如 role_filter 的 ["admin", "user", "all"]）
    - default:     默认值（OpenAI 可能使用此值减少用户输入）
    """
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[list] = None
    default: Any = None


class ToolType(str, Enum):
    """工具类型枚举——用于在 get_tools_schema 中标识工具性质。
    虽然当前 Schema 中未直接使用，但为未来扩展留空间（如按类型过滤/分组工具）。"""
    QUERY = "query"           # 仅查询，不修改数据（无副作用）
    OPERATION = "operation"   # 修改数据，可能需要用户确认
    ANALYSIS = "analysis"     # 数据分析/统计类


@dataclass
class ToolDefinition:
    """工具定义——将一个工具的元数据和执行函数绑定。

    字段：
    - name:        工具名（用于 OpenAI tool_calls 和 ToolExecutor 映射）
    - description: 工具描述（影响 LLM 选择工具的准确度）
    - tool_type:   工具类型枚举
    - parameters:  参数列表
    - handler:     实际执行函数（Callable）
    """
    name: str
    description: str
    tool_type: ToolType
    parameters: list[ToolParameter]
    handler: Callable  # 实际执行函数

    def to_openai_schema(self) -> dict:
        """将 ToolDefinition 转换为 OpenAI Function Calling Schema 格式。

        OpenAI 要求的格式：
        {
          "type": "function",
          "function": {
            "name": "...",
            "description": "...",
            "parameters": {
              "type": "object",
              "properties": { ... },
              "required": [ ... ]
            }
          }
        }

        注意：此方法在当前项目未使用，而是用 get_tools_schema() 直接构造 Schema。
        保留此方法是为了未来可能的动态工具注册/过滤需求。
        """
        schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [p.name for p in self.parameters if p.required],
                }
            }
        }

        # 为每个参数构建 properties（type + description + 可选 enum/default）
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            schema["function"]["parameters"]["properties"][param.name] = prop

        return schema


# ============================================================================
# 工具权限控制：管理员专属工具集合（白名单模式）
# ============================================================================

# 仅管理员可调用的工具集合
# 采用白名单模式——默认安全：任何不在集合中的工具普通用户均可使用
# 新增管理员工具时，必须在此集合中显式注册，否则普通用户也能调用
ADMIN_ONLY_TOOLS: set[str] = {
    # ---- 用户管理 ----
    "query_users",             # 查看所有用户列表
    "get_user_stats",          # 用户统计数据
    "create_user",             # 创建新用户
    "delete_user",             # 永久删除用户（不可逆）
    "ban_user",                # 封禁用户
    "unban_user",              # 解禁用户
    "reset_user_password",     # 重置用户密码
    "promote_user_to_admin",   # 提升为管理员
    "demote_user_from_admin",  # 降级为普通用户
    "admin_update_user",       # 修改任意用户资料
    # ---- 系统监控 ----
    "get_request_metrics",     # 请求指标/端点排行
    "get_system_health",       # 系统健康状态
    # ---- 内容管控 ----
    "delete_article",          # 删除任意文章
    "delete_comment",          # 删除任意评论
    "delete_tag",              # 删除标签
    # ---- 缓存操作 ----
    "get_cache_value",         # 读取 Redis 缓存值
    "set_cache_value",         # 写入 Redis 缓存值
    # ---- 邮件 ----
    "send_bulk_email",         # 批量发送邮件
}

# 普通用户可用的工具（以下不在 ADMIN_ONLY_TOOLS 中，供参考）：
#   query_articles, get_article_stats, create_article, update_own_article,
#   query_items, create_item, update_item, delete_item,
#   query_comments, create_comment,
#   get_tags, create_tag,
#   follow_user, unfollow_user, get_profile, update_own_profile,
#   favorite_article, unfavorite_article, get_feed,
#   get_task_status


# ============================================================================
# ToolExecutor：工具执行器——工具函数的核心实现类
# ============================================================================


class ToolExecutor:
    """工具执行器——封装了所有 Agent 工具的调用逻辑和权限校验。

    每个会话创建一个 ToolExecutor 实例（在 OpsCopilotService.__init__ 中），
    持有当前用户的数据库会话和所有 Repository 实例。

    工具函数分为三类：
    - Query Tools：查询类（query_users, get_user_stats, get_system_health 等）
    - Operation Tools：操作类（ban_user, reset_password, create_article 等）
    - 辅助 Tools：缓存/任务/社交功能等
    """

    def __init__(self, session: AsyncSession, current_user: User):
        self.session = session
        self.current_user = current_user

        # 初始化所有 Repository 实例（每个工具函数按需使用）
        self.user_repo = UserRepository(session)
        self.article_repo = ArticleRepository(session)
        self.comment_repo = CommentRepository(session)
        self.item_repo = ItemRepository(session)
        self.tag_repo = TagRepository(session)
        self.follow_repo = FollowRepository(session)
        self.favorite_repo = FavoriteRepository(session)

    def check_tool_permission(self, tool_name: str) -> None:
        """检查当前用户是否有权调用指定工具。
        如果工具在 ADMIN_ONLY_TOOLS 中而当前用户不是 admin，抛出 PermissionError。
        此方法在 service.py 的 _execute_tool 中先于工具执行调用。"""
        if tool_name in ADMIN_ONLY_TOOLS and self.current_user.role != "admin":
            raise PermissionError(
                f"工具 {tool_name} 仅限管理员使用，当前用户角色为 {self.current_user.role}"
            )

    # ========================================================================
    # 查询类工具（Query Tools）
    # ========================================================================
    # 特点：无数据修改，纯读取操作。即使管理员调用也不会产生副作用。

    async def query_users(
        self,
        skip: int = 0,
        limit: int = 20,
        role_filter: str = "all",
        status_filter: str = "all"
    ) -> dict:
        """查询用户列表——管理员工具。
        支持按角色（admin/user/all）和状态（active/banned/all）过滤。
        注意：目前的过滤是 Python 内存过滤，大数据量下应改为 SQL WHERE 过滤。"""
        # 从数据库获取用户列表（基础分页）
        users = await self.user_repo.list(skip=skip, limit=limit)

        # Python 侧过滤——简单但非最优，生产环境应推送到 SQL
        if role_filter != "all":
            users = [u for u in users if u.role == role_filter]

        if status_filter == "active":
            users = [u for u in users if u.is_active]
        elif status_filter == "banned":
            users = [u for u in users if not u.is_active]

        return {
            "total": len(users),
            "skip": skip,
            "limit": limit,
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
        }

    async def query_articles(
        self,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[int] = None,
        tag: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc"
    ) -> dict:
        """查询文章列表——所有用户可用。
        支持按作者、标签过滤和排序。
        current_user_favorited 字段表示当前登录用户是否已收藏该文章，
        这个信息通过 article_repo.list 内部的子查询获取，避免了 N+1 问题。"""
        articles = await self.article_repo.list(
            user_id=self.current_user.id,  # 用于收藏标记的子查询（不是过滤条件）
            skip=skip,
            limit=limit,
            tag=tag,
            author_id=author_id,
            sort_by=sort_by,
            order=order,
        )

        return {
            "total": len(articles),
            "skip": skip,
            "limit": limit,
            "current_user_id": self.current_user.id,
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "slug": a.slug,
                    "author_id": a.author_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    # favorites_count 等计数字段来自 Article 物化列，favorited 来自收藏状态子查询
                    "favorites_count": a.favorites_count if hasattr(a, "favorites_count") else 0,
                    "comments_count": a.comments_count if hasattr(a, "comments_count") else 0,
                    "references_count": a.references_count if hasattr(a, "references_count") else 0,
                    "views_count": a.views_count if hasattr(a, "views_count") else 0,
                    "current_user_favorited": bool(a.favorited) if hasattr(a, "favorited") else False,
                }
                for a in articles
            ]
        }

    async def get_user_stats(self, days: int = 7) -> dict:
        """获取用户统计数据——管理员工具。
        统计总用户数、活跃/禁用/管理员数、最近 N 天新增。
        注意：当前用 Python 内存聚合（加载全部用户），生产环境应改为 SQL COUNT + GROUP BY。"""
        # 取全部用户用于统计（limit=10000 是安全上限，实际应改为 SQL 聚合）
        all_users = await self.user_repo.list(skip=0, limit=10000)

        # 内存统计
        total_users = len(all_users)
        active_users = sum(1 for u in all_users if u.is_active)
        banned_users = sum(1 for u in all_users if not u.is_active)
        admin_users = sum(1 for u in all_users if u.role == "admin")

        # 计算最近 N 天的新增用户
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        new_users_recent = sum(
            1 for u in all_users
            if u.created_at and u.created_at >= cutoff_date
        )

        return {
            "total_users": total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "admin_users": admin_users,
            "new_users_last_n_days": new_users_recent,
            "days": days,
        }

    async def get_article_stats(self, days: int = 7, top_n: int = 10) -> dict:
        """获取文章统计数据——管理员工具。
        统计总文章数、最近 N 天新增、热门文章 Top N（按收藏数排序）。"""
        all_articles = await self.article_repo.list(
            user_id=self.current_user.id, skip=0, limit=10000
        )

        # 最近 N 天的文章
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        recent_articles = [
            a for a in all_articles
            if a.created_at and a.created_at >= cutoff_date
        ]

        # 热门文章 Top N（按收藏数降序）
        top_articles = sorted(
            all_articles,
            key=lambda a: getattr(a, "favorites_count", 0),
            reverse=True
        )[:top_n]

        return {
            "total_articles": len(all_articles),
            "new_articles_last_n_days": len(recent_articles),
            "days": days,
            "top_articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "slug": a.slug,
                    "author_id": a.author_id,
                    "favorites_count": getattr(a, "favorites_count", 0),
                }
                for a in top_articles
            ]
        }

    async def get_system_health(self) -> dict:
        """获取系统健康状态——管理员工具。
        从内存指标收集器（MetricsCollector）读取实时状态。
        错误率 < 5% 判定为 healthy，否则 warning。"""
        metrics_data = metrics.get_metrics()

        return {
            "status": "healthy" if metrics_data.get("error_rate", 0) < 5 else "warning",
            "uptime_seconds": metrics_data.get("uptime_seconds", 0),
            "total_requests": metrics_data.get("total_requests", 0),
            "total_errors": metrics_data.get("total_errors", 0),
            "error_rate_percent": metrics_data.get("error_rate", 0),
        }

    async def get_request_metrics(self, top_n: int = 10) -> dict:
        """获取请求指标——管理员工具。
        返回热门端点和最慢端点的 Top N 排行。
        数据来自内存指标收集器，重启丢失。"""
        metrics_data = metrics.get_metrics()

        return {
            "uptime_seconds": metrics_data.get("uptime_seconds", 0),
            "top_endpoints": metrics_data.get("top_endpoints", [])[:top_n],
            "slowest_endpoints": metrics_data.get("slowest_endpoints", [])[:top_n],
            "error_rate_percent": metrics_data.get("error_rate", 0),
        }

    # ========================================================================
    # 操作类工具（Operation Tools）—— 修改数据、需要确认
    # ========================================================================
    # 特点：有数据写入/修改副作用，管理员操作后自动发送通知邮件。

    async def ban_user(self, user_id: int, reason: str) -> dict:
        """封禁用户——管理员工具（危险操作，需确认）。

        执行步骤：
        1. 根据 user_id 查找用户
        2. 防止自己封禁自己
        3. 设置 is_active = False
        4. 提交事务
        5. 通过 Celery 异步发送通知邮件给被封禁用户
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 不允许封禁自己
        if user.id == self.current_user.id:
            raise HTTPException(
                status_code=400,
                detail="Cannot ban yourself"
            )

        # 更新状态并提交
        updated = await self.user_repo.update(user, {"is_active": False})
        await self.session.commit()

        # 异步发送通知邮件（不阻塞 Agent 回复）
        TaskDispatchService().queue_notification_email_safe(
            user.email,
            "Your account has been suspended",
            f"Your account has been suspended due to: {reason}"
        )

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "action": "banned",
            "reason": reason,
        }

    async def unban_user(self, user_id: int) -> dict:
        """解禁用户——管理员工具。
        恢复 is_active = True，发送恢复通知邮件。"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        updated = await self.user_repo.update(user, {"is_active": True})
        await self.session.commit()

        TaskDispatchService().queue_notification_email_safe(
            user.email,
            "Your account has been restored",
            "Your account has been restored and you can now login normally."
        )

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "action": "unbanned",
        }

    async def reset_user_password(
        self,
        user_id: int,
        temporary_password: Optional[str] = None
    ) -> dict:
        """重置用户密码——管理员工具（危险操作，需确认）。

        安全机制：
        - 如果不提供临时密码，用 secrets.token_urlsafe 生成随机密码
        - bcrypt 哈希后存入数据库
        - 临时密码明文通过邮件发送给用户（邮件中提示立即修改）

        注意：temporary_password 在 API 响应中也会暴露一次（仅响应中可见），
        邮件是第二个信道，降低泄露风险。
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        from app.core.security import get_password_hash
        from secrets import token_urlsafe

        # 生成随机临时密码（12 字节 → 16 字符 base64）
        if not temporary_password:
            temporary_password = token_urlsafe(12)[:16]

        hashed = get_password_hash(temporary_password)
        await self.user_repo.update(user, {"hashed_password": hashed})
        await self.session.commit()

        TaskDispatchService().queue_notification_email_safe(
            user.email,
            "Your password has been reset",
            f"Your password has been reset to: {temporary_password}\nPlease login and change it immediately."
        )

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "action": "password_reset",
            "temporary_password": temporary_password,  # 仅在响应中显示一次
        }

    async def promote_user_to_admin(self, user_id: int) -> dict:
        """提升用户为管理员——管理员工具（危险操作，需确认）。
        修改 user.role = 'admin'，发送通知邮件。"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await self.user_repo.update(user, {"role": "admin"})
        await self.session.commit()

        TaskDispatchService().queue_notification_email_safe(
            user.email,
            "You have been promoted to Admin",
            "Congratulations! You are now an administrator of the system."
        )

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "action": "promoted",
            "new_role": "admin",
        }

    async def delete_article(self, article_slug: str, reason: str) -> dict:
        """删除文章——管理员工具（不可逆操作，需确认）。
        通过 slug 定位文章，删除后通知文章作者。"""
        article = await self.article_repo.get_by_slug(article_slug)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # 在删除前获取作者邮箱（用于通知）
        author_email = article.author.email if hasattr(article, "author") else None

        deleted = await self.article_repo.delete(article.id)
        await self.session.commit()

        if author_email:
            TaskDispatchService().queue_notification_email_safe(
                author_email,
                "Your article has been deleted by admin",
                f"Your article '{article.title}' has been deleted due to: {reason}"
            )

        return {
            "success": True,
            "article_id": article.id,
            "article_slug": article_slug,
            "action": "deleted",
            "reason": reason,
        }

    async def send_bulk_email(
        self,
        user_ids: list[int],
        subject: str,
        content: str
    ) -> dict:
        """批量发送邮件——管理员工具。
        遍历用户 ID 列表，每个用户创建一个 Celery 异步邮件任务。
        返回所有任务 ID 列表，可通过 get_task_status 查询发送状态。"""
        # 按用户 ID 逐个获取用户对象（实际可优化为 IN 查询）
        users = [
            await self.user_repo.get_by_id(uid)
            for uid in user_ids
        ]
        users = [u for u in users if u is not None]  # 过滤不存在的用户

        # 为每个用户创建异步邮件任务
        task_ids = []
        for user in users:
            task_id = TaskDispatchService().queue_notification_email(
                user.email,
                subject,
                content
            )
            task_ids.append(task_id)

        return {
            "success": True,
            "recipients_count": len(users),
            "task_ids": task_ids,
            "action": "bulk_email_queued",
        }

    async def create_user(
        self, email: str, password: str, full_name: str = "", role: str = "user"
    ) -> dict:
        """创建新用户——管理员工具。
        步骤：
        1. 检查邮箱是否已被注册
        2. bcrypt 哈希密码
        3. 创建用户 → 如果指定 admin 则更新角色 → 提交事务
        """
        from app.core.security import get_password_hash

        # 邮箱唯一性检查
        existing = await self.user_repo.get_by_email(email)
        if existing:
            return {"success": False, "error": f"邮箱 {email} 已被注册"}

        hashed_password = get_password_hash(password)
        user = await self.user_repo.create(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name or None,
        )

        # 如果指定为 admin，二次更新 role（create 默认 user）
        if role == "admin":
            await self.user_repo.update(user, {"role": "admin"})

        await self.session.commit()

        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": role,
            "action": "created",
        }

    async def delete_user(self, user_id: int, reason: str = "") -> dict:
        """永久删除用户及其所有数据——管理员工具（不可逆操作，需确认）。

        限制：
        - 不能删除自己
        - 删除会级联清除用户的 Items、Articles、Comments 等（取决于 ORM 的 cascade 设置）
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}

        if user.id == self.current_user.id:
            return {"success": False, "error": "不能删除自己"}

        email = user.email
        # ORM 的 Session.delete 会标记删除（级联取决于 relation 的 cascade 配置）
        await self.session.delete(user)
        await self.session.commit()

        return {
            "success": True,
            "user_id": user_id,
            "email": email,
            "action": "permanently_deleted",
            "reason": reason,
        }

    async def delete_comment(self, comment_id: int, reason: str = "") -> dict:
        """删除评论——管理员工具。
        用于清理违规评论。通过 comment_id 精确定位。"""
        comment = await self.comment_repo.get_by_id(comment_id)
        if not comment:
            return {"success": False, "error": f"评论 ID {comment_id} 不存在"}

        await self.comment_repo.delete(comment)
        await self.session.commit()

        return {
            "success": True,
            "comment_id": comment_id,
            "action": "comment_deleted",
            "reason": reason,
        }

    # ========================================================================
    # Items 工具（CRUD）
    # ========================================================================

    async def query_items(
        self,
        skip: int = 0,
        limit: int = 20,
        owner_id: Optional[int] = None,
        status_filter: str = "all",
        priority_filter: Optional[int] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> dict:
        """查询 Items 列表——所有权隔离。

        权限模型：
        - 普通用户：只能查询自己的 Items（忽略 owner_id 参数）
        - 管理员：可通过 owner_id 查询任意用户的 Items

        支持按状态、优先级过滤和多种排序方式。
        """
        # owner_id 取值逻辑：管理员且指定了 owner_id → 用指定值，否则用当前用户 ID
        uid = owner_id if (self.current_user.role == "admin" and owner_id) else self.current_user.id
        items = await self.item_repo.list(
            owner_id=uid, skip=skip, limit=limit,
            status=status_filter if status_filter != "all" else None,
            priority=priority_filter,
            sort_by=sort_by, order=order,
        )
        return {
            "total": len(items), "skip": skip, "limit": limit,
            "items": [
                {
                    "id": i.id, "title": i.title, "description": i.description,
                    "priority": i.priority, "status": i.status,
                    "owner_id": i.owner_id,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in items
            ],
        }

    async def create_item(self, title: str, description: str = "", priority: int = 3) -> dict:
        """创建 Item——自动归属当前用户。
        priority 默认为 3（中等优先级，范围 1-5）。"""
        item = await self.item_repo.create(
            title=title, description=description or None,
            priority=priority, owner_id=self.current_user.id,
        )
        await self.session.commit()
        return {
            "success": True, "item_id": item.id, "title": item.title,
            "priority": item.priority, "action": "created",
        }

    async def update_item(self, item_id: int, title: Optional[str] = None,
                          description: Optional[str] = None, priority: Optional[int] = None,
                          status: Optional[str] = None) -> dict:
        """更新 Item——所有权检查。

        权限模型：
        - 普通用户：只能更新自己的 Items
        - 管理员：可以更新任何人的 Items

        只更新显式提供值的字段（未提供的不修改）。
        """
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            return {"success": False, "error": "物品不存在"}
        # 所有权校验（管理员跳过）
        if self.current_user.role != "admin" and item.owner_id != self.current_user.id:
            return {"success": False, "error": "无权修改他人物品"}
        # 构建仅含非空字段的更新字典
        data: dict = {}
        if title is not None: data["title"] = title
        if description is not None: data["description"] = description
        if priority is not None: data["priority"] = priority
        if status is not None: data["status"] = status
        if not data:
            return {"success": False, "error": "未提供任何要更新的字段"}
        await self.item_repo.update(item, data)
        await self.session.commit()
        return {"success": True, "item_id": item.id, "action": "updated", "updated_fields": list(data.keys())}

    async def delete_item(self, item_id: int) -> dict:
        """删除 Item——所有权检查。
        普通用户只能删自己的，管理员可删所有。"""
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            return {"success": False, "error": "物品不存在"}
        if self.current_user.role != "admin" and item.owner_id != self.current_user.id:
            return {"success": False, "error": "无权删除他人物品"}
        await self.item_repo.delete(item)
        await self.session.commit()
        return {"success": True, "item_id": item_id, "action": "deleted"}

    # ========================================================================
    # 评论工具
    # ========================================================================

    async def query_comments(self, item_id: int) -> dict:
        """查询某个 Item 下的所有评论列表——所有登录用户可用。
        按创建时间排序（Repository 层控制）。"""
        comments = await self.comment_repo.list_by_item(item_id)
        return {
            "item_id": item_id,
            "total": len(comments),
            "comments": [
                {
                    "id": c.id, "body": c.body, "author_id": c.author_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comments
            ],
        }

    async def create_comment(self, item_id: int, body: str) -> dict:
        """给 Item 添加评论——自动归属当前用户。"""
        comment = await self.comment_repo.create(
            body=body, item_id=item_id, author_id=self.current_user.id,
        )
        await self.session.commit()
        return {
            "success": True, "comment_id": comment.id,
            "item_id": item_id, "action": "comment_created",
        }

    # ========================================================================
    # 文章创建 + 更新
    # ========================================================================

    async def create_article(self, title: str, body: str, description: str = "", tags: Optional[list[str]] = None) -> dict:
        """创建文章——自动归属当前用户。

        关键功能：
        - Slug 自动生成（用 python-slugify）
        - Slug 冲突处理：如果标题 slug 已被占用，追加时间戳
        - 标签自动创建：如果标签不存在则自动创建（保证 idempotent）
        """
        from slugify import slugify

        # 生成 URL 友好的 slug
        slug = slugify(title, max_length=200)
        # 防止 slug 冲突（追加 Unix 时间戳确保唯一性）
        existing = await self.article_repo.get_by_slug(slug)
        if existing:
            import time
            slug = f"{slug}-{int(time.time())}"

        article = await self.article_repo.create(
            title=title, slug=slug, body=body,
            description=description or None,
            author_id=self.current_user.id,
        )

        # 处理标签：不存在的自动创建
        if tags:
            tag_objs = []
            for tag_name in tags:
                t = await self.tag_repo.get_by_name(tag_name)
                if not t:
                    t = await self.tag_repo.create(name=tag_name)
                tag_objs.append(t)
            # 通过关联表设置多对多关系
            await self.article_repo.set_tags(article, tag_objs)

        await self.session.commit()
        return {
            "success": True, "article_id": article.id,
            "slug": article.slug, "title": article.title,
            "action": "created",
        }

    async def update_own_article(self, article_slug: str, title: Optional[str] = None,
                                  body: Optional[str] = None, description: Optional[str] = None) -> dict:
        """更新文章——所有权检查。
        普通用户只能改自己的，管理员可改所有。
        通过 slug 而非 id 定位文章（SEO 友好）。"""
        article = await self.article_repo.get_by_slug(article_slug)
        if not article:
            return {"success": False, "error": "文章不存在"}
        # 所有权校验
        if self.current_user.role != "admin" and article.author_id != self.current_user.id:
            return {"success": False, "error": "无权修改他人文章"}
        data: dict = {}
        if title is not None: data["title"] = title
        if body is not None: data["body"] = body
        if description is not None: data["description"] = description
        if not data:
            return {"success": False, "error": "未提供任何要更新的字段"}
        await self.article_repo.update(article, data)
        await self.session.commit()
        return {"success": True, "slug": article.slug, "action": "updated", "updated_fields": list(data.keys())}

    # ========================================================================
    # 标签工具
    # ========================================================================

    async def get_tags(self) -> dict:
        """获取所有标签列表——公开信息。"""
        tags = await self.tag_repo.list_all()
        return {
            "total": len(tags),
            "tags": [{"id": t.id, "name": t.name} for t in tags],
        }

    async def create_tag(self, name: str) -> dict:
        """创建新标签——所有登录用户可用。
        标签名唯一性检查：重复创建返回错误。
        标签用于 Items 和 Articles 的分类/过滤。"""
        existing = await self.tag_repo.get_by_name(name)
        if existing:
            return {"success": False, "error": f"标签 '{name}' 已存在"}
        tag = await self.tag_repo.create(name=name)
        await self.session.commit()
        return {"success": True, "tag_id": tag.id, "name": tag.name, "action": "created"}

    async def delete_tag(self, tag_id: int) -> dict:
        """删除标签——管理员工具。
        删除标签不会自动清理关联表中的记录（由数据库 CASCADE 处理）。"""
        tag = await self.tag_repo.get_by_id(tag_id)
        if not tag:
            return {"success": False, "error": "标签不存在"}
        await self.tag_repo.delete(tag)
        await self.session.commit()
        return {"success": True, "tag_id": tag_id, "name": tag.name, "action": "deleted"}

    # ========================================================================
    # 社交功能工具
    # ========================================================================

    async def follow_user(self, target_user_id: int) -> dict:
        """关注用户——所有登录用户可用。
        规则：不能关注自己，被关注用户必须存在。"""
        if target_user_id == self.current_user.id:
            return {"success": False, "error": "不能关注自己"}
        target = await self.user_repo.get_by_id(target_user_id)
        if not target:
            return {"success": False, "error": "用户不存在"}
        await self.follow_repo.follow(follower_id=self.current_user.id, following_id=target_user_id)
        await self.session.commit()
        return {"success": True, "action": "followed", "target_user_id": target_user_id, "target_email": target.email}

    async def unfollow_user(self, target_user_id: int) -> dict:
        """取消关注用户。幂等操作——即使未关注也不会报错。"""
        await self.follow_repo.unfollow(follower_id=self.current_user.id, following_id=target_user_id)
        await self.session.commit()
        return {"success": True, "action": "unfollowed", "target_user_id": target_user_id}

    async def favorite_article(self, article_slug: str) -> dict:
        """收藏文章——只能代表当前用户操作，无法代替其他用户。

        幂等设计：如果已收藏则返回 "already_favorited"；
        如果首次收藏返回 "favorited"。
        user_id 固定使用 current_user.id，确保安全。"""
        article = await self.article_repo.get_by_slug(article_slug)
        if not article:
            return {"success": False, "error": "文章不存在"}
        # add 方法返回 (favorite_obj, created: bool)
        _, created = await self.favorite_repo.add(user_id=self.current_user.id, article_id=article.id)
        await self.session.commit()
        if created:
            return {"success": True, "action": "favorited", "article_slug": article_slug, "user_id": self.current_user.id}
        else:
            return {"success": True, "action": "already_favorited", "article_slug": article_slug, "user_id": self.current_user.id, "message": "当前用户已经收藏过此文章"}

    async def unfavorite_article(self, article_slug: str) -> dict:
        """取消收藏文章。幂等操作。"""
        article = await self.article_repo.get_by_slug(article_slug)
        if not article:
            return {"success": False, "error": "文章不存在"}
        await self.favorite_repo.remove(user_id=self.current_user.id, article_id=article.id)
        await self.session.commit()
        return {"success": True, "action": "unfavorited", "article_slug": article_slug}

    async def get_profile(self, user_id: int) -> dict:
        """查看用户公开资料——所有登录用户可用。
        包含 is_following 状态（当前用户是否已关注该用户）。"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        # 查询当前用户是否已关注此用户
        is_following = await self.follow_repo.is_following(
            follower_id=self.current_user.id, following_id=user_id
        )
        return {
            "user_id": user.id, "email": user.email,
            "full_name": user.full_name, "bio": user.bio, "image": user.image,
            "role": user.role, "is_following": is_following,
        }

    async def update_own_profile(self, full_name: Optional[str] = None,
                                  bio: Optional[str] = None, image: Optional[str] = None) -> dict:
        """更新当前用户的个人资料。
        只更新显式提供值的字段。"""
        data: dict = {}
        if full_name is not None: data["full_name"] = full_name
        if bio is not None: data["bio"] = bio
        if image is not None: data["image"] = image
        if not data:
            return {"success": False, "error": "未提供任何要更新的字段"}
        await self.user_repo.update(self.current_user, data)
        await self.session.commit()
        return {"success": True, "action": "profile_updated", "updated_fields": list(data.keys())}

    async def get_feed(self, skip: int = 0, limit: int = 20) -> dict:
        """获取关注用户的文章 Feed——所有登录用户可用。
        Feed 内容是当前用户关注的人发表的文章列表。
        底层通过 article_repo.list_feed 实现 JOIN + 排序。"""
        articles = await self.article_repo.list_feed(
            user_id=self.current_user.id, skip=skip, limit=limit,
        )
        return {
            "total": len(articles), "skip": skip, "limit": limit,
            "articles": [
                {
                    "id": a.id, "title": a.title, "slug": a.slug,
                    "author_id": a.author_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "favorites_count": getattr(a, "favorites_count", 0),
                    "comments_count": getattr(a, "comments_count", 0),
                    "references_count": getattr(a, "references_count", 0),
                    "views_count": getattr(a, "views_count", 0),
                    "current_user_favorited": bool(getattr(a, "favorited", False)),
                }
                for a in articles
            ],
        }

    # ========================================================================
    # 缓存 + 任务 + 管理员降级
    # ========================================================================

    async def get_cache_value(self, key: str) -> dict:
        """读取 Redis 缓存值——管理员工具。
        直接操作 Redis 连接，返回 key 对应的值。"""
        redis = await get_redis()
        value = await redis.get(key)
        return {"key": key, "value": value.decode() if isinstance(value, bytes) else value}

    async def set_cache_value(self, key: str, value: str, ttl: int = 60) -> dict:
        """写入 Redis 缓存值——管理员工具。
        默认 TTL 60 秒，可自定义过期时间。"""
        redis = await get_redis()
        await redis.set(key, value, ex=ttl)
        return {"success": True, "key": key, "ttl": ttl, "action": "cache_set"}

    async def get_task_status(self, task_id: str) -> dict:
        """查询 Celery 异步任务的执行状态。
        可用于追踪邮件发送等异步操作——输入 task_id（在 send_bulk_email 返回中获取）。"""
        result = TaskDispatchService().get_task_status(task_id)
        return {"task_id": task_id, "status": result}

    async def demote_user_from_admin(self, user_id: int) -> dict:
        """将管理员降级为普通用户——管理员工具。

        安全限制：
        - 不能降级自己
        - 如果目标用户已经是普通用户，返回错误提示
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        if user.id == self.current_user.id:
            return {"success": False, "error": "不能降级自己"}
        if user.role != "admin":
            return {"success": False, "error": "该用户已经是普通用户"}
        await self.user_repo.update(user, {"role": "user"})
        await self.session.commit()
        return {"success": True, "user_id": user.id, "email": user.email, "action": "demoted", "new_role": "user"}

    async def admin_update_user(
        self, user_id: int,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        bio: Optional[str] = None,
        image: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict:
        """管理员修改任意用户的资料——管理员工具。

        安全机制：
        - 修改邮箱时检查新邮箱是否已被其他用户占用（唯一性检查）
        - 修改角色时校验 role 值只能为 "user" 或 "admin"
        - 只更新显式提供值的字段
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        data: dict = {}
        if full_name is not None:
            data["full_name"] = full_name
        if email is not None:
            # 邮箱唯一性检查：新邮箱不能已被其他用户使用
            existing = await self.user_repo.get_by_email(email)
            if existing and existing.id != user_id:
                return {"success": False, "error": f"邮箱 {email} 已被其他用户使用"}
            data["email"] = email
        if bio is not None:
            data["bio"] = bio
        if image is not None:
            data["image"] = image
        if role is not None:
            # 角色值校验
            if role not in ("user", "admin"):
                return {"success": False, "error": "角色只能是 user 或 admin"}
            data["role"] = role
        if not data:
            return {"success": False, "error": "未提供任何要更新的字段"}
        await self.user_repo.update(user, data)
        await self.session.commit()
        return {
            "success": True, "user_id": user.id,
            "email": user.email, "full_name": user.full_name,
            "action": "admin_updated", "updated_fields": list(data.keys()),
        }


# ============================================================================
# get_tools_schema：生成 OpenAI Function Calling 工具 Schema
# ============================================================================


def get_tools_schema() -> list[dict]:
    """获取所有工具的 OpenAI Function Calling Schema。

    返回的列表直接作为 chat.completions.create(tools=...) 的参数。
    注意：当前 Schema 不根据用户角色裁剪——裁剪由 ToolExecutor.check_tool_permission
    在运行时完成。这意味着 LLM 可能选择它没有权限的工具，然后被拒绝。

    方案说明：
    如果改为在 Schema 层面按角色过滤，可以减少无效工具调用但会增加内存开销。
    当前方案是运行时拒绝，简单且可调试。

    Schema 分为以下模块（按功能分类，便于维护）：
    1. 用户管理工具（query_users ~ admin_update_user）
    2. Items 工具（query_items ~ delete_item）
    3. 评论工具（query_comments, create_comment）
    4. 文章创建 + 更新（create_article, update_own_article）
    5. 标签工具（get_tags ~ delete_tag）
    6. 社交功能工具（follow_user ~ get_feed）
    7. 缓存 + 任务 + 降级（get_cache_value ~ demote_user_from_admin）
    """
    return [
        # ==================== 用户管理工具 ====================
        {
            "type": "function",
            "function": {
                "name": "query_users",
                "description": "查询用户列表，可按角色和状态过滤",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skip": {"type": "integer", "description": "分页起始，默认 0"},
                        "limit": {"type": "integer", "description": "分页数量，默认 20"},
                        "role_filter": {
                            "type": "string",
                            "enum": ["admin", "user", "all"],
                            "description": "按角色过滤，默认 all"
                        },
                        "status_filter": {
                            "type": "string",
                            "enum": ["active", "banned", "all"],
                            "description": "按状态过滤，默认 all"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_articles",
                "description": "查询文章列表，可按作者、标签过滤，支持排序。返回结果中 current_user_favorited 表示当前登录用户（即你）是否已收藏该文章，favorites_count 是总收藏数。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skip": {"type": "integer", "description": "分页起始，默认 0"},
                        "limit": {"type": "integer", "description": "分页数量，默认 20"},
                        "author_id": {"type": "integer", "description": "按作者 ID 过滤"},
                        "tag": {"type": "string", "description": "按标签名过滤"},
                        "sort_by": {
                            "type": "string",
                            "enum": ["created_at", "updated_at", "title", "favorites_count", "comments_count", "references_count", "views_count"],
                            "description": "排序字段，默认 created_at"
                        },
                        "order": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "排序顺序，默认 desc"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_user_stats",
                "description": "获取用户统计数据：总用户数、活跃用户、被禁用户、管理员数、最近N天新增用户数",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "统计最近 N 天的数据，默认 7"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_article_stats",
                "description": "获取文章统计数据：总文章数、最近N天新增、热门文章 Top N",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "统计最近 N 天的数据，默认 7"},
                        "top_n": {"type": "integer", "description": "返回热门文章数量，默认 10"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_system_health",
                "description": "获取系统健康状态：运行时长、总请求数、总错误数、错误率",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_request_metrics",
                "description": "获取请求指标：最热门端点 Top N、最慢端点 Top N、错误率",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "top_n": {"type": "integer", "description": "返回 Top N 端点，默认 10"}
                    }
                }
            }
        },
        # 用户状态管理
        {
            "type": "function",
            "function": {
                "name": "ban_user",
                "description": "禁用用户账户，用户将无法登录。会自动发送通知邮件。这是危险操作，执行前必须与管理员确认。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "要禁用的用户 ID"},
                        "reason": {"type": "string", "description": "禁用原因（会出现在通知邮件中）"}
                    },
                    "required": ["user_id", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "unban_user",
                "description": "解禁用户账户，恢复用户登录权限。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "要解禁的用户 ID"}
                    },
                    "required": ["user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "reset_user_password",
                "description": "重置用户密码并通知用户。如不指定临时密码则自动生成。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "用户 ID"},
                        "temporary_password": {"type": "string", "description": "临时密码（可选，不传则自动生成）"}
                    },
                    "required": ["user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "promote_user_to_admin",
                "description": "将普通用户提升为管理员角色。这是危险操作，需确认。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "要提升的用户 ID"}
                    },
                    "required": ["user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "admin_update_user",
                "description": "管理员修改任意用户的资料，包括姓名、邮箱、简介、头像、角色。修改后全局立即生效。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "目标用户 ID"},
                        "full_name": {"type": "string", "description": "新的全名"},
                        "email": {"type": "string", "description": "新的邮箱"},
                        "bio": {"type": "string", "description": "新的个人简介"},
                        "image": {"type": "string", "description": "新的头像 URL"},
                        "role": {
                            "type": "string",
                            "enum": ["user", "admin"],
                            "description": "新的角色"
                        }
                    },
                    "required": ["user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_article",
                "description": "永久删除一篇文章。会通知文章作者。这是不可逆操作，需确认。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "article_slug": {"type": "string", "description": "文章的 slug 标识"},
                        "reason": {"type": "string", "description": "删除原因"}
                    },
                    "required": ["article_slug", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_bulk_email",
                "description": "向多个用户发送邮件（通过 Celery 异步任务队列）。返回任务 ID 列表，可后续查询发送状态。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "接收邮件的用户 ID 列表"
                        },
                        "subject": {"type": "string", "description": "邮件主题"},
                        "content": {"type": "string", "description": "邮件正文"}
                    },
                    "required": ["user_ids", "subject", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_user",
                "description": "创建新用户。需提供邮箱和密码，可选全名和角色。创建管理员用户需谨慎。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "用户邮箱"},
                        "password": {"type": "string", "description": "用户密码"},
                        "full_name": {"type": "string", "description": "用户全名（可选）"},
                        "role": {
                            "type": "string",
                            "enum": ["user", "admin"],
                            "description": "用户角色，默认 user"
                        }
                    },
                    "required": ["email", "password"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_user",
                "description": "永久删除用户账户及其所有数据。这是不可逆操作，执行前必须确认。不能删除自己。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "要删除的用户 ID"},
                        "reason": {"type": "string", "description": "删除原因"}
                    },
                    "required": ["user_id", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_comment",
                "description": "删除指定 ID 的评论。用于清理违规评论。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "comment_id": {"type": "integer", "description": "要删除的评论 ID"},
                        "reason": {"type": "string", "description": "删除原因"}
                    },
                    "required": ["comment_id"]
                }
            }
        },
        # ==================== Items 工具 ====================
        {
            "type": "function",
            "function": {
                "name": "query_items",
                "description": "查询物品列表。普通用户只能查自己的，管理员可通过 owner_id 查任何人的。支持按状态、优先级过滤和排序。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skip": {"type": "integer", "description": "分页起始，默认 0"},
                        "limit": {"type": "integer", "description": "分页数量，默认 20"},
                        "owner_id": {"type": "integer", "description": "按拥有者 ID 过滤（仅管理员可用）"},
                        "status_filter": {
                            "type": "string",
                            "enum": ["active", "inactive", "all"],
                            "description": "按状态过滤，默认 all"
                        },
                        "priority_filter": {"type": "integer", "description": "按优先级过滤（1-5）"},
                        "sort_by": {
                            "type": "string",
                            "enum": ["created_at", "priority", "title"],
                            "description": "排序字段，默认 created_at"
                        },
                        "order": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "排序顺序，默认 desc"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_item",
                "description": "创建新物品，自动归属当前用户。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "物品标题"},
                        "description": {"type": "string", "description": "物品描述（可选）"},
                        "priority": {"type": "integer", "description": "优先级 1-5，默认 3"}
                    },
                    "required": ["title"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_item",
                "description": "更新物品信息。普通用户只能改自己的，管理员可改所有。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "物品 ID"},
                        "title": {"type": "string", "description": "新标题"},
                        "description": {"type": "string", "description": "新描述"},
                        "priority": {"type": "integer", "description": "新优先级 1-5"},
                        "status": {"type": "string", "description": "新状态"}
                    },
                    "required": ["item_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_item",
                "description": "删除物品。普通用户只能删自己的，管理员可删所有。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "要删除的物品 ID"}
                    },
                    "required": ["item_id"]
                }
            }
        },
        # ==================== 评论工具 ====================
        {
            "type": "function",
            "function": {
                "name": "query_comments",
                "description": "查询指定物品下的所有评论。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "物品 ID"}
                    },
                    "required": ["item_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_comment",
                "description": "给物品添加评论，自动归属当前用户。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "description": "物品 ID"},
                        "body": {"type": "string", "description": "评论内容"}
                    },
                    "required": ["item_id", "body"]
                }
            }
        },
        # ==================== 文章创建 + 更新 ====================
        {
            "type": "function",
            "function": {
                "name": "create_article",
                "description": "创建新文章，自动归属当前用户。可同时指定标签（不存在的标签会自动创建）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "文章标题"},
                        "body": {"type": "string", "description": "文章正文"},
                        "description": {"type": "string", "description": "文章摘要（可选）"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签名列表（可选，不存在的标签会自动创建）"
                        }
                    },
                    "required": ["title", "body"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_own_article",
                "description": "更新文章。普通用户只能改自己的，管理员可改所有。通过 slug 标识文章。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "article_slug": {"type": "string", "description": "文章的 slug 标识"},
                        "title": {"type": "string", "description": "新标题"},
                        "body": {"type": "string", "description": "新正文"},
                        "description": {"type": "string", "description": "新摘要"}
                    },
                    "required": ["article_slug"]
                }
            }
        },
        # ==================== 标签工具 ====================
        {
            "type": "function",
            "function": {
                "name": "get_tags",
                "description": "获取系统中所有标签列表。",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_tag",
                "description": "创建新标签。如果标签已存在则返回错误。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "标签名称"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_tag",
                "description": "删除标签（仅管理员）。这是不可逆操作。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tag_id": {"type": "integer", "description": "要删除的标签 ID"}
                    },
                    "required": ["tag_id"]
                }
            }
        },
        # ==================== 社交功能工具 ====================
        {
            "type": "function",
            "function": {
                "name": "follow_user",
                "description": "关注指定用户。不能关注自己。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_user_id": {"type": "integer", "description": "要关注的用户 ID"}
                    },
                    "required": ["target_user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "unfollow_user",
                "description": "取消关注指定用户。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_user_id": {"type": "integer", "description": "要取消关注的用户 ID"}
                    },
                    "required": ["target_user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "favorite_article",
                "description": "收藏文章（只能代表当前登录用户操作，无法替其他用户收藏）。通过 slug 标识文章。返回 user_id 表示实际执行收藏的用户。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "article_slug": {"type": "string", "description": "文章的 slug 标识"}
                    },
                    "required": ["article_slug"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "unfavorite_article",
                "description": "取消收藏文章。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "article_slug": {"type": "string", "description": "文章的 slug 标识"}
                    },
                    "required": ["article_slug"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_profile",
                "description": "查看指定用户的公开资料，包括是否已关注。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "用户 ID"}
                    },
                    "required": ["user_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_own_profile",
                "description": "更新当前登录用户的个人资料。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string", "description": "新的全名"},
                        "bio": {"type": "string", "description": "新的个人简介"},
                        "image": {"type": "string", "description": "新的头像 URL"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_feed",
                "description": "获取当前用户关注的人发表的文章 Feed。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skip": {"type": "integer", "description": "分页起始，默认 0"},
                        "limit": {"type": "integer", "description": "分页数量，默认 20"}
                    }
                }
            }
        },
        # ==================== 缓存 + 任务 + 降级 ====================
        {
            "type": "function",
            "function": {
                "name": "get_cache_value",
                "description": "读取 Redis 缓存中指定 key 的值（仅管理员）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "缓存键名"}
                    },
                    "required": ["key"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_cache_value",
                "description": "向 Redis 写入缓存值（仅管理员）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "缓存键名"},
                        "value": {"type": "string", "description": "缓存值"},
                        "ttl": {"type": "integer", "description": "过期时间（秒），默认 60"}
                    },
                    "required": ["key", "value"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_task_status",
                "description": "查询 Celery 异步任务的执行状态。可用于追踪邮件发送等异步操作。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Celery 任务 ID"}
                    },
                    "required": ["task_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "demote_user_from_admin",
                "description": "将管理员降级为普通用户（仅管理员可操作）。不能降级自己。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "要降级的用户 ID"}
                    },
                    "required": ["user_id"]
                }
            }
        },
    ]
