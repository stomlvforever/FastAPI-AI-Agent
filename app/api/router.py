"""顶层 API 路由模块。

职责：聚合 v1 和 v2 版本路由，为它们统一添加版本前缀。

URL 结构：
- /api/v1/*  → v1 路由组（主版本，所有业务接口）
- /api/v2/*  → v2 路由组（预留版本，当前只有 /ping 示例）

版本化设计的意义：
- v1 路由可以继续演进而不破坏现有 API 契约
- v2 路由用于实验性接口或 API 重大变更
- 前端可以灰度升级调用新版 API
"""

from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.api.v2.router import router as v2_router
from app.core.config import settings

# 顶层路由聚合器——最终挂载到 FastAPI app 上
api_router = APIRouter()

# v1 路由：生产环境的主要 API 版本
api_router.include_router(v1_router, prefix=settings.api_v1_prefix)

# v2 路由：预留的 API 版本（当前仅 /ping 端点）
api_router.include_router(v2_router, prefix=settings.api_v2_prefix)
