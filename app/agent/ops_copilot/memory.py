"""Ops Copilot 的 Redis 分层记忆模块。

核心设计思路（参考 MemGPT 的分层记忆思想）：
1. 将对话记忆拆分为五层存储：recent（最近消息）、archive（归档消息）、
   summary（LLM 生成的摘要）、facts（结构化事实）、tool_digests（工具调用摘要）
2. 通过关键词匹配 + LLM 精排实现记忆召回，解决长对话上下文窗口限制
3. 全部存储在 Redis 中，TTL 过期机制管理内存，无需额外数据库

数据流向：
  用户消息 → load_context() 加载当前记忆 → 构建 System Prompt → LLM 调用
  → append_turn() 写入新消息 → 窗口溢出时自动归档 → 触发摘要刷新（必要时）

作者：fastapi_chuxue 项目
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any

from loguru import logger

from app.cache.redis import get_redis
from app.core.config import settings


# ============================================================================
# 工具函数：时间、默认值、JSON 安全解析、文本规范化
# ============================================================================


def utc_now_iso() -> str:
    """获取当前 UTC 时间的 ISO 格式字符串。
    用于给记忆条目打时间戳，统一使用 UTC 避免时区问题。"""
    return datetime.now(timezone.utc).isoformat()


def default_facts() -> dict[str, list[str] | str]:
    """返回 facts（结构化事实）的默认空白模板。
    四个维度：
    - task_goal:   用户当前任务目标（一段文字）
    - preferences: 用户偏好列表（如"用中文回答"、"简洁模式"）
    - entities:    从对话中提取的关键实体（邮箱、用户名、ID、中文词等）
    - open_loops:  尚未解决的待办/追问事项
    每次加载或合并 facts 时都用此模板兜底，保证字段完整。
    """
    return {
        "task_goal": "",
        "preferences": [],
        "entities": [],
        "open_loops": [],
    }


# ============================================================================
# 数据类：记忆快照、摘要状态、上下文容器
# ============================================================================


@dataclass
class SummaryState:
    """摘要状态——描述当前已压缩的对话摘要。"""
    text: str = ""
    # 摘要正文（由 LLM 生成的压缩文本）
    updated_at: str | None = None
    # 最后更新摘要的时间戳，用于判断是否需要重新生成
    archive_cursor: int = 0
    # 归档游标：已压缩到摘要中的 archive 消息序号，增量归档时只处理 cursor 之后的消息


@dataclass
class MemorySnippet:
    """一个记忆片段——召回时的候选项。
    来自 archive / facts / tool_digests 等不同来源。"""
    source: str
    # 来源标签：'archive' | 'fact' | 'tool_digest'
    text: str
    # 记忆片段的文本内容
    score: float = 0.0
    # 相关性评分（关键词匹配初始分 + LLM 精排分）
    created_at: str | None = None
    # 片段创建时间，用于排序和日志


@dataclass
class MemoryContext:
    """记忆上下文——每次 LLM 调用前从 Redis 加载的完整记忆快照。
    这个容器汇聚了五层记忆，是构建 System Prompt 的数据源。"""
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    # 最近 N 轮对话（滑动窗口内的完整消息）
    summary: SummaryState = field(default_factory=SummaryState)
    # 历史对话的 LLM 压缩摘要
    facts: dict[str, list[str] | str] = field(default_factory=default_facts)
    # 结构化事实（任务目标 + 偏好 + 实体 + 待办）
    tool_digests: list[dict[str, Any]] = field(default_factory=list)
    # 最近工具调用的输入输出摘要（防止 LLM 重复调用同一工具）
    archive_count: int = 0
    # 归档消息的总数（用于判断是否有历史可召回）


# ============================================================================
# JSON / 文本处理工具
# ============================================================================


def _safe_load_json(payload: str | None, default: Any) -> Any:
    """安全解析 JSON 字符串：空值或解析失败时返回默认值，不抛异常。
    Redis 可能返回 None 或损坏的数据，此函数保证记忆加载永远不崩溃。"""
    if not payload:
        return default
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return default


def _normalize_text(value: str, limit: int = 500) -> str:
    """规范化文本：压缩多余空白、截断超长内容。
    用于控制每条记忆片段的长度，避免 Token 浪费。
    limit=500 是默认上限，不同场景可调（如 facts 的 task_goal 用 300）。
    """
    # 压缩所有连续空白为单个空格
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    # 超长时截断并加省略号，留出 3 个字符给 "..."
    return f"{compact[: limit - 3]}..."


def normalize_facts(raw_facts: dict[str, Any] | None) -> dict[str, list[str] | str]:
    """规范化 facts 字典：去重、截断、限速。
    从 Redis 加载的 facts 可能被篡改或格式错误，此函数确保输出安全的标准化结构。
    各字段限制：
    - task_goal: 最多 300 字符
    - preferences/entities/open_loops: 每项最多 160 字符，最多保留 8 条
    - 自动去重（按规范化后的文本比对）
    """
    facts = default_facts()
    if not raw_facts:
        return facts

    # 任务目标：纯文本，截断到 300 字符
    facts["task_goal"] = _normalize_text(str(raw_facts.get("task_goal", "")), limit=300)
    # 遍历三个列表字段，逐项规范化
    for key in ("preferences", "entities", "open_loops"):
        values = raw_facts.get(key) or []
        if isinstance(values, list):
            deduped: list[str] = []
            for item in values:
                text = _normalize_text(str(item), limit=160)
                if text and text not in deduped:  # 去重
                    deduped.append(text)
            facts[key] = deduped[:8]  # 每类最多 8 条
    return facts


def facts_to_text(facts: dict[str, list[str] | str]) -> str:
    """将结构化 facts 字典转为可嵌入 System Prompt 的文本。
    格式为多行 Markdown 列表，供 LLM 直接阅读理解。"""
    lines: list[str] = []

    task_goal = str(facts.get("task_goal") or "").strip()
    if task_goal:
        lines.append(f"- Current goal: {task_goal}")

    # 三个维度的映射：显示名 → facts 键名
    for label, key in (
        ("Preferences", "preferences"),
        ("Entities", "entities"),
        ("Open loops", "open_loops"),
    ):
        values = facts.get(key) or []
        if values:
            joined = "; ".join(str(v) for v in values)
            lines.append(f"- {label}: {joined}")

    return "\n".join(lines)


# ============================================================================
# 实体提取、偏好提取、追问检测
# ============================================================================


def extract_entities_from_text(text: str) -> list[str]:
    """从文本中提取关键实体。
    用四种正则模式匹配：
    1. 邮箱地址
    2. 英文单词/标识符（>=3字符）
    3. 中文词组（>=2个汉字）
    4. 日期格式（如 2024-01-15）

    用途：用于记忆召回时的关键词匹配，提取的实体越多，召回精度越高。
    """
    lowered = text.lower()
    entities: list[str] = []
    patterns = [
        r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",  # 邮箱
        r"\b[a-z0-9_-]{3,}\b",                       # 英文标识符（>=3字符）
        r"[\u4e00-\u9fff]{2,}",                       # 中文词组（>=2字）
        r"\b\d{1,4}(?:-\d{1,2}(?:-\d{1,2})?)?\b",    # 日期/数字格式
    ]
    for pattern in patterns:
        for match in re.findall(pattern, lowered):
            token = match.strip()
            if len(token) < 2:
                continue
            if token not in entities:  # 去重
                entities.append(token)
    return entities[:20]  # 最多 20 个实体


def looks_like_follow_up(text: str) -> bool:
    """检测用户消息是否为'追问/延续'性质的消息。
    这类消息依赖上下文才有意义（如"继续"、"刚才那个呢？"），
    检测结果影响记忆召回策略：
      - 如果是追问 → 触发记忆召回（必须加载历史才能理解）
      - 如果是新话题 → 更新 task_goal，不强制召回
    """
    lowered = text.lower()
    keywords = (
        "继续",
        "刚才",
        "之前",
        "前面",
        "上次",
        "那个",
        "这些",
        "based on",
        "continue",
        "earlier",
        "previous",
        "that one",
    )
    return any(keyword in lowered for keyword in keywords)


def extract_preferences_from_text(text: str) -> list[str]:
    """从用户消息中提取偏好设置。
    通过检测偏好关键词（如"不要"、"简洁"、"中文"）来识别用户偏好，
    以标点符号为分隔符切分句子，逐句检查是否包含偏好标记。
    """
    snippets: list[str] = []
    # 用中英文标点切分句子，每个句子可能是独立偏好
    segments = re.split(r"[，。,.\n！？!?；;]", text)
    markers = ("不要", "别", "只", "优先", "先", "简洁", "详细", "中文", "英文", "markdown")
    for segment in segments:
        cleaned = _normalize_text(segment, limit=120)
        if cleaned and any(marker in cleaned for marker in markers) and cleaned not in snippets:
            snippets.append(cleaned)
    return snippets[:5]  # 最多 5 条偏好


# ============================================================================
# 工具摘要构建
# ============================================================================


def build_tool_digest(tool_name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """构建一个工具调用的摘要记录。
    每条摘要包含工具名、输入参数摘要、输出结果摘要和时间戳。
    输入截断到 240 字符，输出截断到 400 字符——平衡信息保留与 Token 消耗。
    这些摘要会在后续对话中作为上下文召回，防止 LLM 重复调用相同工具。"""
    input_digest = _normalize_text(json.dumps(args, ensure_ascii=False, sort_keys=True), limit=240)
    output_digest = _normalize_text(json.dumps(result, ensure_ascii=False, sort_keys=True), limit=400)
    return {
        "tool_name": tool_name,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "created_at": utc_now_iso(),
    }


# ============================================================================
# Facts 合并引擎：每轮对话后自动更新结构化记忆
# ============================================================================


def merge_facts(
    current_facts: dict[str, Any],
    user_message: str,
    assistant_message: str,
    tool_digests: list[dict[str, Any]],
) -> dict[str, list[str] | str]:
    """合并本轮对话内容到 facts 中。
    此函数是 Agent 记忆更新的核心——每轮对话结束后自动执行：
    1. 如果用户不是追问，更新 task_goal 为新目标
    2. 从用户消息中提取偏好和实体
    3. 从工具调用消化中提取实体和待办
    4. 从助手回复中提取追问句，加入 open_loops
    """
    facts = normalize_facts(current_facts)

    # 如果不是追问或还没有目标 → 把用户消息作为新任务目标
    # 追问时保留原有目标不变，因为用户的意图仍然是之前的目标
    if not looks_like_follow_up(user_message) or not facts["task_goal"]:
        facts["task_goal"] = _normalize_text(user_message, limit=300)

    # 提取用户偏好（如"用中文"、"不要用表格"）
    for preference in extract_preferences_from_text(user_message):
        if preference not in facts["preferences"]:
            facts["preferences"].append(preference)

    # 提取实体（邮箱、用户名、中文词等）
    for entity in extract_entities_from_text(user_message):
        if entity not in facts["entities"]:
            facts["entities"].append(entity)

    # 从工具调用消化中提取信息
    # 取最近 N 条（由配置决定，避免无限增长）
    for digest in tool_digests[-settings.agent_tool_digest_limit :]:
        # 工具摘要加入 open_loops，表示"已完成但可能需要跟进的操作"
        summary = _normalize_text(
            f"{digest.get('tool_name')}: {digest.get('output_digest', '')}",
            limit=180,
        )
        if summary and summary not in facts["open_loops"]:
            facts["open_loops"].append(summary)
        # 工具输入输出中的实体也提取出来
        for entity in extract_entities_from_text(
            f"{digest.get('input_digest', '')} {digest.get('output_digest', '')}"
        ):
            if entity not in facts["entities"]:
                facts["entities"].append(entity)

    # 从助手回复中检测追问句子
    # 如果助手问了问题或请求用户确认，这些就是 open_loops
    if assistant_message:
        follow_up_lines = re.split(r"[。！？!?]\s*", assistant_message)
        for line in follow_up_lines:
            cleaned = _normalize_text(line, limit=160)
            if cleaned and ("?" in line or "？" in line or "可以" in cleaned or "需要" in cleaned):
                if cleaned not in facts["open_loops"]:
                    facts["open_loops"].append(cleaned)

    # 控制每条列表的长度上限
    facts["preferences"] = facts["preferences"][:8]
    facts["entities"] = facts["entities"][:12]
    facts["open_loops"] = facts["open_loops"][:8]
    return facts


# ============================================================================
# 文本分词（关键词匹配的基础）
# ============================================================================


def _tokenize(text: str) -> set[str]:
    """将文本拆分为 Token 集合，用于记忆召回的关键词匹配。
    直接复用实体提取函数作为简单分词器——不需要复杂的 NLP 分词，
    因为 Agent 对话的实体密度较高，实体匹配已足够有效。"""
    return set(extract_entities_from_text(text))


# ============================================================================
# ConversationMemoryStore：Redis 支持的 v2 分层记忆存储
# ============================================================================


class ConversationMemoryStore:
    """Redis 支持的 v2 分层记忆存储。

    五层 Redis Key 结构（按 user_id 隔离）：
      {prefix}:{user_id}:recent       → List，滑动窗口内的完整消息
      {prefix}:{user_id}:archive      → List，超出窗口的归档消息
      {prefix}:{user_id}:summary      → String (JSON)，对话摘要元信息
      {prefix}:{user_id}:facts        → String (JSON)，结构化事实
      {prefix}:{user_id}:tool_digests → List，工具调用摘要

    所有 key 共享同一个 TTL，到期自动全部清理。
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        # Redis key 前缀，确保不同用户隔离、不同环境不冲突
        self.prefix = f"{settings.agent_memory_prefix}:{user_id}"

    def _key(self, suffix: str) -> str:
        """拼接完整 Redis key"""
        return f"{self.prefix}:{suffix}"

    # ---- Redis Key 属性 ----
    @property
    def recent_key(self) -> str:
        return self._key("recent")

    @property
    def summary_key(self) -> str:
        return self._key("summary")

    @property
    def facts_key(self) -> str:
        return self._key("facts")

    @property
    def tool_digests_key(self) -> str:
        return self._key("tool_digests")

    @property
    def archive_key(self) -> str:
        return self._key("archive")

    # ---- 生命周期管理 ----

    async def _touch_all(self, redis) -> None:
        """刷新所有记忆 key 的 TTL。
        每次读写记忆后调用，保证活跃用户的记忆不过期。
        用 Redis Pipeline 批量操作，一次网络往返刷新全部 key。"""
        ttl = settings.agent_memory_ttl_seconds
        pipe = redis.pipeline()
        for key in (
            self.recent_key,
            self.summary_key,
            self.facts_key,
            self.tool_digests_key,
            self.archive_key,
        ):
            pipe.expire(key, ttl)
        await pipe.execute()

    # ---- 核心读写方法 ----

    async def load_context(self) -> MemoryContext:
        """从 Redis 加载当前用户的完整记忆上下文。
        这是 Agent 每次对话前调用的入口方法：
        1. 读取 summary + facts（用 mget 一次获取）
        2. 读取 recent 消息列表
        3. 读取 tool_digests 列表
        4. 统计 archive 消息数量
        """
        redis = await get_redis()

        # summary 和 facts 用 mget 一次获取，减少网络往返
        summary_raw, facts_raw = await redis.mget(
            self.summary_key,
            self.facts_key,
        )

        # recent 和 tool_digests 是 List 类型，用 lrange 获取全部
        recent_items = await redis.lrange(self.recent_key, 0, -1)
        tool_digest_items = await redis.lrange(self.tool_digests_key, 0, -1)
        archive_count = await redis.llen(self.archive_key)

        # 安全解析 JSON（容错：损坏的数据返回空）
        summary_payload = _safe_load_json(summary_raw, {})
        facts_payload = normalize_facts(_safe_load_json(facts_raw, {}))

        recent_messages = [_safe_load_json(item, {}) for item in recent_items]
        tool_digests = [_safe_load_json(item, {}) for item in tool_digest_items]

        # 构建 SummaryState 对象
        summary = SummaryState(
            text=str(summary_payload.get("text", "")),
            updated_at=summary_payload.get("updated_at"),
            archive_cursor=int(summary_payload.get("archive_cursor", 0) or 0),
        )

        # 刷新 TTL（每次读取也续期）
        await self._touch_all(redis)
        # 过滤掉空字典（JSON 解析失败产生的默认值）
        return MemoryContext(
            recent_messages=[msg for msg in recent_messages if msg],
            summary=summary,
            facts=facts_payload,
            tool_digests=[digest for digest in tool_digests if digest],
            archive_count=archive_count,
        )

    async def append_turn(
        self,
        user_message: str,
        assistant_message: str,
        tool_digests: list[dict[str, Any]],
        facts: dict[str, Any],
    ) -> MemoryContext:
        """写入一轮对话到记忆存储。
        步骤：
        1. 将用户消息和助手消息分别追加到 recent 列表（rpush）
        2. 如果 recent 超出滑动窗口，将最早的消息弹出并归档到 archive（lpop + rpush）
        3. 追加工具调用摘要，裁剪到最近 N 条
        4. 更新 facts JSON
        5. 刷新 TTL

        返回更新后的完整 MemoryContext。
        """
        redis = await get_redis()

        # 构造两条消息记录（用户 + 助手），各自带唯一 message_id
        new_items = [
            {
                "message_id": f"user-{utc_now_iso()}",
                "role": "user",
                "content": user_message,
                "created_at": utc_now_iso(),
            },
            {
                "message_id": f"assistant-{utc_now_iso()}",
                "role": "assistant",
                "content": assistant_message,
                "created_at": utc_now_iso(),
            },
        ]

        # 追加到 recent 列表末尾
        for item in new_items:
            await redis.rpush(self.recent_key, json.dumps(item, ensure_ascii=False))

        # ---- 滑动窗口管理 ----
        # 检查 recent 列表长度是否超出窗口大小
        recent_len = await redis.llen(self.recent_key)
        overflow = max(0, recent_len - settings.agent_recent_window)
        # 将超出的消息从 recent 头部弹出，反手追加到 archive 尾部
        for _ in range(overflow):
            oldest = await redis.lpop(self.recent_key)
            if oldest:
                await redis.rpush(self.archive_key, oldest)

        # ---- 工具摘要更新 ----
        if tool_digests:
            for digest in tool_digests:
                await redis.rpush(
                    self.tool_digests_key,
                    json.dumps(digest, ensure_ascii=False),
                )
            # 裁剪到最近 N 条（保留尾部的最新记录）
            await redis.ltrim(
                self.tool_digests_key,
                -settings.agent_tool_digest_limit,
                -1,
            )

        # ---- Facts 持久化 ----
        await redis.set(
            self.facts_key,
            json.dumps(normalize_facts(facts), ensure_ascii=False),
        )

        await self._touch_all(redis)
        return await self.load_context()

    # ---- 摘要保存 ----

    async def save_summary(self, text: str, archive_cursor: int) -> None:
        """保存 LLM 生成的对话摘要到 Redis。
        archive_cursor 记录已压缩到摘要中的 archive 消息位置，
        下次生成摘要时只需要处理 cursor 之后的新消息。"""
        redis = await get_redis()
        payload = {
            "text": text,
            "updated_at": utc_now_iso(),
            "archive_cursor": archive_cursor,
        }
        await redis.set(self.summary_key, json.dumps(payload, ensure_ascii=False))
        await self._touch_all(redis)

    # ---- Archive 读取方法 ----

    async def load_archive_slice(self, start: int, stop: int = -1) -> list[dict[str, Any]]:
        """读取 archive 列表的一个切片区间。
        使用 Redis lrange（类似 Python 切片），start/stop 支持负索引。"""
        redis = await get_redis()
        raw_items = await redis.lrange(self.archive_key, start, stop)
        await self._touch_all(redis)
        return [item for item in (_safe_load_json(raw, {}) for raw in raw_items) if item]

    async def load_archive_tail(self, limit: int) -> list[dict[str, Any]]:
        """读取 archive 列表尾部的最近 N 条消息。
        用于记忆召回时只扫描最近的归档消息（性能和相关性折中）。"""
        if limit <= 0:
            return []
        return await self.load_archive_slice(-limit, -1)

    # ---- 对话历史加载（供前端显示） ----

    async def load_history(self, limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
        """加载对话历史，供前端显示或 API 查询。
        策略：
        - 优先返回 recent 消息（最新的在尾部）
        - 如果 recent 不够 limit，从 archive 尾部补足
        - limit=None 时返回全部历史
        返回：(消息列表, 总消息数)
        """
        context = await self.load_context()
        recent = context.recent_messages
        total = context.archive_count + len(recent)

        if limit is None or limit <= 0:
            # 不限制 → 返回全部 archive + recent
            archive_messages = await self.load_archive_slice(0, -1)
            return archive_messages + recent, total

        if len(recent) >= limit:
            # recent 已经够 limit 了，直接截取尾部
            return recent[-limit:], total

        # recent 不够，从 archive 尾部补足差额
        needed = max(0, limit - len(recent))
        archive_messages = await self.load_archive_tail(needed)
        return archive_messages + recent, total

    # ---- 记忆召回 ----

    async def retrieve_candidates(
        self,
        query: str,
        context: MemoryContext,
    ) -> list[MemorySnippet]:
        """记忆召回：从 archive、tool_digests、facts 中检索与当前 query 相关的记忆片段。
        三路召回策略：
        1. 扫描 archive 尾部 N 条消息（由配置控制扫描范围）
        2. 扫描最近的 tool_digests
        3. 遍历 facts 中的每条记录
        每条候选用 _score_candidate 打分（关键词重叠 + 实体重叠 + 时间衰减），
        按分数降序排列，返回 Top K（agent_retrieval_preselect）给 LLM 精排。
        """
        candidates: list[MemorySnippet] = []

        # 从 query 中提取关键词 token 和实体
        query_tokens = _tokenize(query)
        query_entities = set(extract_entities_from_text(query))

        # ---- 第一路：archive 召回 ----
        # 只扫描尾部 N 条，平衡召回覆盖率和性能（Redis lrange 是 O(S+N)，S 为 offset）
        archive_items = await self.load_archive_tail(settings.agent_archive_scan_limit)
        total_archive = len(archive_items) or 1  # 避免除零
        for idx, item in enumerate(archive_items, start=1):
            text = str(item.get("content") or "").strip()
            if not text:
                continue
            # recency_bonus = idx / total_archive：越新的消息获得越高的时间加分
            score = self._score_candidate(
                query_tokens=query_tokens,
                query_entities=query_entities,
                text=text,
                recency_bonus=idx / total_archive,
            )
            if score > 0:
                candidates.append(
                    MemorySnippet(
                        source="archive",
                        text=text,
                        score=score,
                        created_at=item.get("created_at"),
                    )
                )

        # ---- 第二路：tool_digest 召回 ----
        # 工具摘要固定给 0.9 的时间加分（比 archive 高，因为工具调用信息更结构化、更关键）
        for digest in context.tool_digests:
            text = _normalize_text(
                f"Tool {digest.get('tool_name')}: "
                f"input={digest.get('input_digest', '')}; "
                f"output={digest.get('output_digest', '')}",
                limit=480,
            )
            score = self._score_candidate(
                query_tokens=query_tokens,
                query_entities=query_entities,
                text=text,
                recency_bonus=0.9,
            )
            if score > 0:
                candidates.append(
                    MemorySnippet(
                        source="tool_digest",
                        text=text,
                        score=score,
                        created_at=digest.get("created_at"),
                    )
                )

        # ---- 第三路：facts 召回 ----
        # facts 中的 task_goal、preferences、entities、open_loops 分别参与召回
        for fact_snippet in self._build_fact_snippets(context.facts):
            score = self._score_candidate(
                query_tokens=query_tokens,
                query_entities=query_entities,
                text=fact_snippet.text,
                recency_bonus=0.7,  # 结构化事实的时间加分稍低（偏长期记忆）
            )
            if score > 0:
                fact_snippet.score = score
                candidates.append(fact_snippet)

        # 按分数降序排序，返回 Top K 给 LLM 精排
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[: settings.agent_retrieval_preselect]

    # ---- 记忆清理 ----

    async def clear(self) -> None:
        """清空当前用户的所有记忆（删除全部 5 个 Redis Key）。"""
        redis = await get_redis()
        await redis.delete(
            self.recent_key,
            self.summary_key,
            self.facts_key,
            self.tool_digests_key,
            self.archive_key,
        )

    # ---- 辅助方法 ----

    @staticmethod
    def _build_fact_snippets(facts: dict[str, Any]) -> list[MemorySnippet]:
        """将 facts 字典展开为 MemorySnippet 列表，供召回打分。
        task_goal 作为一条，preferences/entities/open_loops 逐条展开。"""
        snippets: list[MemorySnippet] = []
        task_goal = str(facts.get("task_goal") or "").strip()
        if task_goal:
            snippets.append(MemorySnippet(source="fact", text=f"Task goal: {task_goal}"))
        for label, key in (
            ("Preference", "preferences"),
            ("Entity", "entities"),
            ("Open loop", "open_loops"),
        ):
            for value in facts.get(key) or []:
                snippets.append(MemorySnippet(source="fact", text=f"{label}: {value}"))
        return snippets

    @staticmethod
    def _score_candidate(
        query_tokens: set[str],
        query_entities: set[str],
        text: str,
        recency_bonus: float,
    ) -> float:
        """计算候选记忆片段的召回相关性分数。
        评分公式：分数 = 普通词重叠数 × 2 + 实体重叠数 × 3 + 时间衰减加分 + 追问加分
        设计理由：
        - 实体重叠权重更高（×3 > ×2），因为实体匹配是更强的相关性信号
        - 时间衰减加分由 recency_bonus 决定（越新越高）
        - 追问检测额外 +0.5（如果候选片段包含追问关键词，说明更可能是待解决的问题）
        """
        if not text:
            return 0.0

        candidate_tokens = _tokenize(text)
        # 普通词重叠数
        overlap = len(query_tokens & candidate_tokens)
        # 实体重叠数（候选的 tokens 和 query 的实体求交集）
        entity_overlap = len(query_entities & candidate_tokens)

        score = overlap * 2.0 + entity_overlap * 3.0 + recency_bonus
        if looks_like_follow_up(text):
            score += 0.5  # 包含追问关键词的片段加分
        return score


# ============================================================================
# 错误日志
# ============================================================================


async def log_memory_load_failure(user_id: int, error: Exception) -> None:
    """记录记忆加载失败的日志。
    这是一个温和的错误处理——记忆加载失败不阻塞 Agent 主流程，
    只是打一条 warn 日志，Agent 会在无历史的情况下继续工作。"""
    logger.warning("failed to load memory for user {}: {}", user_id, error)
