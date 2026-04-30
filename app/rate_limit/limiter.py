"""限流器配置模块。

基于客户端地址创建 SlowAPI Limiter，供接口限流装饰器使用。"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 基于客户端 IP 的限流器
# default_limits: 全局限流策略，默认每个 IP 每分钟 60 次请求
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    headers_enabled=True  # 在响应头中返回 X-RateLimit-* 信息
)



