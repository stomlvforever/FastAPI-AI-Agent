# FastAPI AI Agent

一个工程化 FastAPI 全栈项目，包含博客业务、认证权限、缓存限流、异步任务、React 前端、一键 Docker 部署，以及基于 OpenAI Function Calling 的 Ops Copilot 智能运营 Agent。

## 项目亮点

- 后端采用 Route、Service、Repository、Model 分层结构，覆盖用户、文章、评论、标签、关注、收藏、Feed、文件上传、验证码、缓存、任务和监控接口。
- Agent 支持自然语言操作业务系统，通过工具调用完成查询用户、查询文章、统计指标、禁用用户、重置密码、删除内容、发送邮件和查看系统健康状态。
- Redis 分层记忆包含 recent、archive、summary、facts、tool_digests，支持多轮上下文、工具摘要和历史召回。
- SSE 流式接口实时返回 Agent 执行过程，前端对 chunk 做增量拼接和节流渲染，降低长文本输出卡顿。
- React + TypeScript + Vite 前端包含登录注册、文章流、文章详情、编辑器、个人主页、作者页、收藏关注、标签筛选和独立 Copilot 页面。
- Docker Compose 一键启动 Nginx、React 前端、FastAPI、PostgreSQL、Redis 和 Celery Worker，Nginx 统一代理前端、API、静态文件和 SSE 流式接口。

## 技术栈

- Backend: FastAPI, Pydantic v2, SQLAlchemy Async, asyncpg, Alembic
- Auth: JWT 双令牌, RBAC, Passlib, bcrypt
- AI Agent: OpenAI AsyncOpenAI, Function Calling, SSE, Redis Memory
- Cache and Task: Redis, SlowAPI, Celery
- Frontend: React 19, TypeScript, Vite, React Router, TanStack Query
- Deploy: Docker Compose, Nginx, PostgreSQL 15, Redis 7

## 目录结构

```text
fastapi_chuxue/
  app/
    agent/ops_copilot/      # Agent 编排、工具和 Redis 记忆
    api/                    # v1/v2 路由和依赖注入
    cache/                  # Redis 连接池
    core/                   # 配置、安全、邮件、存储、日志、指标
    db/                     # 数据库会话和 ORM 模型
    repositories/           # 数据访问层
    services/               # 业务服务层
    tasks/                  # Celery 后台任务
  alembic/                  # 数据库迁移
  docker_deploy/            # Dockerfile、Compose、Nginx
  frontend/                 # React 前端
  streamlit_app/            # 早期 Agent 演示面板
  tests/                    # 后端测试
  tools/                    # 管理脚本
```

## Ops Copilot 流程

1. 前端向 `POST /api/v1/agent/chat/stream` 发送自然语言问题。
2. FastAPI 校验 JWT，获取当前用户和角色。
3. Agent 从 Redis 加载当前用户的分层记忆。
4. Agent 构建 system prompt、历史上下文、用户消息和工具 schema。
5. OpenAI Function Calling 判断是否需要调用工具。
6. 后端解析 tool_calls，并通过工具白名单和 RBAC 做权限兜底。
7. 工具函数访问数据库、Redis 或任务队列，返回真实业务结果。
8. 工具结果作为 tool message 回填给模型，模型生成最终中文回复。
9. 后端通过 SSE 持续推送中间过程和最终内容。
10. 本轮 user、assistant、tool_digests 和 facts 写回 Redis。

## 主要接口

- `POST /api/v1/users` 注册用户
- `POST /api/v1/auth/login` 登录并返回 access token 和 refresh token
- `POST /api/v1/auth/refresh` 刷新 access token
- `GET /api/v1/users/me` 获取当前用户
- `POST /api/v1/articles` 创建文章
- `GET /api/v1/articles` 文章列表，支持分页和排序
- `GET /api/v1/feed` 关注流
- `POST /api/v1/articles/{slug}/favorite` 收藏文章
- `POST /api/v1/agent/chat/stream` Agent SSE 流式对话
- `GET /api/v1/agent/history` 查询 Agent 历史
- `DELETE /api/v1/agent/history` 清空 Agent 历史

## 本地运行

```bash
cd fastapi_chuxue
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

访问地址：

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/api/v1/health`

## 前端运行

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

## 一键部署

先复制环境变量文件并填写必要配置：

```bash
copy .env.example .env
```

启动完整服务：

```bash
docker compose -f docker_deploy/docker-compose.yml up --build -d
```

查看服务状态和日志：

```bash
docker compose -f docker_deploy/docker-compose.yml ps
docker compose -f docker_deploy/docker-compose.yml logs -f app
docker compose -f docker_deploy/docker-compose.yml logs -f nginx
```

停止服务：

```bash
docker compose -f docker_deploy/docker-compose.yml down
```

部署后入口：

- 前端首页：`http://localhost/`
- Swagger：`http://localhost/docs`
- 健康检查：`http://localhost/api/v1/health`
- Agent 流式接口：`http://localhost/api/v1/agent/chat/stream`

## Nginx 代理说明

Nginx 是唯一对外入口，内部通过 Docker Compose 服务名访问 `frontend` 和 `app`。Agent SSE 接口单独关闭代理缓冲：

```nginx
location = /api/v1/agent/chat/stream {
    proxy_pass http://fastapi_app;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    add_header X-Accel-Buffering no;
}
```

这样浏览器可以实时收到大模型输出，而不会等 Nginx 缓冲满之后再一次性返回。

## 数据库迁移

```bash
alembic upgrade head
alembic revision --autogenerate -m "message"
alembic downgrade -1
```

## 测试

```bash
pytest -q
```

项目包含认证、RBAC、文章权限、物化计数字段、分页排序、Redis 验证码和基础接口测试。

## 环境变量

请参考 `.env.example`。真实 `.env` 已被 `.gitignore` 忽略，不要提交真实密钥。

关键配置：

- `SECRET_KEY`: JWT 签名密钥
- `DB_URL`: PostgreSQL 连接地址
- `REDIS_URL`: Redis 连接地址
- `OPENAI_API_KEY`: Agent 调用大模型所需 Key
- `OPENAI_MODEL`: Agent 默认模型
- `CORS_ORIGINS`: 前端跨域白名单
- `MAIL_USERNAME` 和 `MAIL_PASSWORD`: 邮件发送配置

## 安全说明

- `.env`、虚拟环境、缓存文件、上传目录和前端构建产物不会提交到 Git。
- 代码中的云服务密钥、邮箱授权码和 OpenAI Key 默认值均为空，需要通过环境变量注入。
- 管理员工具由 `ADMIN_ONLY_TOOLS` 白名单控制，后端执行工具前会做 RBAC 校验。
- Refresh Token 和 Access Token 在后端解码时会校验 `type` 字段，避免令牌类型混用。

## GitHub

目标仓库：`https://github.com/stomlvforever/FastAPI-AI-Agent.git`
