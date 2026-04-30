# Ops Copilot 实现总结

## 📁 项目结构

```
app/agent/ops_copilot/
├── __init__.py                      # 包入口
├── tools.py                         # ✅ Tool 定义和执行器
├── service.py                       # ✅ Agent 核心服务（对话、历史、多轮上下文）
└── (待实现) config.py              # OpenAI 配置和连接池

app/api/v1/routes/
└── agent.py                         # ✅ API 路由（3 个端点）

app/schemas/
└── agent.py                         # ✅ 请求/响应数据模型

app/agent/
├── ops_copilot_prompt.md            # ✅ Prompt 模板和 Tool Schema 完整参考
└── ops_copilot_prompt.md            # ✅ 使用示例和最佳实践
```

---

## 🔧 核心模块说明

### 1. `tools.py` - 工具定义和执行器

**关键类**:
- `ToolParameter`: 工具参数定义
- `ToolDefinition`: 工具完整定义
- `ToolExecutor`: 工具执行器（12 个工具方法）
- `get_tools_schema()`: 生成 OpenAI Function Calling Schema

**12 个工具**（分为 3 类）:

**查询工具 (Query)**:
1. `query_users` - 查询用户列表，支持过滤
2. `query_articles` - 查询文章列表，支持排序
3. `get_user_stats` - 用户统计数据（总数、活跃、注册趋势）
4. `get_article_stats` - 文章统计数据（热门、标签分布）
5. `get_system_health` - 系统健康状态
6. `get_request_metrics` - 请求性能指标

**操作工具 (Operation - 需要确认)**:
7. `ban_user` - 禁用用户账户
8. `unban_user` - 解禁用户
9. `reset_user_password` - 重置用户密码
10. `promote_user_to_admin` - 提升为管理员
11. `delete_article` - 删除文章
12. `send_bulk_email` - 批量发邮件（异步）

**权限检查**:
```python
# ToolExecutor.__init__() 中检查
if current_user.role != "admin":
    raise HTTPException(status_code=403, detail="Only admins can use Ops Copilot")
```

---

### 2. `service.py` - Agent 核心服务

**关键类**:
- `OpsCopilotService`: Agent 业务逻辑
- `AgentStreamResponse`: SSE 流式响应包装

**核心方法**:

#### `chat(user_message: str) -> AsyncGenerator[str, None]`
```
工作流：
1. 加载对话历史（Redis）
2. 构建消息列表 [system_prompt, ...history, user_message]
3. 调用 OpenAI API (Function Calling)
4. 解析响应，如果有 tool_calls:
   - 执行每个工具，收集结果
   - 将结果追加到消息列表
   - 再次调用 OpenAI 生成最终回复
5. 流式返回所有输出
6. 保存对话历史到 Redis (TTL 24h)
```

#### 会话管理
```python
# 会话 ID 格式：agent_session:{user_id}
session_id = f"agent_session:{current_user.id}"

# Redis 中以 JSON 格式存储历史
{
  "role": "user/assistant/tool",
  "content": "...",
  "timestamp": "ISO8601"
}
```

---

### 3. `routes/agent.py` - API 路由

**3 个端点**:

#### 1. `POST /api/v1/agent/chat` (非流式)
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "最近有什么可疑用户吗？"}'

响应:
{
  "content": "我查到了...",
  "tool_calls": [...]
}
```

#### 2. `POST /api/v1/agent/chat/stream` (流式, SSE)
```bash
# 前端使用 EventSource 接收
const eventSource = new EventSource('/api/v1/agent/chat/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.content);  // 实时显示 Agent 推理过程
};
```

#### 3. `GET /api/v1/agent/history`
```bash
curl http://localhost:8000/api/v1/agent/history?limit=20 \
  -H "Authorization: Bearer <token>"

响应:
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    ...
  ],
  "total": 42
}
```

#### 4. `DELETE /api/v1/agent/history`
```bash
curl -X DELETE http://localhost:8000/api/v1/agent/history \
  -H "Authorization: Bearer <token>"

响应:
{
  "success": true,
  "message": "Conversation history cleared"
}
```

---

## 🚀 集成步骤（待完成）

### Step 1: 安装依赖
```bash
pip install openai>=1.0.0  # 最新版本的 OpenAI Python SDK
```

### Step 2: 配置 OpenAI API

在 `.env` 中添加：
```dotenv
# OpenAI 配置
openai_api_key=sk-xxxxxxxx
openai_model=gpt-4  # 或 gpt-4-turbo, gpt-3.5-turbo
openai_api_base=https://api.openai.com/v1  # 可选，用于代理或其他端点
```

### Step 3: 补全 `service.py` 中的 `_call_openai_api()` 方法

```python
import openai

async def _call_openai_api(self, messages: list[dict]) -> dict:
    """真实调用 OpenAI API"""
    openai.api_key = settings.openai_api_key
    
    response = openai.ChatCompletion.create(
        model=settings.openai_model,
        messages=messages,
        tools=get_tools_schema(),
        tool_choice="auto",  # 自动决定是否调用工具
        temperature=0.7,
        max_tokens=2000,
    )
    
    assistant_message = response.choices[0].message
    
    return {
        "content": assistant_message.get("content", ""),
        "tool_calls": assistant_message.get("tool_calls", [])
    }
