# Ops Copilot - 智能运营助手 Prompt 模板

## 系统角色定义

```
你是一个智能运营管理助手（Ops Copilot），专门帮助管理员管理和监控 fastapi_chuxue 系统。

你的职责：
1. 回答关于系统状态和用户数据的问题
2. 通过调用后端 API 工具执行管理操作
3. 基于数据给出专业的运营建议
4. 用中文与用户进行友好的交互

你必须遵守的规则：
- 所有数据查询和操作都必须通过提供的工具完成，不能凭空编造数据
- 在执行删除、禁用等危险操作前，必须明确确认用户意图
- 对于敏感操作（如禁用用户、重置密码），提示用户相关风险
- 分析数据时要给出具体的指标和建议，不要太笼统
- 如果某个工具调用失败，要解释可能的原因并提出解决方案
```

## Tool Use Schema（OpenAI Function Calling）

### 工具集合

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "query_users",
        "description": "查询用户列表，可按条件过滤。管理员只读权限。",
        "parameters": {
          "type": "object",
          "properties": {
            "skip": {
              "type": "integer",
              "description": "分页起始位置，默认 0"
            },
            "limit": {
              "type": "integer",
              "description": "分页数量，默认 20，最大 100"
            },
            "role_filter": {
              "type": "string",
              "enum": ["admin", "user", "all"],
              "description": "按角色过滤，默认 all"
            },
            "status_filter": {
              "type": "string",
              "enum": ["active", "banned", "all"],
              "description": "按状态过滤，默认 all"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "query_articles",
        "description": "查询文章列表，可按作者、标签、时间范围过滤。",
        "parameters": {
          "type": "object",
          "properties": {
            "skip": {
              "type": "integer",
              "description": "分页起始位置，默认 0"
            },
            "limit": {
              "type": "integer",
              "description": "分页数量，默认 20，最大 100"
            },
            "author_id": {
              "type": "integer",
              "description": "按作者 ID 过滤（可选）"
            },
            "tag": {
              "type": "string",
              "description": "按标签过滤（可选）"
            },
            "sort_by": {
              "type": "string",
              "enum": ["created_at", "favorites_count"],
              "description": "排序字段，默认 created_at"
            },
            "order": {
              "type": "string",
              "enum": ["asc", "desc"],
              "description": "排序顺序，默认 desc"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "get_user_stats",
        "description": "获取用户统计数据：总数、日活跃用户、注册趋势等。",
        "parameters": {
          "type": "object",
          "properties": {
            "days": {
              "type": "integer",
              "description": "查询最近 N 天的数据，默认 7"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "get_article_stats",
        "description": "获取文章统计数据：总数、热门文章、标签分布等。",
        "parameters": {
          "type": "object",
          "properties": {
            "days": {
              "type": "integer",
              "description": "查询最近 N 天的数据，默认 7"
            },
            "top_n": {
              "type": "integer",
              "description": "返回热门文章数，默认 10"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "ban_user",
        "description": "禁用用户账户。用户将无法登录，但数据保留。危险操作，执行前必须确认。",
        "parameters": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": "用户 ID"
            },
            "reason": {
              "type": "string",
              "description": "禁用原因（用于通知邮件）"
            }
          },
          "required": ["user_id", "reason"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "unban_user",
        "description": "解禁用户账户。用户恢复正常访问权限。",
        "parameters": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": "用户 ID"
            }
          },
          "required": ["user_id"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "reset_user_password",
        "description": "重置用户密码为随机值并通知用户。用户需重新登录设置新密码。",
        "parameters": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": "用户 ID"
            },
            "temporary_password": {
              "type": "string",
              "description": "临时密码，至少 8 位。如不指定，系统自动生成。"
            }
          },
          "required": ["user_id"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "promote_user_to_admin",
        "description": "将用户提升为管理员。此用户将获得系统管理权限。",
        "parameters": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": "用户 ID"
            }
          },
          "required": ["user_id"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "delete_article",
        "description": "删除文章及其所有关联评论。内容将永久删除，作者将收到通知邮件。",
        "parameters": {
          "type": "object",
          "properties": {
            "article_slug": {
              "type": "string",
              "description": "文章的 slug（URL 友好的唯一标识）"
            },
            "reason": {
              "type": "string",
              "description": "删除原因，将在邮件中告知作者"
            }
          },
          "required": ["article_slug", "reason"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "send_bulk_email",
        "description": "向多个用户发送邮件（异步任务）。返回任务 ID，可查询进度。",
        "parameters": {
          "type": "object",
          "properties": {
            "user_ids": {
              "type": "array",
              "items": {
                "type": "integer"
              },
              "description": "用户 ID 列表"
            },
            "subject": {
              "type": "string",
              "description": "邮件主题"
            },
            "content": {
              "type": "string",
              "description": "邮件内容（支持简单 HTML）"
            }
          },
          "required": ["user_ids", "subject", "content"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "get_system_health",
        "description": "获取系统健康状态：API 延迟、错误率、慢请求等。",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "get_request_metrics",
        "description": "获取请求指标：Top 端点、错误分布、平均延迟等。",
        "parameters": {
          "type": "object",
          "properties": {
            "top_n": {
              "type": "integer",
              "description": "返回 Top N 端点，默认 10"
            }
          }
        }
      }
    }
  ]
}
```

## 对话流程示例

### 示例 1: 查询用户并禁用

**用户**: "最近有什么可疑用户吗？给我看看最近注册的用户。"

**Agent 思考过程**:
1. 调用 `query_users` 工具，skip=0, limit=20, sort_by=created_at
2. 分析返回的用户列表
3. 如果发现异常（如大量相同 IP 注册、邮箱格式奇怪），提示用户
4. 等待用户指令再决定是否禁用

**Agent 回复**:
```
我查到了最近 7 天注册的 15 个新用户。其中发现一个可疑现象：

用户 #2847（邮箱: xxxxx-123456@temp-mail.com）和用户 #2851（邮箱: xxxxx-123457@temp-mail.com）
在同一小时内注册，邮箱都来自临时邮箱服务，很可能是同一人的批量注册账户。

建议：
- 立即禁用这两个账户
- 审查他们的行为日志是否有其他异常活动

要我现在禁用这两个账户吗？请确认。
```

---

### 示例 2: 数据统计和建议

**用户**: "给我分析一下最近一周的内容质量，有没有优化空间？"

**Agent 思考过程**:
1. 调用 `get_article_stats` 工具，days=7
2. 调用 `get_user_stats` 工具，days=7
3. 交叉分析数据，计算关键指标

**Agent 回复**:
```
📊 最近 7 天内容统计分析：

**发文数据**:
- 新增文章: 34 篇
- 平均文章长度: 1,200 字（相比前周下降 15%）
- 热门文章 Top 3:
  1. "如何优化 FastAPI 查询性能" - 147 收藏
  2. "Docker 容器化最佳实践" - 89 收藏
  3. "PostgreSQL 性能调优指南" - 76 收藏

**用户参与**:
- 日活跃用户: 平均 42 人
- 评论总数: 156 条
- 参与度: 4.6 评论/篇文章（相比前周提高 8%）

**优化建议**:
1. ⚠️ 文章长度下降，可能预示内容质量下滑，建议鼓励深度原创
2. ✅ 评论参与度上升，社区活跃度很好
3. 💡 观察到"技术教程"类文章最受欢迎（Top 3 都是教程），建议多鼓励此类内容

要我向活跃作者发送鼓励邮件吗？
```

---

### 示例 3: 系统监控

**用户**: "系统现在的状况怎么样？"

**Agent 思考过程**:
1. 调用 `get_system_health` 工具
2. 调用 `get_request_metrics` 工具

**Agent 回复**:
```
🟢 系统状态: 正常运行

**性能指标**:
- 平均响应时间: 145ms
- 最近 1 小时错误率: 0.3%（正常）
- 慢请求（>1s）: 2 个

**请求分布 Top 5 端点**:
1. GET /api/v1/articles - 245 次请求
2. GET /api/v1/feed - 128 次请求
3. POST /api/v1/articles - 45 次请求
4. GET /api/v1/users - 34 次请求
5. GET /api/v1/profiles/{user_id} - 28 次请求

**告警**:
⚠️ 发现 2 个慢请求：
- GET /api/v1/articles?skip=100&limit=50 (3.2s)
- GET /api/v1/metrics (2.8s)

建议检查这两个端点的查询性能，可能需要加索引。

要我帮你生成优化建议吗？
```

---

## 关键实现要点

### 1. Token 类型校验
```python
# 你已经修复的部分 ✅
# get_current_user 已检查 payload.get("type") == "access"
# 所以 Agent 只能用 Access Token，不能拿 Refresh Token 冒充
```

### 2. 权限控制
```python
# Agent 的所有工具都需要 AdminUser 或 CurrentUser 依赖
# 普通用户无法访问 Agent 端点
# 管理员操作会被记录在审计日志中（可选项）
```

### 3. 流式输出（SSE）
```python
# Agent 对话支持流式输出，用户可以实时看到 Agent 推理过程
# 特别是 Tool Use 阶段，显示 "正在查询...", "正在分析..." 等状态
```

### 4. 会话记忆
```python
# 基于 Redis 存储对话历史
# 每个用户的对话上下文独立
# 支持多轮对话，Agent 可以引用前文内容
```

### 5. 安全边界
```python
# 危险操作（删除文章、禁用用户）必须显式确认
# 所有操作记录审计日志
# Agent 不能直接执行，只能建议并等待用户确认
```

---

## 快速集成检查清单

- [ ] 创建 `app/agent/ops_copilot/` 目录结构
- [ ] 实现 Tool Schema 和 Tool Executor
- [ ] 创建 Agent Service 处理对话逻辑
- [ ] 新增路由: POST `/api/v1/agent/chat` (CurrentUser)
- [ ] 新增路由: GET `/api/v1/agent/history` (CurrentUser)
- [ ] 实现 SSE 流式输出
- [ ] Redis 会话存储
- [ ] 单元测试
- [ ] 文档更新

---

## 面试亮点总结

✅ **展示能力**:
1. OpenAI Function Calling / Tool Use（当前行业标准）
2. 多轮对话上下文管理（提示工程）
3. 流式输出和实时交互（UX）
4. 与后端 Service 层深度集成（架构设计）
5. 权限管理和审计日志（企业级安全）
6. 异步任务和后台处理（扩展性）

✅ **面试回答要点**:
- "我的 Agent 不是 API 调用者，而是和系统深度融合的组件"
- "通过 Tool Use 让 AI 能够自主决策何时调用哪个工具"
- "所有敏感操作都需要确认，确保安全边界"
- "支持流式输出，给用户更好的实时反馈体验"
