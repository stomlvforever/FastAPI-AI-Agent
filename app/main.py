"""应用启动入口（app/main.py）。

这是 FastAPI 应用的真正创建和配置入口。

启动流程：
1. lifespan 上下文管理器：
   - 启动时：配置日志 → 初始化数据库（dev 环境建表） → 启动应用
   - 关闭时：释放数据库连接 → 关闭 Redis 连接
2. 中间件注册顺序（执行顺序是注册时的逆序）：
   - CORSMiddleware（最外层：允许跨域）
   - SlowAPIMiddleware（限流）
   - add_security_headers（安全头 + 指标 + 慢请求）
3. 异常处理器：统一 HTTPException 和 ValidationError 的 JSON 响应
4. 路由挂载：v1/v2 版本路由 + 静态文件目录

中间件执行链（请求进入时）：
  CORS → SlowAPI → 安全头+指标+慢请求 → 路由函数 → 异常处理器
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import time

from loguru import logger

from app.api.router import api_router
from app.cache.redis import close_redis
from app.core.config import BASE_DIR, settings
from app.core.logging import setup_logging
from app.core.metrics import metrics
from app.core.security_headers import apply_security_headers
from app.db.session import close_db, init_db
from app.rate_limit.limiter import limiter
from app.utils.exceptions import register_exception_handlers


# ============================================================================
# 应用生命周期管理
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期上下文管理器。

    使用 asynccontextmanager 将一个 async generator 包装为 FastAPI 的 lifespan 处理器。
    yield 之前的代码在应用启动时执行，之后的代码在应用关闭时执行。
    """
    # ====== 启动阶段 ======
    setup_logging()  # 配置 Loguru 日志系统
    # 测试环境不主动连接数据库——pytest 会通过 dependency_overrides 注入 mock 会话
    if settings.environment != "test":
        await init_db()  # dev 环境：create_all 建表；生产环境：不做任何操作

    # yield 将控制权交还给 FastAPI，应用正式运行
    yield

    # ====== 关闭阶段 ======
    if settings.environment != "test":
        await close_db()  # 释放数据库连接池
    await close_redis()  # 关闭 Redis 连接


# ============================================================================
# FastAPI 应用实例
# ============================================================================

app = FastAPI(title=settings.app_name, lifespan=lifespan)

# ============================================================================
# 中间件注册（按注册顺序，但执行顺序是逆序的）
# ============================================================================

# ---- CORS 中间件：允许前端跨域访问 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 速率限制器 ----
# 将 limiter 挂载到 app.state，SlowAPI 通过 request.app.state.limiter 访问
app.state.limiter = limiter
# 统一处理限流超出异常（429 Too Many Requests）
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# 限流中间件：基于 IP 的请求频率控制
app.add_middleware(SlowAPIMiddleware)

# ---- 自定义 HTTP 中间件：安全响应头 + 指标收集 + 慢请求告警 ----
@app.middleware("http")
async def add_security_headers(request, call_next):
    """为每个 HTTP 请求注入安全响应头、收集指标并记录慢请求。

    这个中间件的执行时机在 SlowAPI 限流之后、路由函数之前，
    记录的是实际请求处理时间（不包括中间的排队等待时间）。

    三合一设计的原因：
    - 安全头注入依赖响应对象，必须在响应返回前设置
    - 指标收集需要记录请求路径、方法和响应状态码
    - 慢请求检测需要测量从请求进入中间件到响应返回的耗时
      三者都在同一个代码块中自然组合，不需要拆成三个独立中间件。
    """
    start = time.time()
    response = await call_next(request)  # 执行下一个中间件和路由函数
    duration = time.time() - start       # 计算处理耗时

    # 1. 安全响应头注入
    apply_security_headers(response)

    # 2. 指标收集（线程安全的内存计数器）
    path = request.url.path
    method = request.method
    metrics.record_request(method, path, response.status_code, duration)

    # 3. 慢请求告警日志
    slow_threshold = getattr(settings, "slow_request_threshold", 1.0)
    if duration >= slow_threshold:
        logger.warning(
            "🐢 Slow request: {method} {path} → {status} in {ms:.0f}ms",
            method=method,
            path=path,
            status=response.status_code,
            ms=duration * 1000,
        )

    return response


# ============================================================================
# 异常处理器 + 路由 + 静态文件
# ============================================================================

# 全局异常处理器：统一 HTTPException 和 ValidationError 的 JSON 响应格式
register_exception_handlers(app)

# 挂载版本化 API 路由（内含 v1 和 v2 子路由）
app.include_router(api_router)

# 挂载头像静态文件目录
# 上传的头像存储在 uploads/avatars/，通过 /static/avatars/xxx.jpg 访问
UPLOAD_DIR = BASE_DIR / "uploads" / "avatars"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 确保目录存在
app.mount("/static/avatars", StaticFiles(directory=str(UPLOAD_DIR)), name="avatars")
