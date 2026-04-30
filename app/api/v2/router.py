"""API v2 路由汇总模块。

当前只挂载 ping 示例路由，作为后续 v2 扩展入口。"""

from fastapi import APIRouter

from app.api.v2.routes import ping

# v2 版本路由集合
router = APIRouter()
router.include_router(ping.router, tags=["v2"])
