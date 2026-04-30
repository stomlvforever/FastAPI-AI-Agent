# ============ 第一阶段：安装依赖 ============
# 使用 Python 3.11 精简版作为基础镜像
FROM python:3.11-slim AS base

# 设置工作目录为 /app
WORKDIR /app

# 防止 Python 生成 .pyc 字节码文件（减小镜像体积）
ENV PYTHONDONTWRITEBYTECODE=1
# 让 Python 输出直接显示，不缓冲（方便查看日志）
ENV PYTHONUNBUFFERED=1

# 先复制依赖文件（利用 Docker 缓存层，依赖不变时不重新安装）
COPY requirements.txt .
# 安装 Python 依赖包，--no-cache-dir 不保存缓存（减小镜像体积）
RUN pip install --no-cache-dir -r requirements.txt

# ============ 第二阶段：复制代码 ============
# 复制项目所有文件到容器
COPY . .

# 将 docker_deploy/entrypoint.sh 复制到根目录并赋予执行权限
COPY docker_deploy/entrypoint.sh .
RUN chmod +x entrypoint.sh

# 创建上传文件目录（头像等）
RUN mkdir -p /app/uploads/avatars

# 创建非 root 用户运行应用（安全最佳实践）
RUN adduser --disabled-password --no-create-home appuser
# 给上传目录写入权限
RUN chown -R appuser:appuser /app/uploads
USER appuser

# 暴露端口（文档用途，实际映射在 docker-compose 中配置）
EXPOSE 8000

# 容器启动时执行入口脚本（先迁移数据库，再启动服务）
CMD ["bash", "entrypoint.sh"]
