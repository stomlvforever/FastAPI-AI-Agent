"""运行指标接口。

仅管理员可访问，用于查看请求数、错误率、慢请求和热门端点等内存指标。"""

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_admin
from app.core.metrics import metrics

router = APIRouter()


@router.get("/metrics", summary="查看应用指标（仅管理员）")
async def get_metrics(_=Depends(require_admin)):
    """
    返回应用运行指标：
    - uptime_seconds: 运行时长
    - total_requests: 总请求数
    - total_errors: 总错误数
    - error_rate: 错误率 (%)
    - top_endpoints: 请求量 Top 10
    - slowest_endpoints: 平均延迟 Top 10
    - errors_by_status: 按状态码分组的错误数
    - recent_slow_requests: 最近 10 条慢请求
    """
    return metrics.get_metrics()

