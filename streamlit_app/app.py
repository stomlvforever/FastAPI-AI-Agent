import streamlit as st
import httpx
import json
import time

# 配置 API 地址
API_BASE = "http://127.0.0.1:8000/api/v1"

st.set_page_config(page_title="Ops Copilot 面板", layout="wide")

# 1. 简单的会话状态存储
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= 侧边栏：登录 =================
with st.sidebar:
    st.title("🔐 管理员登录")
    if not st.session_state.token:
        with st.form("login_form"):
            username = st.text_input("邮箱 (Admin)")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录")
            
            if submitted:
                # 调用后端登录接口
                resp = httpx.post(
                    f"{API_BASE}/auth/login",
                    data={"username": username, "password": password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("登录失败，请检查账号密码或权限。")
    else:
        st.success("✅ 已登录")
        if st.button("退出登录"):
            st.session_state.token = None
            st.session_state.messages = []
            st.rerun()
        
        if st.button("🗑️ 清空历史对话"):
            # 如果你有的话也可以调后端的 clear history 接口
            st.session_state.messages = []
            st.rerun()


# ================= 主界面：Agent 聊天 =================
st.title("🤖 Ops Copilot 智能运营助手")

if not st.session_state.token:
    st.info("👈 请先在左侧侧边栏登录管理员账号。")
    st.stop()

# 渲染已有对话历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 聊天输入框
if prompt := st.chat_input("问我任何关于系统、用户或文章的问题..."):
    # 1. 显示用户自己的消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 与 FastAPI Agent 交互（使用 SSE 流式输出）
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # 发起流式请求
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            payload = {"message": prompt}
            
            with httpx.stream("POST", f"{API_BASE}/agent/chat/stream", headers=headers, json=payload, timeout=120.0) as response:
                if response.status_code != 200:
                    st.error(f"Agent 调用失败：{response.text}")
                else:
                    # 逐行读取 SSE 数据，节流渲染防止长文本卡顿
                    last_render = 0
                    RENDER_INTERVAL = 0.08  # 每 80ms 最多渲染一次

                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data_json = json.loads(data_str)
                                chunk = data_json.get("content", "")
                                full_response += chunk

                                # 节流：距离上次渲染超过 80ms 才刷新 UI
                                now = time.time()
                                if now - last_render > RENDER_INTERVAL:
                                    message_placeholder.markdown(full_response + "▌")
                                    last_render = now
                            except json.JSONDecodeError:
                                pass
                    
                    # 结束时去掉光标
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"连接 Agent 失败: {e}")

