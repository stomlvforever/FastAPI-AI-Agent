"""Agent 接口 Schema。

定义 Ops Copilot 对话请求、响应、历史记录和清空历史的响应结构。"""

from pydantic import BaseModel, Field
from typing import Optional


class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    message: str = Field(..., description="用户消息", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="对话会话 ID（可选，用于区分多个独立会话）")


class AgentChatResponse(BaseModel):
    """Agent 对话响应（非流式时使用）"""
    content: str = Field(..., description="Assistant 回复内容")
    tool_calls: Optional[list] = Field(None, description="执行的工具调用列表")


class AgentHistoryRequest(BaseModel):
    """获取对话历史请求"""
    limit: int = Field(default=20, description="返回最近 N 条消息", ge=1, le=100)


class AgentHistoryItem(BaseModel):
    """对话历史条目"""
    role: str = Field(..., description="角色：user/assistant/tool")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[str] = Field(None, description="消息时间戳")


class AgentHistoryResponse(BaseModel):
    """对话历史响应"""
    messages: list[AgentHistoryItem] = Field(..., description="对话历史列表")
    total: int = Field(..., description="总消息数")


class AgentClearHistoryResponse(BaseModel):
    """清空历史响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="操作结果消息")

