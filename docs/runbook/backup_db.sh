#!/usr/bin/env bash
# ============================================================
# PostgreSQL 数据库备份脚本
# 用法: bash backup_db.sh [备份目录]
# 默认备份到 ./backups/ 目录
# ============================================================
set -euo pipefail

# ---------- 配置 ----------
# 可通过环境变量覆盖
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-fastapi_db}"
DB_USER="${DB_USER:-postgres}"
BACKUP_DIR="${1:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"  # 保留最近 N 天的备份

# ---------- 时间戳 ----------
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

# ---------- 创建备份目录 ----------
mkdir -p "${BACKUP_DIR}"

echo "============================================"
echo " PostgreSQL 备份"
echo " 数据库: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo " 目标:   ${BACKUP_FILE}"
echo "============================================"

# ---------- 执行备份 ----------
# pg_dump 格式说明:
#   --format=custom (-Fc)  → 使用自定义压缩格式（推荐生产环境）
#   这里使用 plain + gzip 方便查看 SQL 内容（学习用途）
echo "[1/3] 正在导出数据库..."
PGPASSWORD="${DB_PASSWORD:-}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-privileges \
    --verbose \
    2>/dev/null | gzip > "${BACKUP_FILE}"

# ---------- 验证备份 ----------
echo "[2/3] 验证备份文件..."
FILE_SIZE=$(stat --printf="%s" "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null)
if [ "${FILE_SIZE}" -gt 0 ]; then
    echo "  ✅ 备份成功: ${BACKUP_FILE} ($(numfmt --to=iec ${FILE_SIZE} 2>/dev/null || echo "${FILE_SIZE} bytes"))"
else
    echo "  ❌ 备份文件为空，请检查数据库连接"
    exit 1
fi

# ---------- 清理旧备份 ----------
echo "[3/3] 清理 ${KEEP_DAYS} 天前的旧备份..."
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true
REMAINING=$(find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" | wc -l)
echo "  📁 当前共保留 ${REMAINING} 个备份"

echo ""
echo "✅ 备份完成!"
echo "  恢复命令: bash restore_db.sh ${BACKUP_FILE}"
