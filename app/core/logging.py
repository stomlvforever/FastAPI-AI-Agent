"""日志配置模块。

统一配置 loguru 输出格式、日志级别和运行时日志行为。"""

import sys

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    # 移除默认 logger，避免重复输出
    logger.remove()
    # 输出到 stdout，日志级别来自配置
    logger.add(sys.stdout, level=settings.log_level)