```

### Step 4: 更新 `requirements.txt`

```
openai>=1.0.0
```

### Step 5: 单元测试

```python
# tests/test_ops_copilot.py
import pytest
from app.agent.ops_copilot.service import OpsCopilotService

@pytest.mark.asyncio
async def test_agent_query_users(admin_user, session):
    """测试 Agent 查询用户"""
    service = OpsCopilotService(session, admin_user)
    
    # 模拟用户消息
    async for chunk in service.chat("有多少个活跃用户？"):
        print(chunk)  # 应该包含用户统计信息
```

---

## 📊 使用场景示例

### 场景 1: 快速审查用户

**用户**: "给我列出最近 7 天注册的用户，有没有可疑账户？"

**Agent 流程**:
1. 调用 `query_users(skip=0, limit=100)`
2. 根据邮箱、用户名、IP 等启发式规则识别可疑账户
3. 提示用户可疑信息
4. 等待用户确认是否执行禁用

---

### 场景 2: 内容质量监控

**用户**: "分析一下最近一周的内容表现，有优化空间吗？"

**Agent 流程**:
1. 调用 `get_article_stats(days=7, top_n=10)`
2. 调用 `get_user_stats(days=7)`
3. 计算：人均发文数、平均文章长度、评论参与度、热门话题分布
4. 根据数据给出运营建议
5. 可选：调用 `send_bulk_email()` 向活跃作者发送鼓励

---

### 场景 3: 紧急事件处理

**用户**: "用户 #2847 有严重违规，帮我禁用他的账户"

**Agent 流程**:
1. 确认用户 ID
2. 调用 `ban_user(user_id=2847, reason="严重违规")`
3. 系统自动发送通知邮件给该用户
4. 返回操作结果和审计日志

---

## 🔐 安全考虑

### 1. 权限校验
- ✅ 所有 Agent 接口都需要 `AdminUser` 依赖
- ✅ 工具执行前再次检查权限
- ✅ 所有操作记录审计日志（待实现）

### 2. 操作确认
- ✅ 危险操作（删除、禁用）需要显式确认
- ✅ Agent 建议执行，用户决定是否实施

### 3. Token 安全
- ✅ Access Token 被正确校验（type=="access"）
- ✅ Refresh Token 无法冒充 Access Token

### 4. 数据隐私
- ✅ 对话历史存储在 Redis，非持久化
- ✅ 24 小时自动过期
- ✅ 用户只能看到自己的历史

---

## 📈 面试亮点

### 技术栈
✅ OpenAI Function Calling（2024年企业级标准）
✅ 多轮对话上下文管理（会话状态）
✅ 流式输出 (SSE) 实时交互体验
✅ Redis 分布式缓存
✅ 权限检查和安全边界
✅ 异步任务和后台处理

### 架构设计
✅ 与后端 Service 层深度集成，不是简单的 API 调用者
✅ 工具执行器 (ToolExecutor) 清晰的职责分离
✅ 流式响应让用户体验更好
✅ 支持多用户隔离会话

### 企业级特性
✅ 审计日志（待实现）
✅ 速率限制（可选）
✅ 错误恢复和重试机制（待实现）
✅ 监控和告警（可集成到 /metrics）

---

## ⚠️ 已知限制 & 待优化

1. **OpenAI API 调用**
   - 当前 `_call_openai_api()` 是模拟实现
   - 需要真实调用 OpenAI API
   - 可能产生 API 费用

2. **工具结果精度**
   - 当前查询工具返回内存数据（简单实现）
   - 生产环境应该用 SQL 聚合查询优化性能

3. **Agent 推理能力**
   - 依赖 GPT-4 或更强的模型
   - 如果用 GPT-3.5-turbo，推理能力可能不足

4. **审计日志**
   - 所有管理操作应该记录到数据库
   - 待实现：`create_audit_log(user_id, action, details)`

5. **速率限制**
   - 可以添加到 Agent 路由防止滥用
   - 如：每分钟最多 10 条消息

---

## 🎯 下一步行动

1. **集成 OpenAI API**
   - 补全 `_call_openai_api()` 实现
   - 配置 API Key 和模型

2. **补全工具实现**
   - 优化查询性能（SQL 聚合）
   - 添加更多工具（权限、日志等）

3. **增强 Agent 能力**
   - 改进提示词（用专业的 prompt engineering）
   - 添加长期记忆（跨会话的知识积累）
   - 改进 Tool Use 选择策略

4. **生产部署**
   - 添加审计日志
   - 配置速率限制
   - 性能测试和优化
   - 监控和告警

5. **前端集成**
   - Streamlit 管理后台
   - 实时流式对话界面
   - 操作确认对话框

---

## 参考链接

- [OpenAI Function Calling API](https://platform.openai.com/docs/guides/function-calling)
- [Prompt Engineering Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/streaming/)
- [Redis Async Client](https://redis-py.readthedocs.io/en/stable/topics/client_side_caching.html)
