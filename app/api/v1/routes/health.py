"""健康检查接口。

用于容器健康检查、部署探活和基础服务可用性验证。"""

from fastapi import APIRouter, Request, Response

from app.rate_limit.limiter import limiter

router = APIRouter()


@router.get("/health")
@limiter.limit("10/minute")
async def health(request: Request, response: Response):
    # 健康检查：通常用于容器/负载均衡存活探测
    return {"status": "ok"}


