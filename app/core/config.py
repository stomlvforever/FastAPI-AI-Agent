"""应用配置模块。

使用 Pydantic Settings 从环境变量和 .env 文件读取所有配置项。
Pydantic Settings v2 会自动：
1. 加载 .env 文件中的 KEY=VALUE 对
2. 覆盖为环境变量（环境变量优先级高于 .env）
3. 做类型转换（字符串自动转为 int/float/list 等）
4. 执行自定义校验器（field_validator）

配置项按功能分组：
- 基础应用：app_name, environment, API 前缀
- 安全：secret_key, JWT 过期时间, 加密算法
- 数据库与缓存：PostgreSQL URL, Redis URL
- Celery：消息代理和结果后端
- 邮件：SMTP 配置
- 文件存储：本地 / S3 切换
- 验证码：过期时间 / 位数
- 短信：provider 和阿里云/Twilio 凭证
- OpenAI / LLM：API Key, 模型, 超时, 重试
- 监控：慢请求阈值
- 跨域：CORS 来源列表
- Agent Memory：滑动窗口、召回参数、精排配置等
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（fastapi_chuxue/）
# Path(__file__) = .../app/core/config.py → .parent.parent.parent = fastapi_chuxue/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """全局应用配置类——单例模式，启动时解析。

    Pydantic Settings 会在类实例化时自动：
    1. 从 env_file (默认为 .env) 加载变量
    2. 用环境变量覆盖同名配置
    3. 验证类型并执行 field_validator
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),  # .env 文件路径
        env_file_encoding="utf-8",
        case_sensitive=False,              # 变量名大小写不敏感
        extra="ignore",                    # 忽略 .env 中未定义的额外变量
    )

    # ========================================================================
    # 基础应用配置
    # ========================================================================
    app_name: str = "fastapi_chuxue"
    environment: str = "dev"               # dev / test / production
    api_v1_prefix: str = "/api/v1"         # v1 API 路由前缀
    api_v2_prefix: str = "/api/v2"         # v2 API 路由前缀（预留）

    # ========================================================================
    # 安全相关配置
    # ========================================================================
    secret_key: str = "change-me"          # JWT 签名密钥（生产环境必须修改！）
    access_token_expire_minutes: int = 30  # Access Token 有效期（分钟）
    refresh_token_expire_days: int = 7     # Refresh Token 有效期（天）
    algorithm: str = "HS256"               # JWT 签名算法（HS256 = HMAC-SHA256）

    # ========================================================================
    # 数据库与缓存配置
    # ========================================================================
    # asyncpg 是 FastAPI 推荐的高性能异步 PostgreSQL 驱动
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_chuxue"
    # Redis 既用于缓存也用于 Agent 记忆存储
    redis_url: str = "redis://localhost:6379/0"

    # ========================================================================
    # Celery 异步任务配置
    # ========================================================================
    celery_broker_url: str = "redis://localhost:6379/1"   # 消息代理（Broker）
    celery_result_backend: str = "redis://localhost:6379/2"  # 结果后端（Backend）

    # ========================================================================
    # 邮件配置（SMTP - 126 邮箱）
    # ========================================================================
    mail_username: str = ""
    mail_password: str = ""   # 126 邮箱授权码（非登录密码）
    mail_from: str = "noreply@example.com"
    mail_port: int = 465
    mail_server: str = "smtp.126.com"
    mail_ssl_tls: bool = True
    mail_starttls: bool = False

    # ========================================================================
    # 文件存储配置（抽象设计：可通过 storage_type 切换本地/S3）
    # ========================================================================
    storage_type: str = "local"             # "local"（本地磁盘）或 "s3"（对象存储）
    # S3 配置（仅 storage_type="s3" 时生效）
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""               # 使用 MinIO 等兼容服务时填写此字段
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ========================================================================
    # 验证码配置
    # ========================================================================
    verify_code_expire_seconds: int = 300   # 验证码有效期（5 分钟）
    verify_code_length: int = 6             # 验证码位数

    # ========================================================================
    # 短信配置（抽象设计：可通过 sms_provider 切换 mock/aliyun/twilio）
    # ========================================================================
    sms_provider: str = "mock"              # "mock"=无真实发送, "aliyun"=阿里云, "twilio"=Twilio
    # 阿里云短信配置
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_sms_sign_name: str = ""          # 阿里云短信签名（需先申请）
    aliyun_sms_template_code: str = ""      # 阿里云短信模板 CODE（如 SMS_123456789）

    # ========================================================================
    # OpenAI / LLM 配置（Ops Copilot Agent 依赖）
    # ========================================================================
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"       # 默认使用的模型
    openai_api_base: str = "https://api.openai-proxy.org/v1"  # API 基础 URL（可换代理/兼容端点）

    # OpenAI 超时与重试配置
    # 四个独立超时时间段（对应 httpx.Timeout 的四元组）
    openai_connect_timeout: float = 5.0     # TCP 连接超时（秒）
    openai_read_timeout: float = 60.0       # 读取响应超时（秒）—— LLM 生成慢，需留足
    openai_write_timeout: float = 10.0      # 发送请求体超时（秒）
    openai_pool_timeout: float = 10.0       # 从连接池获取连接超时（秒）
    # 重试策略（指数退避 + 随机抖动，防止雷鸣效应）
    openai_max_retries: int = 3             # 最多重试次数
    openai_retry_base_delay: float = 1.0    # 基础延迟（秒），退避公式：base × 2^attempt + jitter
    openai_retry_max_delay: float = 30.0    # 单次延迟上限（秒）

    # ========================================================================
    # 监控配置
    # ========================================================================
    slow_request_threshold: float = 0.001   # 慢请求阈值（秒），超过此值的请求记录告警日志

    # ========================================================================
    # 跨域与日志
    # ========================================================================
    cors_origins: list[str] = ["http://localhost:3000"]  # 允许的 CORS 来源列表
    log_level: str = "INFO"                               # Loguru 日志级别

    # ========================================================================
    # Agent Memory v2 配置（分层记忆系统参数）
    # ========================================================================
    agent_memory_prefix: str = "agent_memory_v2"  # Redis key 前缀，区分不同版本/环境
    agent_recent_window: int = 12                 # 滑动窗口大小（最近 N 条消息）
    agent_tool_digest_limit: int = 6              # 工具调用摘要保留数量
    agent_archive_scan_limit: int = 50            # 记忆召回时扫描的 archive 尾部条数
    agent_retrieval_preselect: int = 12           # 关键词召回最大候选数
    agent_rerank_top_k: int = 3                   # LLM 精排后返回 Top K
    agent_summary_trigger_archive_delta: int = 6  # 触发摘要的最小归档增量
    agent_context_char_budget: int = 6000         # 上下文字符预算（超过触发摘要压缩）
    agent_rerank_enabled: bool = True             # 是否启用 LLM 精排
    agent_rerank_model: str = ""                  # 精排专用模型（空=使用默认模型）
    agent_memory_ttl_seconds: int = 86400         # 记忆 TTL（24 小时，过期自动清理）
    agent_memory_search_timeout_seconds: float = 5.0  # 记忆搜索/精排超时（秒）

    # ========================================================================
    # 自定义校验器
    # ========================================================================

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        """允许用逗号分隔的字符串配置 CORS 来源列表。
        例如在 .env 中写：CORS_ORIGINS=http://a.com,https://b.com"""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


# ========================================================================
# 全局配置单例
# ========================================================================
# 应用启动时即创建—所有模块通过 `from app.core.config import settings` 访问
# Pydantic Settings 在第一次实例化时自动加载 .env 文件
settings = Settings()
