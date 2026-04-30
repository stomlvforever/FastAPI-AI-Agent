"""Ops Copilot Agent 接口（Agent Routes）。

提供 Agent 对话的 HTTP 端点：
- POST /agent/chat          — 非流式对话（一次性返回完整响应）
- POST /agent/chat/stream   — SSE 流式对话（实时显示 Agent 思考过程）
- GET /agent/history         — 查询当前用户的对话历史
- DELETE /agent/history      — 清空当前用户的对话历史

流式接口的 Session 管理策略：
- agent_chat（非流式）使用 SessionDep：路由返回时关闭 session，正常
- agent_chat_stream（流式）不使用 SessionDep：
  因为 StreamingResponse 在路由返回后才执行 generator，
  此时 FastAPI 已经释放了依赖注入提供的 AsyncSession。
  解决方案：在 generator 内部用 AsyncSessionLocal() 创建独立的 session，
  生成完毕后再关闭——确保所有 DB 操作都在有效 session 内完成。
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.db import SessionDep
from app.db.session import AsyncSessionLocal
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentHistoryResponse,
    AgentHistoryItem,
    AgentClearHistoryResponse,
)
from app.agent.ops_copilot.service import OpsCopilotService, AgentStreamResponse

router = APIRouter()


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    """非流式对话——发送一条消息，等待 Agent 完整回复。

    适用场景：
    - 不需要实时反馈的简单查询
    - 批量/脚本调用
    - 前端不方便处理 SSE 的场景

    内部实际上是流式收集 + 拼接返回：
    虽然是 async generator，但此端点等待所有 chunk 收集完成后才返回。
    """
    try:
        service = OpsCopilotService(session, current_user)

        # 流式收集所有输出片段，拼接为完整响应
        response_content = ""
        async for chunk in service.chat(request.message):
            response_content += chunk

        return AgentChatResponse(content=response_content)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}"
        )


@router.post("/agent/chat/stream")
async def agent_chat_stream(
    request: AgentChatRequest,
    current_user: CurrentUser,  # 注意：不使用 SessionDep，session 在 generator 内管理
):
    """流式对话——通过 SSE（Server-Sent Events）实时返回 Agent 的思考过程。

    前端可以看到 Agent 逐步输出：
    "Agent 正在执行工具..."
    "调用工具: query_articles"
    "工具返回结果: {...}"
    "Agent 正在分析工具结果..."
    "根据查询结果，您有 3 篇文章..."

    这个接口不使用 SessionDep 的原因：
    FastAPI 在路由函数返回 StreamingResponse 后就会关闭依赖注入的 session。
    但 generator 此时还在执行 DB 操作（工具调用）。
    所以 generator 内部自行创建和关闭 AsyncSession，确保生命周期匹配。

    响应头：
    - Content-Type: text/event-stream（SSE 必须）
    - Cache-Control: no-cache（禁止缓存）
    - X-Accel-Buffering: no（Nginx 代理时不缓冲 SSE 流）
    """
    async def _stream_with_session():
        """在独立的 AsyncSession 上下文中执行流式对话。

        用 async with AsyncSessionLocal() 创建新 session：
        - 生成过程中所有 DB 操作共用此 session
        - 生成完成后自动调用 close() 归还连接
        """
        async with AsyncSessionLocal() as session:
            service = OpsCopilotService(session, current_user)
            # AgentStreamResponse 将纯文本包装为 SSE 格式 "data: {...}\n\n"
            async for chunk in AgentStreamResponse(service.chat(request.message)):
                yield chunk

    try:
        return StreamingResponse(
            _stream_with_session(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # 通知 Nginx 不要缓冲 SSE 流
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stream error: {str(e)}"
        )


@router.get("/agent/history", response_model=AgentHistoryResponse)
async def get_agent_history(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = 20,
):
    """查询当前用户的 Agent 对话历史。

    返回最多 limit 条消息，按时间倒序（最新的在前）。
    每条消息包含 role（user/assistant）、content 和 timestamp。
    """
    try:
        service = OpsCopilotService(session, current_user)
        history, total = await service.load_conversation_history(limit=limit)

        items = [
            AgentHistoryItem(
                role=msg.get("role", "unknown"),
                content=msg.get("content", ""),
                timestamp=msg.get("created_at") or msg.get("timestamp"),
            )
            for msg in history
        ]

        return AgentHistoryResponse(
            messages=items,
            total=total
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load history: {str(e)}"
        )


@router.delete("/agent/history", response_model=AgentClearHistoryResponse)
async def clear_agent_history(
    session: SessionDep,
    current_user: CurrentUser,
):
    """清空当前用户的 Agent 对话历史（不可恢复）。
    清除 Redis 中该用户的全部 5 个记忆 key。"""
    try:
        service = OpsCopilotService(session, current_user)
        await service.clear_history()

        return AgentClearHistoryResponse(
            success=True,
            message="Conversation history cleared"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear history: {str(e)}"
        )
