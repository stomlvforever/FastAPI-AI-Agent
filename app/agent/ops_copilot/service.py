"""Ops Copilot 的核心编排服务。

职责：加载记忆 → 构造模型上下文 → 调用 OpenAI → 处理工具调用 → 流式输出 → 写回会话记忆。

核心流程（chat 方法）：
  1. load_context()     从 Redis 加载五层记忆
  2. 判断是否需要召回    根据用户消息特征决定是否搜索历史记忆
  3. retrieve + rerank  关键词初筛 → LLM 精排（可选）
  4. build_context      组装 system prompt + summary + facts + recent + retrieved + user message
  5. 多轮工具调用循环   最多 5 轮，每轮 LLM 返回 tool_calls → 执行工具 → 追加 tool 消息 → 继续
  6. merge_facts +     本轮结束后更新 facts 并写回记忆
  7. 摘要刷新（条件触发） 当上下文字符数超预算或归档增量超阈值时触发 LLM 压缩

设计要点：
- 所有 OpenAI 调用带指数退避重试（429/5xx/超时/连接错误）
- 重试逻辑与流式输出解耦（流式只在 chat 主循环中产出）
- 工具权限检查在 _execute_tool 中完成（check_tool_permission 先检查角色）
- 记忆召回失败不影响主流程（降级到无记忆模式）
"""

from __future__ import annotations

from typing import AsyncGenerator, Awaitable, Callable, Optional, TypeVar
import asyncio
import json
import random

import httpx
import openai
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

# 从 memory 模块导入记忆相关类型和工具函数
from app.agent.ops_copilot.memory import (
    ConversationMemoryStore,
    MemoryContext,
    MemorySnippet,
    build_tool_digest,
    facts_to_text,
    looks_like_follow_up,
    merge_facts,
)
from app.agent.ops_copilot.tools import ToolExecutor, get_tools_schema
from app.core.config import settings
from app.db.models.user import User

T = TypeVar("T")


# ============================================================================
# OpenAI 客户端：懒加载单例
# ============================================================================

# 模块级缓存：整个应用生命周期只创建一个 AsyncOpenAI 实例
_openai_client: openai.AsyncOpenAI | None = None


def get_openai_client() -> openai.AsyncOpenAI:
    """返回懒加载的共享 OpenAI 客户端（单例模式）。

    设计理由：
    - 不在模块顶部创建，因为 settings 可能在 import 时还未加载
    - 用 global 变量缓存，避免每次调用都创建新连接池
    - max_retries=0：将重试逻辑交给自定义的 _run_openai_with_retry 控制，
      这样可以自定义哪些 HTTP 状态码需要重试、重试间隔更灵活
    - timeout 四元组：connect / read / write / pool 分别控制，
      防止网络抖动导致请求永久挂住
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            # httpx.Timeout 支持四个独立超时参数
            timeout=httpx.Timeout(
                connect=settings.openai_connect_timeout,  # 建立 TCP 连接的超时
                read=settings.openai_read_timeout,        # 读取响应的超时
                write=settings.openai_write_timeout,      # 发送请求体的超时
                pool=settings.openai_pool_timeout,        # 从连接池获取连接的超时
            ),
            max_retries=0,  # 由项目的 retry 逻辑统一管理
        )
    return _openai_client


# ============================================================================
# OpsCopilotService：Agent 核心编排类
# ============================================================================


class OpsCopilotService:
    """Ops Copilot Agent 的核心编排服务。

    每个会话创建一个实例（在 API 路由层的 chat/chat/stream 端点中），
    持有：
    - session:       数据库会话（供工具执行器使用）
    - current_user:  当前登录用户（用于权限判断和 System Prompt 角色描述）
    - tool_executor: 工具执行器（封装 30+ 工具函数的调用和权限校验）
    - memory_store:  分层记忆存储（读/写/召回 Redis 记忆）
    - system_prompt: 根据用户角色动态生成的 System Prompt
    """

    # 可重试的 HTTP 状态码集合：这些错误通常是临时性的
    _RETRYABLE_STATUS_CODES: set[int] = {429, 500, 502, 503}

    def __init__(self, session: AsyncSession, current_user: User):
        self.session = session
        self.current_user = current_user
        # 初始化工具执行器——注入数据库会话和当前用户
        self.tool_executor = ToolExecutor(session, current_user)
        # 初始化记忆存储器——按用户 ID 隔离
        self.memory_store = ConversationMemoryStore(current_user.id)

        # ---- 根据用户角色动态生成 System Prompt ----
        # 管理员和普通用户看到完全不同的 Prompt，确保权限边界清晰
        if current_user.role == "admin":
            role_desc = "管理员"
            role_rules = """- 你拥有全部工具权限，包括用户管理、系统监控和敏感管控操作。
