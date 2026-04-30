"""WebSocket 示例接口。

提供基础实时通信示例，用于验证 WebSocket 连接和消息回显。"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# 导入：APIRouter（路由）、WebSocket（连接对象）、WebSocketDisconnect（断开异常）

router = APIRouter()
# 创建路由实例，返回：APIRouter 对象

@router.websocket("/ws/echo")
# 装饰器：注册 WebSocket 端点，路径是 /ws/echo
# 返回：无（装饰器不返回，只是注册）

async def websocket_echo(websocket: WebSocket):
# 定义异步函数，参数 websocket 是连接对象
# 返回：None（函数结束时）

    await websocket.accept()
    # 接受客户端的 WebSocket 连接请求
    # 返回：None（只是建立连接）
    
    try:
        while True:
        # 无限循环，保持连接活跃
        # 返回：无（循环本身不返回）
        
            data = await websocket.receive_text()
            # 等待并接收客户端发来的文本消息（阻塞式）
            # 返回：str（客户端发送的文本内容）
            
            await websocket.send_text(f"echo: {data}")
            # 发送消息回客户端，格式是 "echo: 原消息"
            # 返回：None（只是发送）
            
    except WebSocketDisconnect:
    # 捕获客户端断开连接的异常
    # 返回：无（异常处理）
    
        return
        # 退出函数，结束连接
        # 返回：None

