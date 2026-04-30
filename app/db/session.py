"""异步数据库会话模块。

负责创建 AsyncEngine、AsyncSession 工厂，并提供数据库启动/关闭和会话依赖注入。

分层架构中的位置：
  API 路由层 → 通过 SessionDep 依赖注入获得 AsyncSession
  Service 层 → 通过构造函数注入 AsyncSession
  Repository 层 → 通过构造函数注入 AsyncSession

核心组件：
- engine：全局唯一的异步数据库引擎（应用生命周期内复用）
- AsyncSessionLocal：会话工厂，每次请求生成一个新的 AsyncSession
- get_db()：FastAPI 依赖注入函数，自动管理会话的生命周期
- init_db()：开发环境自动建表（生产环境用 Alembic 迁移）
- close_db()：应用关闭时释放数据库连接
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base

# ============================================================================
# 数据库引擎与会话工厂
# ============================================================================

# 创建异步数据库引擎
# echo=True：打印所有 SQL 语句（开发调试用，生产关掉）
# pool_pre_ping=True：连接池返回连接前先 ping，确保连接有效（防止连接被数据库超时关闭）
engine = create_async_engine(settings.db_url, echo=True, pool_pre_ping=True)

# 创建异步会话工厂
# expire_on_commit=False：提交后不标记对象为"过期"，允许在提交后继续访问属性
#   （AsyncSession 默认 expire_on_commit=True，但在 Web 请求中通常不需要）
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


# ============================================================================
# 生命周期管理
# ============================================================================


async def init_db() -> None:
    """初始化数据库——开发环境自动建表。

    仅在 environment="dev" 时执行，生产环境必须通过 Alembic 迁移管理 schema。
    通过导入 models 包来确保 Base.metadata 已经注册了所有表定义，
    然后调用 create_all 在数据库中创建对应的表结构。
    """
    if settings.environment == "dev":
        # 导入所有模型，触发 ORM 类的元数据注册到 Base.metadata
        # noqa: F401 告诉 Ruff 忽略"导入但未使用"的警告
        from app.db import models  # noqa: F401

        # create_all 在数据库事务中执行 CREATE TABLE（如果表不存在）
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """释放数据库引擎的资源（关闭连接池中的所有连接）。
    在应用 shutdown 事件中调用，避免进程退出时连接泄露。"""
    await engine.dispose()


# ============================================================================
# 会话依赖注入
# ============================================================================


async def get_db():
    """FastAPI 依赖注入：每次请求生成一个 AsyncSession。

    使用 async context manager 自动管理会话生命周期：
    - async with 进入时：创建新会话
    - yield 时：将会话传给路由函数
    - async with 退出时：自动关闭会话并归还到连接池

    在路由中的使用方式：
    @router.get("/items")
    async def list_items(session: SessionDep):
        ...
    其中 SessionDep = Annotated[AsyncSession, Depends(get_db)]
    """
    async with AsyncSessionLocal() as session:
        yield session
