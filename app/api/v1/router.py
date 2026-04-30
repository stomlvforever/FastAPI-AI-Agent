"""API v1 路由汇总模块。

将 v1 版本下的 14 个业务子路由统一挂载到一个 APIRouter，
供顶层 API router（app/api/router.py）引入。

每个子路由有独立的 tags 标签，影响 Swagger UI 的分组显示顺序和分组名。
tags 按功能域划分：health / auth / verification / admin / users /
profiles / items / articles / tags / comments / tasks / cache / metrics / agent / ws
"""

from fastapi import APIRouter

# 导入所有 v1 子路由模块——虽然看起来像"未使用"的 import，但 include_router 需要模块引用
from app.api.v1.routes import admin_users, agent, articles, auth, cache, comments, health, items, metrics, profiles, tags, tasks, users, verification, ws

# v1 版本路由集合
router = APIRouter()

# 按功能分组挂载子路由，tags 参数影响 Swagger UI 端点分组
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, tags=["auth"])
router.include_router(verification.router, tags=["verification"])
router.include_router(admin_users.router, tags=["admin"])
router.include_router(users.router, tags=["users"])
router.include_router(profiles.router, tags=["profiles"])
router.include_router(items.router, tags=["items"])
router.include_router(articles.router, tags=["articles"])
router.include_router(tags.router, tags=["tags"])
router.include_router(comments.router, tags=["comments"])
router.include_router(tasks.router, tags=["tasks"])
router.include_router(cache.router, tags=["cache"])
router.include_router(metrics.router, tags=["metrics"])
router.include_router(agent.router, tags=["agent"])
router.include_router(ws.router, tags=["ws"])