- 执行删除、禁用、重置密码等敏感操作前，先明确说明风险和影响。
- 如用户意图不明确，不要直接执行高风险操作。"""
        else:
            role_desc = "普通用户"
            role_rules = """- 你只能使用普通用户可用的查询和内容管理工具。
- 涉及管理员权限的需求，必须直接说明当前角色无权执行。
- 你可以结合文章、评论、关注、收藏、资料和任务工具帮助用户完成操作。"""

        self.system_prompt = f"""你是 fastapi_chuxue 的智能运营助手 Ops Copilot。
当前用户角色：{role_desc}（{current_user.email}）。

你的职责：
1. 基于用户权限回答问题并调用工具。
2. 所有真实数据查询或修改都必须通过工具完成。
3. 用中文回答，并在需要时给出简洁、具体、可执行的建议。
4. 如果工具失败，解释原因并说明下一步建议。

权限规则：
{role_rules}
"""

    # ========================================================================
    # 对话历史管理（兼容旧版 API）
    # ========================================================================

    async def load_conversation_history(
        self,
        limit: int | None = None,
    ) -> tuple[list[dict], int]:
        """从 v2 记忆存储中加载对话历史。
        返回 (消息列表, 总消息数)，供前端或 API 端点查询。"""
        return await self.memory_store.load_history(limit)

    async def save_conversation_history(self, messages: list[dict]) -> None:
        """（已弃用）兼容旧版 API 的保存方法。
        v2 记忆系统已由 append_turn + merge_facts 自动保存，此方法仅为兼容保留。"""
        if len(messages) >= 2:
            # 取最后两条：倒数第二条是用户消息，最后一条是助手消息
            user_message = str(messages[-2].get("content") or "")
            assistant_message = str(messages[-1].get("content") or "")
            context = await self.memory_store.load_context()
            facts = merge_facts(context.facts, user_message, assistant_message, [])
            await self.memory_store.append_turn(user_message, assistant_message, [], facts)

    # ========================================================================
    # 核心对话方法：chat（流式输出）
    # ========================================================================

    async def chat(self, user_message: str) -> AsyncGenerator[str, None]:
        """处理用户消息并流式返回中间进度和最终回复。

        这是 Agent 的最上层入口，完整流程：
        1. 加载记忆上下文
        2. 条件性记忆召回（判断是否需要查历史）
        3. 构建消息列表（System Prompt + 记忆 + 用户消息）
        4. 多轮工具调用循环（最多 5 轮）
        5. 更新 facts 并写回记忆
        6. 条件性触发摘要刷新

        AsyncGenerator 产出：每收到新文本就 yield，前端通过 SSE 流式接收。
        """
        # ---- 第 1 步：加载当前用户记忆 ----
        context = await self.memory_store.load_context()
        retrieved_memories: list[MemorySnippet] = []
        rerank_used = False
        candidate_count = 0

        # ---- 第 2 步：条件性记忆召回 ----
        # 根据用户消息特征和当前记忆状态，决定是否需要搜索历史记忆
        if self._should_retrieve_memories(user_message, context):
            candidates = await self.memory_store.retrieve_candidates(user_message, context)
            candidate_count = len(candidates)
            if candidates:
                # 关键词初筛的结果交给 LLM 精排（如果启用）
                retrieved_memories, rerank_used = await self._rank_memory_candidates(
                    user_message,
                    candidates,
                )

        # 确定当前运行模式（用于日志/指标）：retrieve_and_rerank / summary_only / recent_only
        memory_mode = self._resolve_memory_mode(context, retrieved_memories, rerank_used)

        # ---- 第 3 步：构建消息列表 ----
        messages = self._build_context_messages(context, user_message, retrieved_memories)

        # ---- 第 4 步：多轮工具调用循环 ----
        max_rounds = 5  # 最大工具调用轮数，防止无限循环
        final_content = ""
        tool_digests: list[dict] = []

        for round_idx in range(max_rounds):
            # ---- 4a: 调用 OpenAI（带重试） ----
            try:
                choice = await self._call_openai_message_with_retry(messages)
            except openai.AuthenticationError:
                logger.error("OpenAI authentication failed: invalid API key")
                yield "AI 服务认证失败，请检查 API Key。\n"
                return
            except openai.RateLimitError:
                logger.warning("OpenAI rate limit exceeded after all retries")
                yield "AI 服务繁忙，请稍后再试。\n"
                return
            except openai.APITimeoutError:
                logger.warning("OpenAI API timeout after all retries")
                yield "AI 响应超时，请稍后重试。\n"
                return
            except openai.APIStatusError as exc:
                logger.error("OpenAI API status error: {} {}", exc.status_code, exc.message)
                yield f"AI 服务异常（HTTP {exc.status_code}），请稍后重试。\n"
                return
            except Exception as exc:
                logger.error("Unexpected OpenAI error (round {}): {}", round_idx, exc)
                yield f"AI 服务异常: {exc}\n"
                return

            # ---- 4b: 检查是否有工具调用 ----
            tool_calls = choice.tool_calls
            if not tool_calls:
                # 无工具调用 → LLM 给出了最终回答
                final_content = choice.content or ""
                break

            # 第一轮开始工具调用时通知前端
            if round_idx == 0:
                yield "Agent 正在执行工具...\n\n"

            # 将 LLM 的 assistant 消息（含 tool_calls）追加到消息历史
            messages.append(choice.model_dump())

            # ---- 4c: 逐个执行工具 ----
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                # 解析工具参数 JSON（解析失败时降级为空字典）
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                yield f"调用工具: {tool_name}\n"

                try:
                    # 执行工具（内部会做权限检查）
                    result = await self._execute_tool(tool_name, tool_args)
                    result_str = json.dumps(result, ensure_ascii=False)
                    # 记录工具调用消化
                    tool_digests.append(build_tool_digest(tool_name, tool_args, result))
                    yield f"工具返回结果:\n{json.dumps(result, ensure_ascii=False, indent=2)}\n\n"
                except Exception as exc:
                    # 工具执行异常：返回错误信息给 LLM，不中断主流程
                    error_result = {"error": str(exc)}
                    result_str = json.dumps(error_result, ensure_ascii=False)
                    tool_digests.append(build_tool_digest(tool_name, tool_args, error_result))
                    yield f"工具执行失败: {exc}\n"

                # 将工具返回结果作为 tool 角色消息追加到消息历史
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    }
                )

            yield "Agent 正在分析工具结果...\n\n"
        else:
            # for 循环没有被 break（即达到最大轮数仍未给出最终回答）
            final_content = "工具调用轮次过多，请简化问题后重试。"

        # 输出最终回复
        yield f"{final_content}\n"

        # ---- 第 5 步：更新记忆 ----
        # 合并本轮对话内容到 facts
        facts = merge_facts(context.facts, user_message, final_content, tool_digests)
        # 写入记忆存储
        updated_context = await self.memory_store.append_turn(
            user_message=user_message,
            assistant_message=final_content,
            tool_digests=tool_digests,
            facts=facts,
        )

        # ---- 第 6 步：条件性触发摘要刷新 ----
        await self._maybe_refresh_summary(updated_context)

        # 记录本轮 Agent 运行的记忆状态（用于调试和指标）
        logger.info(
            "agent memory updated user={} mode={} recent_count={} archive_candidates={} rerank_used={} retrieved_count={}",
            self.current_user.id,
            memory_mode,
            len(updated_context.recent_messages),
            candidate_count,
            rerank_used,
            len(retrieved_memories),
        )

    # ========================================================================
    # OpenAI API 调用层
    # ========================================================================

    async def _call_openai_api(self, messages: list[dict]):
        """调用 OpenAI Chat Completions API（带工具定义）。
        这是主对话模型调用，tools 参数启用了 Function Calling。
        返回 choices[0].message（可能包含 tool_calls 或 text content）。"""
        client = get_openai_client()
        # 在调用前清理消息格式（确保 tool_calls 格式符合 OpenAI API 要求）
        clean_messages = self._prepare_messages_for_openai(messages)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=clean_messages,
            tools=get_tools_schema(),  # 传入所有工具定义（含权限过滤后的）
            tool_choice="auto",        # 让模型自动决定是否调用工具
            temperature=0.3,           # 温和的创造性——既不太死板也不随机
        )
        return response.choices[0].message

    async def _call_openai_text(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        timeout: float | None = None,
    ) -> str:
        """纯文本 OpenAI 调用（不带工具定义）。
        用于摘要生成和记忆精排等不需要 Function Calling 的场景。
        temperature=0 确保输出稳定可预测。
        timeout 可选限制调用时长（如精排场景不能等太久）。"""
        client = get_openai_client()
        response = await client.chat.completions.create(
            model=model or settings.openai_model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
        return response.choices[0].message.content or ""

    # ========================================================================
    # 消息格式清理：确保 OpenAI API 兼容性
    # ========================================================================

    def _prepare_messages_for_openai(self, messages: list[dict]) -> list[dict]:
        """将内部消息格式转换为 OpenAI API 期望的干净格式。

        为什么需要这个步骤？
        - 内部消息可能从 Redis 反序列化后带了额外字段（如 message_id、created_at）
        - OpenAI API 对消息字段严格且有限制（尤其是在多轮 tool_calls 后需要回滚）
        - tool 角色消息只保留 tool_call_id + content
        - assistant 角色消息如果有 tool_calls，需要设置 content=None 并规范 tool_calls 结构
        - 其他角色只保留 role + content

        如果不清理就发给 OpenAI，会返回 "Additional properties are not allowed" 错误。
        """
        clean_messages: list[dict] = []
        for message in messages:
            role = message["role"]

            # 工具返回消息：只保留 tool_call_id 和 content
            if role == "tool":
                clean_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": message["tool_call_id"],
                        "content": message.get("content") or "",
                    }
                )
                continue

            # 助手消息含 tool_calls：清理 tool_calls 结构
            if role == "assistant" and message.get("tool_calls"):
                clean_tool_calls = []
                for tool_call in message["tool_calls"]:
                    clean_tool_calls.append(
                        {
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["function"]["name"],
                                "arguments": tool_call["function"]["arguments"],
                            },
                        }
                    )
                clean_messages.append(
                    {
                        "role": "assistant",
                        "content": None,  # 有 tool_calls 时 content 必须为 None
                        "tool_calls": clean_tool_calls,
                    }
                )
                continue

            # 普通消息（user / system / 无 tool_calls 的 assistant）
            clean_messages.append(
                {
                    "role": role,
                    "content": message.get("content") or "",
                }
            )
        return clean_messages

    # ========================================================================
    # 重试逻辑：指数退避 + 随机抖动
    # ========================================================================

    async def _call_openai_message_with_retry(self, messages: list[dict]):
        """调用对话 API（带自动重试）。"""
        return await self._run_openai_with_retry(lambda: self._call_openai_api(messages))

    async def _call_openai_text_with_retry(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        timeout: float | None = None,
    ) -> str:
        """调用纯文本 API（带自动重试）。"""
        return await self._run_openai_with_retry(
            lambda: self._call_openai_text(
                messages,
                model=model,
                temperature=temperature,
                timeout=timeout,
            )
        )

    async def _run_openai_with_retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        """通用 OpenAI 重试执行器：指数退避 + 随机抖动。

        重试策略：
        - 最多重试 max_retries 次（可配置）
        - 退避公式：base_delay × 2^attempt + random(0, 1)（指数退避 + 抖动防止雷鸣效应）
        - 可重试的错误：RateLimitError、APITimeoutError、APIConnectionError、
          以及 status_code 在 _RETRYABLE_STATUS_CODES 中的 APIStatusError
        - 不可重试的错误（如 400 Bad Request、401 Unauthorized）：直接抛出
        - 所有重试用完后仍失败的：抛出最后一个异常
        """
        max_retries = settings.openai_max_retries
        base_delay = settings.openai_retry_base_delay
        max_delay = settings.openai_retry_max_delay
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except openai.RateLimitError as exc:
                # 速率限制：等待更长时间，指数退避
                last_exception = exc
                if attempt >= max_retries:
                    break
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning("Rate limited, retry {}/{} after {:.1f}s", attempt + 1, max_retries, delay)
                await asyncio.sleep(delay)
            except openai.APITimeoutError as exc:
                # 超时：可能是服务端过载，同样指数退避
                last_exception = exc
                if attempt >= max_retries:
                    break
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning("OpenAI timeout, retry {}/{} after {:.1f}s", attempt + 1, max_retries, delay)
                await asyncio.sleep(delay)
            except openai.APIStatusError as exc:
                # HTTP 错误：只重试可重试的状态码
                if exc.status_code not in self._RETRYABLE_STATUS_CODES:
                    raise  # 不可重试的错误直接抛出
                last_exception = exc
                if attempt >= max_retries:
                    break
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    "OpenAI server error {}, retry {}/{} after {:.1f}s",
                    exc.status_code,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            except openai.APIConnectionError as exc:
                # 连接错误：可能 DNS/网络波动，重试
                last_exception = exc
                if attempt >= max_retries:
                    break
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning("OpenAI connection error, retry {}/{} after {:.1f}s", attempt + 1, max_retries, delay)
                await asyncio.sleep(delay)

        # 所有重试已用完，抛出最后一个异常
        raise last_exception  # type: ignore[misc]

    # ========================================================================
    # 工具执行：调度 + 权限检查
    # ========================================================================

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """执行指定的工具函数。

        工作流程：
        1. 在 tool_mapping 字典中查找工具名对应的执行函数
        2. 调用 check_tool_permission 检查当前用户角色是否有权调用
        3. 传入参数执行工具函数

        工具映射是显式的字典——不使用反射/动态调用，保证安全性。
        """
        # 工具名 → 执行函数的映射表
        tool_mapping = {
            "query_users": self.tool_executor.query_users,
            "get_user_stats": self.tool_executor.get_user_stats,
            "create_user": self.tool_executor.create_user,
            "delete_user": self.tool_executor.delete_user,
            "ban_user": self.tool_executor.ban_user,
            "unban_user": self.tool_executor.unban_user,
            "reset_user_password": self.tool_executor.reset_user_password,
            "promote_user_to_admin": self.tool_executor.promote_user_to_admin,
            "demote_user_from_admin": self.tool_executor.demote_user_from_admin,
            "admin_update_user": self.tool_executor.admin_update_user,
            "get_system_health": self.tool_executor.get_system_health,
            "get_request_metrics": self.tool_executor.get_request_metrics,
            "query_articles": self.tool_executor.query_articles,
            "get_article_stats": self.tool_executor.get_article_stats,
            "create_article": self.tool_executor.create_article,
            "update_own_article": self.tool_executor.update_own_article,
            "delete_article": self.tool_executor.delete_article,
            "query_items": self.tool_executor.query_items,
            "create_item": self.tool_executor.create_item,
            "update_item": self.tool_executor.update_item,
            "delete_item": self.tool_executor.delete_item,
            "query_comments": self.tool_executor.query_comments,
            "create_comment": self.tool_executor.create_comment,
            "delete_comment": self.tool_executor.delete_comment,
            "get_tags": self.tool_executor.get_tags,
            "create_tag": self.tool_executor.create_tag,
            "delete_tag": self.tool_executor.delete_tag,
            "follow_user": self.tool_executor.follow_user,
            "unfollow_user": self.tool_executor.unfollow_user,
            "favorite_article": self.tool_executor.favorite_article,
            "unfavorite_article": self.tool_executor.unfavorite_article,
            "get_profile": self.tool_executor.get_profile,
            "update_own_profile": self.tool_executor.update_own_profile,
            "get_feed": self.tool_executor.get_feed,
            "get_cache_value": self.tool_executor.get_cache_value,
            "set_cache_value": self.tool_executor.set_cache_value,
            "get_task_status": self.tool_executor.get_task_status,
            "send_bulk_email": self.tool_executor.send_bulk_email,
        }

        if tool_name not in tool_mapping:
            raise ValueError(f"Unknown tool: {tool_name}")

        # 先做权限检查（角色校验），失败会抛出 PermissionError
        self.tool_executor.check_tool_permission(tool_name)
        # 执行工具函数
        return await tool_mapping[tool_name](**args)

    # ========================================================================
    # 消息上下文构建
    # ========================================================================

    def _build_context_messages(
        self,
        context: MemoryContext,
        user_message: str,
        retrieved_memories: list[MemorySnippet],
    ) -> list[dict]:
        """构建发送给 OpenAI 的完整消息列表。

        消息顺序（遵循 System → Context → History → User 的模式）：
        1. System Prompt（角色描述 + 权限规则）
        2. Conversation Summary（对话历史摘要，如果有）
        3. Structured Facts（任务目标 + 偏好 + 实体 + 待办，如果有）
        4. Recent Messages（滑动窗口内的最近对话）
        5. Retrieved Memories（召回的关联历史记忆片段，如果有）
        6. User Message（当前用户消息）

        设计理由：
        - System Prompt 在最前面，给 LLM 设定角色和规则
        - 摘要和 facts 也在 system 角色中，LLM 不会混淆它们和历史对话
        - 召回的关联记忆独立一段 system 消息，引用格式清晰[archive/tool_digest/fact]
        - 用户消息放在最后，确保 LLM 直接响应它
        """
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]

        # 如果有历史摘要，追加为 system 消息
        if context.summary.text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Conversation summary:\n{context.summary.text}",
                }
            )

        # 如果有结构化 facts，追加为 system 消息
        facts_text = facts_to_text(context.facts)
        if facts_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Structured memory facts:\n{facts_text}",
                }
            )

        # 追加最近的对话历史（只保留 user 和 assistant 角色）
        for item in context.recent_messages:
            role = item.get("role")
            if role not in {"user", "assistant"}:
                continue
            messages.append(
                {
                    "role": role,
                    "content": item.get("content") or "",
                }
            )

        # 如果有召回的关联记忆，追加为 system 消息
        if retrieved_memories:
            # 编号列表格式，标注来源便于 LLM 理解
            rendered = "\n".join(
                f"{index}. [{snippet.source}] {snippet.text}"
                for index, snippet in enumerate(retrieved_memories, start=1)
            )
            messages.append(
                {
                    "role": "system",
                    "content": f"Relevant prior memories:\n{rendered}",
                }
            )

        # 最后追加用户当前消息
        messages.append({"role": "user", "content": user_message})
        return messages

    # ========================================================================
    # 记忆召回决策
    # ========================================================================

    def _should_retrieve_memories(self, user_message: str, context: MemoryContext) -> bool:
        """判断当前对话轮次是否需要触发记忆召回。

        决策规则（按优先级）：
        1. 如果没有任何可召回的内容（无 archive、无 tool_digests、无 facts）→ 不召回
        2. 如果用户消息是追问性质（"继续"、"刚才那个"等）→ 必须召回
        3. 如果消息包含结果依赖类关键词 + 存在工具摘要 → 召回
           （如"分析结果"、"再查一次"，说明需要引用之前的工具调用结果）
        4. 如果历史消息很少但有 archive/tool_digests → 召回
           （可能是新会话，但有历史记忆可用）
        5. 如果消息很短但存在历史 → 召回
           （短消息通常是"那个呢？"这种依赖上下文的问题）
        6. 其他情况 → 不召回

        这个决策函数控制 Token 消耗：无意义的召回不仅浪费 API 费用，
        还会冲淡 System Prompt 中更关键的信息。
        """
        # 没有任何可召回的内容，直接跳过
        if not context.archive_count and not context.tool_digests and not facts_to_text(context.facts):
            return False

        # 追问类消息必须召回（否则 LLM 不知道"那个"指的是什么）
        if looks_like_follow_up(user_message):
            return True

        # 结果依赖类关键词 + 有工具摘要 → 可能是"看一下刚才查的结果"
        lowered = user_message.lower()
        dependency_keywords = ("结果", "分析", "继续", "再", "again", "result", "follow up")
        if any(keyword in lowered for keyword in dependency_keywords) and context.tool_digests:
            return True

        # 历史对话很少但有记忆 → 新对话但可能有相关历史
        if len(context.recent_messages) < 2 and (context.archive_count or context.tool_digests):
            return True

        # 短消息 + 有记忆 → 很可能是依赖上下文的问题
        if len(user_message) < 30 and (context.archive_count or context.tool_digests):
            return True

        return False

    # ========================================================================
    # 记忆精排：关键词初筛 + LLM 精排（可选）
    # ========================================================================

    async def _rank_memory_candidates(
        self,
        query: str,
        candidates: list[MemorySnippet],
    ) -> tuple[list[MemorySnippet], bool]:
        """对召回候选项做精排。

        两阶段：
        1. 候选列表为空 → 直接返回空
        2. rerank 未启用 → 返回 Top K（按关键词分数）
        3. rerank 启用 → 调用 LLM 做精排

        LLM 精排的 Prompt 设计：
        - 要求返回纯 JSON（不要解释），格式 {"ranked":[{"index":1,"score":0.95}]}
        - 使用 1-based 索引（和候选列表对齐）
        - 超时保护 + 异常降级：精排失败时回退到关键词分数排序

        返回：(排序后的记忆片段列表, 是否使用了 LLM 精排)
        """
        if not candidates:
            return [], False

        # 精排未启用 → 直接取 Top K
        if not settings.agent_rerank_enabled:
            return candidates[: settings.agent_rerank_top_k], False

        # 构造精排 Prompt
        prompt = {
            "role": "user",
            "content": (
                "You are a memory reranker. Rank the candidate memory snippets for the query.\n"
                "Return JSON only in the form "
                '{"ranked":[{"index":1,"score":0.95}]}. '
                "Use 1-based indexes and sort by relevance descending.\n\n"
                f"Query:\n{query}\n\n"
                "Candidates:\n"
                + "\n".join(
                    f"{idx}. [{candidate.source}] {candidate.text}"
                    for idx, candidate in enumerate(candidates, start=1)
                )
            ),
        }

        try:
            content = await self._call_openai_text_with_retry(
                [
                    {
                        "role": "system",
                        "content": "Return compact JSON only. Do not explain your reasoning.",
                    },
                    prompt,
                ],
                model=settings.agent_rerank_model or settings.openai_model,
                temperature=0.0,  # 排序任务不需要创造性
                timeout=settings.agent_memory_search_timeout_seconds,
            )
            # 解析 LLM 返回的 JSON 排序结果
            parsed = json.loads(content)
            ranked_items = parsed.get("ranked", [])
            # 构建索引→分数的映射（1-based → 0-based）
            ranking_map = {
                int(item["index"]) - 1: float(item.get("score", 0))
                for item in ranked_items
                if "index" in item
            }
            # 应用精排分数
            ranked = []
            for index, candidate in enumerate(candidates):
                if index in ranking_map:
                    candidate.score = ranking_map[index]
                ranked.append(candidate)
            ranked.sort(key=lambda item: item.score, reverse=True)
            return ranked[: settings.agent_rerank_top_k], True
        except Exception as exc:
            # 精排失败 → 降级到关键词分数排序
            logger.warning("memory rerank failed, fallback to heuristic order: {}", exc)
            return candidates[: settings.agent_rerank_top_k], False

    # ========================================================================
    # 摘要生成：条件触发 + LLM 压缩
    # ========================================================================

    async def _maybe_refresh_summary(self, context: MemoryContext) -> None:
        """条件性触发对话摘要刷新。

        触发条件（两者满足任一即触发）：
        1. 归档增量 ≥ agent_summary_trigger_archive_delta：新归档的消息足够多了
        2. 总字符数 > agent_context_char_budget：上下文总字符数超出预算

        为什么需要摘要刷新？
        - 随着对话进行，archive 中的消息越来越多
        - 如果不压缩，将来召回时的 Prompt 会过长
        - 摘要将大量历史消息压缩为结构化文本，节省 Token
        """
        # 计算总字符数
        recent_chars = sum(len(str(item.get("content") or "")) for item in context.recent_messages)
        total_chars = recent_chars + len(context.summary.text)
        # 自上次摘要后的新归档消息数
        archive_delta = context.archive_count - context.summary.archive_cursor

        # 两个条件都不满足 → 跳过
        if archive_delta < settings.agent_summary_trigger_archive_delta and (
            total_chars <= settings.agent_context_char_budget
        ):
            return

        # 加载上次摘要 cursor 之后的新归档消息
        archive_items = await self.memory_store.load_archive_slice(context.summary.archive_cursor, -1)
        if not archive_items:
            return

        # 调用 LLM 生成摘要
        summary_text = await self._generate_summary(context, archive_items)
        if not summary_text:
            return

        # 保存摘要到 Redis（同时更新 archive_cursor）
        await self.memory_store.save_summary(summary_text, context.archive_count)

    async def _generate_summary(
        self,
        context: MemoryContext,
        archive_items: list[dict],
    ) -> str:
        """调用 LLM 生成对话摘要。

        摘要 Prompt 要求 LLM 按固定五段式输出：
        当前目标 / 已确认事实 / 已完成动作 / 待继续事项 / 约束/偏好
        这个结构化格式便于后续 Agent 快速定位需要的信息。

        异常降级：LLM 调用失败时使用 _fallback_summary 生成简版摘要。
        """
        # 将归档消息格式化为列表文本
        archive_text = "\n".join(
            f"- {item.get('role', 'unknown')}: {item.get('content', '')}"
            for item in archive_items
        )
        facts_text = facts_to_text(context.facts) or "- None"

        try:
            summary = await self._call_openai_text_with_retry(
                [
                    {
                        "role": "system",
                        "content": (
                            "Summarize older conversation history into a compact structured memory. "
                            "Use the same language as the conversation. Keep the exact section order:\n"
                            "当前目标:\n已确认事实:\n已完成动作:\n待继续事项:\n约束/偏好:"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Previous summary:\n{context.summary.text or 'None'}\n\n"
                            f"Structured facts:\n{facts_text}\n\n"
                            f"New archive snippets:\n{archive_text}"
                        ),
                    },
                ],
                temperature=0.1,
                timeout=settings.agent_memory_search_timeout_seconds,
            )
            return summary.strip()
        except Exception as exc:
            logger.warning("summary refresh failed, using fallback summary: {}", exc)
            return self._fallback_summary(context, archive_items)

    def _fallback_summary(self, context: MemoryContext, archive_items: list[dict]) -> str:
        """生成不依赖 LLM 的降级摘要。
        直接从 facts 和最近 3 条归档消息中拼出结构化文本。
        虽然不如 LLM 摘要精确，但保证在 API 不可用时系统仍能运行。"""
        recent_archive = "；".join(
            str(item.get("content") or "")[:120] for item in archive_items[-3:]
        )
        facts_text = facts_to_text(context.facts) or "无"
        return (
            f"当前目标:\n{context.facts.get('task_goal') or '无'}\n"
            f"已确认事实:\n{facts_text}\n"
            f"已完成动作:\n{recent_archive or '无'}\n"
            "待继续事项:\n待结合后续对话更新\n"
            f"约束/偏好:\n{'; '.join(context.facts.get('preferences') or []) or '无'}"
        )

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _resolve_memory_mode(
        self,
        context: MemoryContext,
        retrieved_memories: list[MemorySnippet],
        rerank_used: bool,
    ) -> str:
        """确定当前 Agent 运行模式，仅用于日志/指标。
        - retrieve_and_rerank：有记忆被召回
        - summary_only：没有召回结果但有摘要
        - recent_only：只有最近的对话，无摘要无召回
        """
        if retrieved_memories:
            return "retrieve_and_rerank"
        if context.summary.text:
            return "summary_only"
        return "recent_only"

    async def clear_history(self) -> None:
        """清空当前用户的所有 Agent 对话记忆。"""
        await self.memory_store.clear()


# ============================================================================
# AgentStreamResponse：SSE 流式响应适配器
# ============================================================================


class AgentStreamResponse:
    """SSE（Server-Sent Events）流式响应适配器。

    将 AsyncGenerator 的纯文本 yield 包装为 SSE 格式：
    data: {"content": "..."}\n\n

    用法：
    在 FastAPI 路由中返回此对象，设置 media_type="text/event-stream"，
    前端通过 EventSource 或 fetch + ReadableStream 消费。
    """

    def __init__(self, generator: AsyncGenerator[str, None]):
        self.generator = generator

    async def __aiter__(self):
        """实现异步迭代器协议：每次 yield 一行 SSE 格式数据。
        内容用 JSON 包装，前端统一解析。"""
        async for chunk in self.generator:
            yield f"data: {json.dumps({'content': chunk})}\n\n"
