"""限流依赖导出模块。

作为 API dependencies 命名空间的统一入口，供路由层通过
from app.api.dependencies.limiter import limiter 引用共享限流器。

这样做的好处：
- 路由文件不直接依赖 app/rate_limit/limiter（底层实现）
- 如果未来限流实现变更（如换成 Redis 分布式限流），只需修改此模块的导入路径
- 保持依赖层次清晰：Route → dependencies → rate_limit
"""

from fastapi import Request
from app.rate_limit.limiter import limiter
