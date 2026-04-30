# Windows PowerShell 版本：PostgreSQL 数据库备份脚本
# 用法: .\backup_db.ps1 [-BackupDir .\backups]

param(
    [string]$BackupDir = ".\backups",
    [string]$DbHost = $env:DB_HOST ?? "localhost",
    [string]$DbPort = $env:DB_PORT ?? "5432",
    [string]$DbName = $env:DB_NAME ?? "fastapi_db",
    [string]$DbUser = $env:DB_USER ?? "postgres",
    [int]$KeepDays = 7
)

$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "${DbName}_${Timestamp}.sql"

# 创建备份目录
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

Write-Host "============================================"
Write-Host " PostgreSQL 备份"
Write-Host " 数据库: ${DbName}@${DbHost}:${DbPort}"
Write-Host " 目标:   ${BackupFile}"
Write-Host "============================================"

# 设置密码环境变量
if ($env:DB_PASSWORD) {
    $env:PGPASSWORD = $env:DB_PASSWORD
}

# 执行备份
Write-Host "[1/3] 正在导出数据库..."
pg_dump -h $DbHost -p $DbPort -U $DbUser -d $DbName --no-owner --no-privileges -f $BackupFile

# 验证
Write-Host "[2/3] 验证备份文件..."
$FileInfo = Get-Item $BackupFile
if ($FileInfo.Length -gt 0) {
    $SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)
    Write-Host "  ✅ 备份成功: $BackupFile ($SizeMB MB)"
} else {
    Write-Host "  ❌ 备份文件为空"
    exit 1
}

# 清理旧备份
Write-Host "[3/3] 清理 ${KeepDays} 天前的旧备份..."
Get-ChildItem -Path $BackupDir -Filter "${DbName}_*.sql" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } |
    Remove-Item -Force
$Remaining = (Get-ChildItem -Path $BackupDir -Filter "${DbName}_*.sql").Count
Write-Host "  📁 当前共保留 $Remaining 个备份"

Write-Host ""
Write-Host "✅ 备份完成!"
Write-Host "  恢复命令: .\restore_db.ps1 -BackupFile $BackupFile"
