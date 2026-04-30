"""应用入口——uvicorn 启动文件。

这是 uvicorn 命令的入口点（`uvicorn main:app`），
实际应用创建逻辑在 app/main.py 中。
此处仅做 re-export，保持项目根目录的简洁。
"""

from app.main import app  # 应用入口（给 uvicorn main:app 用）

__all__ = ["app"]
