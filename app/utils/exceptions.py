"""全局异常处理模块。

统一处理 FastAPI 应用中的三类异常，返回一致的 JSON 错误响应格式。

三类异常处理：
1. HTTPException：框架级别的 HTTP 异常（404/401/403 等）
   → 返回 {"error": detail, "path": url_path}
2. RequestValidationError：Pydantic 参数校验失败（422）
   → 返回 {"error": "validation_error", "details": [...], "path": url_path}
3. 未捕获异常（可选扩展）：由 FastAPI 默认处理（500 Internal Server Error）

设计原则：
- 所有错误响应包含 path 字段，方便客户端定位出错的接口
- 所有错误响应使用 JSON 格式，统一前端解析逻辑
- 不在异常处理中做业务逻辑（只做格式转换）
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用实例。

    在 app/main.py 的 create_app() 中调用此函数，统一注册所有处理器。
    使用闭包模式：在函数内部用 @app.exception_handler 装饰器注册。"""

    # ---- HTTP 异常处理器 (404/401/403/422 等) ----
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """统一 HTTP 异常的 JSON 响应格式。
        SlowAPI 的限流异常（429）也会经过此处理器。
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "path": request.url.path},
        )

    # ---- 参数校验异常处理器 (Pydantic 校验失败) ----
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """统一 Pydantic 校验错误的 JSON 响应格式。

        exc.errors() 返回 Pydantic v2 的标准化错误详情列表，每项包含：
        - type: 错误类型（如 "missing", "string_type", "value_error"）
        - loc: 错误位置（如 ["body", "email"]）
        - msg: 人类可读的错误描述
        """
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "details": exc.errors(),
                "path": request.url.path,
            },
        )
