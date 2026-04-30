"""SQLAlchemy 声明式基类模块。

Base 是所有 ORM 模型的公共基类，继承自 SQLAlchemy 2.0 的 DeclarativeBase。
其核心作用有二：
1. 统一元数据管理：所有模型通过 Base 共享同一个 MetaData 对象，
   Alembic 通过 Base.metadata 获取所有表的 DDL 信息来生成迁移
2. 提供声明式映射：通过 Mapped[] + mapped_column() 语法定义表和列，
   不需要手动声明 Table 对象

使用示例：
  class User(Base):
      __tablename__ = "users"
      id: Mapped[int] = mapped_column(primary_key=True)
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类——继承自 SQLAlchemy 2.0 的 DeclarativeBase。"""

    pass
