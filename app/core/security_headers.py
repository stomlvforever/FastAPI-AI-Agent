"""安全响应头模块。

集中设置常见安全响应头，降低点击劫持、MIME 嗅探等基础风险。"""

from fastapi import Response


def apply_security_headers(response: Response) -> None:
    """Set common security headers on every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    # HSTS is safe when served behind HTTPS reverse proxy.
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

