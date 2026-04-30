#!/bin/bash
# entrypoint.sh — 容器启动入口脚本
#
# 执行顺序：
# 1. 等待数据库就绪
# 2. 运行 Alembic 数据库迁移（自动建表/更新表结构）
# 3. 启动 FastAPI 应用

set -e  # 任何命令失败立即退出

echo "⏳ 等待数据库就绪..."
# 简单的重试机制：最多尝试 30 次，每次间隔 1 秒
for i in $(seq 1 30); do
    python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('db', 5432))
    s.close()
    exit(0)
except:
    exit(1)
" && break
    echo "  数据库未就绪，重试 ($i/30)..."
    sleep 1
done

echo "✅ 数据库已就绪"

echo "🔄 执行数据库迁移..."
python -m alembic upgrade head

echo "🚀 启动 FastAPI 应用..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
