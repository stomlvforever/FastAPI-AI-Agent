"""API v2 示例路由。

用于验证 v2 路由挂载是否正常。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping():
    # v2 示例接口
    return {"message": "pong", "version": "v2"}


