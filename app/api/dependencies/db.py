"""数据库会话依赖模块。

为路由函数提供类型安全的 AsyncSession 依赖注入别名。

FastAPI 的依赖注入体系：
1. 定义 get_db() 工厂函数（在 app/db/session.py 中）
2. 用 Annotated 将"类型 + 依赖函数"绑定为一个别名
3. 路由函数参数声明 `session: SessionDep` 即可自动注入

Annotated 的核心价值：
  - 普通的 Depends(get_db) 需要写在函数默认值中，可能被格式化工具误改
  - Annotated[Type, Depends(...)] 是 PEP 593 标准，表达"这个参数的类型是 T，
    但还附加了依赖注入的元信息"，类型检查和 DI 各取所需
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

# SessionDep = 注入 AsyncSession 的类型别名
# 使用方式：async def list_items(session: SessionDep, ...):
SessionDep = Annotated[AsyncSession, Depends(get_db)]
