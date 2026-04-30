# Windows PowerShell 版本：PostgreSQL 数据库恢复脚本
# 用法: .\restore_db.ps1 -BackupFile .\backups\fastapi_db_20250101_120000.sql

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$DbHost = $env:DB_HOST ?? "localhost",
    [string]$DbPort = $env:DB_PORT ?? "5432",
    [string]$DbName = $env:DB_NAME ?? "fastapi_db",
    [string]$DbUser = $env:DB_USER ?? "postgres"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    Write-Host "❌ 备份文件不存在: $BackupFile"
    exit 1
}

Write-Host "============================================"
Write-Host " PostgreSQL 恢复"
Write-Host " 数据库: ${DbName}@${DbHost}:${DbPort}"
Write-Host " 备份:   ${BackupFile}"
Write-Host "============================================"
Write-Host ""
Write-Host "⚠️  警告: 此操作将覆盖数据库 '$DbName' 中的所有数据!"
$Confirm = Read-Host "确认恢复? (输入 yes 继续)"
if ($Confirm -ne "yes") {
    Write-Host "已取消."
    exit 0
}

if ($env:DB_PASSWORD) {
    $env:PGPASSWORD = $env:DB_PASSWORD
}

# 断开现有连接
Write-Host "[1/4] 断开数据库的现有连接..."
psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DbName' AND pid <> pg_backend_pid();" 2>$null

# 重建数据库
Write-Host "[2/4] 重建数据库..."
psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS `"$DbName`";" 2>$null
psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "CREATE DATABASE `"$DbName`";" 2>$null

# 恢复数据
Write-Host "[3/4] 正在恢复数据..."
psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -f $BackupFile --single-transaction 2>$null

# 验证
Write-Host "[4/4] 验证恢复结果..."
$TableCount = psql -h $DbHost -p $DbPort -U $DbUser -d $DbName -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>$null
Write-Host "  📊 public schema 中共 $($TableCount.Trim()) 张表"

Write-Host ""
Write-Host "✅ 恢复完成!"
Write-Host "  建议: 恢复后执行 'alembic upgrade head' 确保迁移一致"
