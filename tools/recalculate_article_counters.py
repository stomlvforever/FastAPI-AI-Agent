"""管理命令：重新校准文章物化计数字段。

用法：
    python tools/recalculate_article_counters.py

适合放到定时任务中周期执行，用真实关联表修正 articles 表里的计数字段。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import AsyncSessionLocal, close_db
from app.repositories.article_repo import ArticleRepository


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await ArticleRepository(session).recalculate_counters()
        print(result)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
