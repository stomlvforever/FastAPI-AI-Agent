"""Ops Copilot Agent 子包。

本包是 fastapi_chuxue 的 AI Agent 核心模块，聚合三个关键组件：

1. service.py   → OpsCopilotService：Agent 编排服务（记忆加载、OpenAI 调用、工具调度、流式输出）
2. tools.py     → ToolExecutor：30+ 工具函数的定义与执行器（封装后端业务能力为 Function Calling 工具）
3. memory.py    → ConversationMemoryStore：Redis 支持的分层记忆系统（类 MemGPT 的五层记忆架构）

数据流向：
  api/routes/agent.py (HTTP/SSE 端点)
    → OpsCopilotService.chat()
      → ConversationMemoryStore.load_context()     # 加载记忆
      → ConversationMemoryStore.retrieve_candidates() # 记忆召回
      → OpenAI chat.completions.create()            # LLM 调用
      → ToolExecutor._execute_tool()                # 工具调用
      → merge_facts()                               # 更新 facts
      → ConversationMemoryStore.append_turn()        # 写回记忆
      → ConversationMemoryStore.save_summary()       # 条件性摘要

子包导出：无（内部模块由 app/agent/ 上层按需导入，不暴露公共 API）
"""
