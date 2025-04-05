import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from app.api.routes import router as api_router
import concurrent.futures

# 根应用配置
app = FastAPI(
    title="Blast Player Guesser",
    description="帮助用户更高效地参与Blast.tv的猜测游戏",
    version="1.0.0"
)

# 添加启动事件，设置适当的并发限制和任务配置
@app.on_event("startup")
async def startup_event():
    # 设置更大的任务队列大小，以适应WebSocket连接
    import asyncio
    loop = asyncio.get_event_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=20))

app.include_router(api_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 添加WebSocket端点
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    from app.services.game_service import GameService
    
    try:
        await websocket.accept()
        print(f"WebSocket连接已接受 - 房间: {room_id}")
        
        # 将此WebSocket添加到给定房间的连接列表中
        if not hasattr(GameService, 'ws_connections'):
            GameService.ws_connections = {}
        
        if room_id not in GameService.ws_connections:
            GameService.ws_connections[room_id] = []
        GameService.ws_connections[room_id].append(websocket)
        print(f"当前房间 {room_id} 的连接数: {len(GameService.ws_connections[room_id])}")
        
        # 获取当前游戏状态并发送初始状态
        client = await GameService.get_client(room_id)
        if client:
            remaining_guesses = 8 - len(client.guess_results) if client.current_game_phase == 'game' else 8
            
            initial_state = {
                "type": "INITIAL_STATE",
                "game_phase": client.current_game_phase,
                "best_of": client.best_of,
                "player_wins": client.player_wins,
                "required_wins": client._calculate_required_wins(client.best_of),
                "remaining_guesses": remaining_guesses
            }
            print(f"发送初始状态: {initial_state}")
            await websocket.send_json(initial_state)
        
        # 保持连接打开，等待断开
        while True:
            data = await websocket.receive_text()
            # 可以添加心跳响应
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        print(f"WebSocket连接已断开 - 房间: {room_id}")
        # 客户端断开连接，从连接列表中移除
        if hasattr(GameService, 'ws_connections') and room_id in GameService.ws_connections:
            try:
                GameService.ws_connections[room_id].remove(websocket)
                print(f"已移除断开的连接，当前房间 {room_id} 的连接数: {len(GameService.ws_connections[room_id])}")
            except ValueError:
                pass
    except Exception as e:
        print(f"WebSocket处理错误: {str(e)}")
        traceback.print_exc()