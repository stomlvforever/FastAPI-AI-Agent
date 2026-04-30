#!/usr/bin/env bash
# ============================================================
# PostgreSQL 数据库恢复脚本
# 用法: bash restore_db.sh <备份文件.sql.gz>
# ============================================================
set -euo pipefail

# ---------- 参数检查 ----------
if [ $# -lt 1 ]; then
    echo "用法: bash restore_db.sh <备份文件.sql.gz>"
    echo "示例: bash restore_db.sh ./backups/fastapi_db_20250101_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ 备份文件不存在: ${BACKUP_FILE}"
    exit 1
fi

# ---------- 配置 ----------
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-fastapi_db}"
DB_USER="${DB_USER:-postgres}"

echo "============================================"
echo " PostgreSQL 恢复"
echo " 数据库: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo " 备份:   ${BACKUP_FILE}"
echo "============================================"
echo ""
echo "⚠️  警告: 此操作将覆盖数据库 '${DB_NAME}' 中的所有数据!"
echo ""
read -p "确认恢复? (输入 yes 继续): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "已取消."
    exit 0
fi

# ---------- 断开现有连接 ----------
echo "[1/4] 断开数据库的现有连接..."
PGPASSWORD="${DB_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>/dev/null || true

# ---------- 重建数据库 ----------
echo "[2/4] 重建数据库..."
PGPASSWORD="${DB_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";" \
    2>/dev/null
PGPASSWORD="${DB_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -c "CREATE DATABASE \"${DB_NAME}\";" \
    2>/dev/null

# ---------- 恢复数据 ----------
echo "[3/4] 正在恢复数据..."
gunzip -c "${BACKUP_FILE}" | PGPASSWORD="${DB_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --single-transaction \
    2>/dev/null

# ---------- 验证 ----------
echo "[4/4] 验证恢复结果..."
TABLE_COUNT=$(PGPASSWORD="${DB_PASSWORD:-}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" \
    2>/dev/null | tr -d ' ')
echo "  📊 public schema 中共 ${TABLE_COUNT} 张表"

echo ""
echo "✅ 恢复完成!"
echo "  建议: 恢复后执行 'alembic upgrade head' 确保迁移一致"
