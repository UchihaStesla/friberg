from fastapi import HTTPException, WebSocket, WebSocketDisconnect, Depends
from typing import List, Dict, Any, Optional
import json
import asyncio
import os
from app.core.game_client import BlastTvGameClient

class GameService:
    # 存储活动客户端的字典
    active_clients: Dict[str, BlastTvGameClient] = {}
    ws_connections = {}  # 用于存储每个房间的WebSocket连接
    
    @classmethod
    async def get_client(cls, room_id: str) -> BlastTvGameClient:
        """获取或创建游戏客户端"""
        if room_id not in cls.active_clients:
            client = BlastTvGameClient(room_id)
            client.register_handler("all", client.process_game_messages)
            connected = await client.connect()
            if not connected:
                raise HTTPException(status_code=500, detail="无法连接到游戏服务器")
            
            # 启动消息接收器
            await client.start_receiver()
            
            # 注册消息处理器
            client.register_handler("all", client.process_game_messages)
            
            cls.active_clients[room_id] = client
        
        return cls.active_clients[room_id]
    
    @classmethod
    async def close_client(cls, room_id: str) -> bool:
        """关闭并移除客户端"""
        if room_id in cls.active_clients:
            client = cls.active_clients[room_id]
            await client.close()
            del cls.active_clients[room_id]
            return True
        return False
    
    @classmethod
    async def send_manual_guess(cls, room_id: str, player_id: str) -> Dict[str, Any]:
        """发送手动猜测"""
        client = await cls.get_client(room_id)
        
        # 设置猜测状态
        client.guessing = True
        
        # 发送猜测
        result = await client.send_guess(player_id)
        if not result:
            client.guessing = False
            return {"success": False, "message": "发送猜测失败"}
        
        # 等待猜测结果
        max_wait = 15  # 最多等待15秒
        wait_time = 0
        
        # 确保注册适当的处理器
        client.register_handler("GUESS_RESULT", client.handle_guess_result)
        client.register_handler("all", client.process_game_messages)
        
        while client.guessing and wait_time < max_wait:
            await asyncio.sleep(0.5)  # 缩短等待间隔，提高检查频率
            wait_time += 0.5
            
            # 主动处理消息队列中的消息
            if len(client.message_queue) > 0:
                messages = list(client.message_queue)  # 复制队列而不清空
                for msg in messages:
                    if msg.get('type') == 'GUESS_RESULT' or 'players' in msg:
                        await client.handle_guess_result(msg)
        
        if wait_time >= max_wait:
            client.guessing = False
            return {"success": False, "message": "等待猜测结果超时"}
        
        # 检查猜测结果
        if client.guess_success:
            return {"success": True, "message": "猜测正确！"}
        
        # 返回当前猜测结果
        return {
            "success": True,
            "result": client.current_guess_result,
            "message": "猜测已处理"
        }
    
    @classmethod
    async def start_auto_guessing(cls, room_id: str, max_guesses: int = 8) -> Dict[str, Any]:
        """开始自动猜测"""
        client = await cls.get_client(room_id)
        
        # 启动自动猜测流程
        success = await client.start_auto_guessing(max_guesses)
        
        if success:
            return {"success": True, "message": "自动猜测成功！找到了正确答案。"}
        else:
            return {"success": False, "message": "自动猜测未能找到正确答案。"}
    
    
    
    @classmethod
    async def get_recommendations(cls, room_id: str, constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取推荐玩家列表以及游戏元数据"""
        client = await cls.get_client(room_id)
        
        try:
            # 加载玩家数据
            with open("players_with_entropy.json", 'r', encoding='utf-8') as f:
                all_players = json.load(f)
            
            # 创建已猜测玩家ID集合，用于排除
            guessed_player_ids = set()
            for result in client.guess_results:
                if 'id' in result:
                    guessed_player_ids.add(result['id'])
            
            # 先排除已猜测的玩家
            available_players = [p for p in all_players if p.get('id') not in guessed_player_ids]
            print(f"排除已猜测的 {len(guessed_player_ids)} 名玩家后，剩余 {len(available_players)} 名可推荐玩家")
            
            # 再应用约束条件过滤
            if constraints:
                filtered_players = client.filter_players(available_players, constraints)
            else:
                # 使用客户端内部累积的约束条件
                combined_constraints = {}

                # 从以往猜测中提取约束条件
                combined_constraints = client.accumulated_constraints.copy()  # 使用累积的约束条件

                # 从当前轮次添加额外约束条件
                current_round_constraints = {}
                for result in client.guess_results:
                    if 'constraints' in result:
                        # 使用客户端的merge_constraints方法进行智能合并
                        current_round_constraints = client.merge_constraints(
                            current_round_constraints,
                            result['constraints']
                        )

                # 合并当前轮次和累积的约束条件
                combined_constraints = client.merge_constraints(
                    combined_constraints,
                    current_round_constraints
                )

                filtered_players = client.filter_players(available_players, combined_constraints)
            
            # 按熵值排序
            filtered_players.sort(key=lambda p: p.get('entropy_value', 0), reverse=True)
            
            # 如果过滤后没有玩家，尝试放宽约束条件
            if not filtered_players and available_players:
                print("严格约束条件下没有玩家匹配，返回未经过滤的可用玩家")
                available_players.sort(key=lambda p: p.get('entropy_value', 0), reverse=True)
                filtered_players = available_players[:20]  # 返回熵值最高的20个
            
            # 转换字段名称以匹配Pydantic模型
            transformed_players = []
            for player in filtered_players[:20]:  # 仅返回前20个
                transformed_players.append({
                    'player_id': player.get('id', ''),
                    'first_name': player.get('firstName', ''),
                    'last_name': player.get('lastName', ''),
                    'nickname': player.get('nickname', ''),
                    'nationality': player.get('nationality', ''),
                    'team': player.get('team', {}).get('name') if isinstance(player.get('team'), dict) else player.get('team'),
                    'age': player.get('age'),
                    'role': player.get('role', ''),
                    'is_retired': player.get('isRetired', False),
                    'entropy_value': player.get('entropy_value'),
                    'image_url': player.get('image_url', '')
                })
            
            # 添加游戏元数据
            game_metadata = {
                'best_of': getattr(client, 'best_of', 'best_of_3'),
                'current_wins': getattr(client, 'player_wins', 0),
                'required_wins': client._calculate_required_wins(getattr(client, 'best_of', 'best_of_3')),
                'current_phase': client.current_game_phase,
                'remaining_guesses': 8 - len(client.guess_results) if client.current_game_phase == 'game' else 8
            }
            
            return {
                'recommendations': transformed_players, 
                'game_metadata': game_metadata,
                'constraints': combined_constraints if not constraints else constraints
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"获取推荐失败: {str(e)}")
    
    @classmethod
    async def broadcast_update(cls, room_id: str, update: Dict[str, Any]):
        """向房间内所有连接的WebSocket客户端广播更新"""
        if not hasattr(cls, 'ws_connections') or not cls.ws_connections:
            cls.ws_connections = {}
            print("⚠️ WebSocket连接列表尚未初始化")
            return
        
        if "player_wins" not in update and room_id in cls.active_clients:
            client = cls.active_clients[room_id]
            update["player_wins"] = getattr(client, 'player_wins', 0)
        
        if room_id in cls.ws_connections and cls.ws_connections[room_id]:
            print(f"📣 广播消息类型: {update.get('type')} 到 {len(cls.ws_connections[room_id])} 个客户端")
            
            # 向所有连接的客户端发送消息
            for i, websocket in list(enumerate(cls.ws_connections[room_id])):
                try:
                    await websocket.send_json(update)
                except Exception as e:
                    print(f"⚠️ 向客户端 {i} 发送消息失败: {str(e)}")
                    # 标记断开连接的客户端
                    try:
                        cls.ws_connections[room_id].remove(websocket)
                    except:
                        pass
        else:
            print(f"⚠️ 无法广播消息: 房间 {room_id} 不存在或无WebSocket连接")