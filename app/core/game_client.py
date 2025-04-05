from app.core.util import custom_uuid_implementation
from collections import deque
from typing import Optional, Callable, Deque, Dict, List, Any, Tuple
import json
import asyncio
import websockets
import ssl
import traceback

class BlastTvGameClient:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.uuid = custom_uuid_implementation()
        self.base_url = f"wss://minigames-ws.blast.tv/parties/game/{room_id}"
        self.full_url = f"{self.base_url}?_pk={self.uuid}"
        self.websocket = None
        self.connection_id = None
        self.connected = False
        
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        self.message_queue: Deque[Dict[str, Any]] = deque(maxlen=100)
        self.receiver_task = None
        self.message_handlers = {}
        self.stop_receiving = False
        
        self.guess_results = []
        self.accumulated_constraints = {}
        self.guessing = False
        self.current_guess_result = None
        self.guess_success = False
        self.player_wins = 0
        self.current_game_phase = None
        self.game_complete = False
        self.processed_end_messages = set()
        self.best_of = "best_of_3" 
        self.game_meta = {} 

        try:
            with open("countries.json", 'r', encoding='utf-8') as f:
                self.countries_data = json.load(f)
        except Exception as e:
            print(f"加载国家数据失败: {str(e)}")
            self.countries_data = {}

    async def connect(self, max_retries=3):
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.websocket = await websockets.connect(self.full_url, ssl=self.ssl_context)
                self.connected = True
                print("成功连接到游戏服务器")
                return True
            except Exception as e:
                print(f"连接失败: {str(e)}，重试中...")
                retry_count += 1
                await asyncio.sleep(1)
        print("达到最大重试次数，连接失败")
        return False

    async def player_ready(self):
        if not self.websocket or not self.connected:
            print("错误: 尚未建立WebSocket连接")
            return False
        
        conn_id = self.connection_id if self.connection_id else self.uuid
        
        ready_message = {
            "type": "PLAYER_READY",
            "payload": {
                "connectionId": conn_id
            }
        }
        
        try:
            await self.websocket.send(json.dumps(ready_message))
            print("已发送准备就绪消息")
            return True
        except Exception as e:
            print(f"发送准备消息失败: {str(e)}")
            self.connected = False
            await self.close()
            return False

    async def receive_message(self):
        if not self.websocket or not self.connected:
            return None
            
        try:
            message = await self.websocket.recv()
            return json.loads(message)
        except websockets.exceptions.ConnectionClosed:
            print("连接已关闭")
            self.connected = False
            return None
        except Exception as e:
            print(f"接收消息失败: {str(e)}")
            self.connected = False
            return None

    async def send_guess(self, player_id: str):
        if not self.websocket or not self.connected:
            print("错误: 尚未建立WebSocket连接")
            return False
        
        conn_id = self.connection_id if self.connection_id else self.uuid
        
        guess_message = {
            "type": "GUESS",
            "payload": {
                "playerId": player_id,
                "connectionId": conn_id
            }
        }
        
        try:
            await self.websocket.send(json.dumps(guess_message))
            print(f"已发送猜测消息，目标玩家ID: {player_id}")
            return True
        except Exception as e:
            print(f"发送猜测消息失败: {str(e)}")
            self.connected = False
            await self.close()
            return False

    async def start_receiver(self):
        if not self.websocket or not self.connected:
            print("错误: 尚未建立WebSocket连接")
            return False
        
        if self.receiver_task is not None:
            print("消息接收器已启动")
            return True
            
        self.stop_receiving = False
        self.receiver_task = asyncio.create_task(self._message_receiver())
        print("消息接收器已启动")
        return True

    async def _message_receiver(self):
        """后台消息接收器，持续接收消息并分发处理"""
        try:
            while not self.stop_receiving and self.connected:
                try:
                    message = await self.receive_message()
                    if message:
                        # 增强调试信息，显示更多消息内容
                        msg_type = message.get('type', '未知类型')
                        print(f"接收到消息: {msg_type}")
                        
                        # 对于未知类型的消息，打印更详细的信息便于调试
                        if msg_type == '未知类型':
                            # 安全地打印消息的前100个字符
                            msg_preview = str(message)[:100] + ('...' if len(str(message)) > 100 else '')
                            print(f"未知类型消息内容预览: {msg_preview}")
                            
                            # 检测关键字段，即使没有type字段也能处理
                            if 'phase' in message:
                                print(f"检测到未分类的阶段更新消息: phase={message['phase']}")
                                # 创建处理任务
                                asyncio.create_task(self.process_game_messages(message))
                            elif 'players' in message:
                                print(f"检测到未分类的玩家更新消息，包含{len(message['players'])}名玩家")
                                # 创建处理任务
                                asyncio.create_task(self.process_game_messages(message))
                            elif 'meta' in message:
                                print(f"检测到未分类的元数据消息")
                                # 创建处理任务
                                asyncio.create_task(self.process_game_messages(message))
                        
                        # 添加到消息队列
                        self.message_queue.append(message)
                        
                        # 分发消息给处理器
                        self.dispatch_message(message)
                        
                        # 特别处理猜测相关消息
                        if self.guessing and (message.get('type') == 'GUESS_RESULT' or 'players' in message):
                            await self.handle_guess_result(message)
                except Exception as e:
                    print(f"消息接收器错误: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # 短暂等待后继续
                    await asyncio.sleep(1)
        finally:
            print("消息接收器已停止")
            self.receiver_task = None

    def dispatch_message(self, message: Dict[str, Any]):
        """分发消息到注册的处理器，添加消息去重机制和无类型消息处理"""
        # 检查是否是无类型消息但包含重要状态信息
        contains_important_data = False
        if 'type' not in message:
            if 'phase' in message or 'players' in message or 'meta' in message:
                contains_important_data = True
                print("检测到包含重要数据的无类型消息，强制处理")
        
        # 计算消息指纹用于去重
        message_fingerprint = None
        if 'type' in message and message['type'] == 'GUESS_RESULT':
            if 'payload' in message and 'id' in message['payload']:
                message_fingerprint = f"guess_{message['payload']['id']}"
        elif 'players' in message:
            for player in message['players']:
                if player.get('id') == self.connection_id and 'guesses' in player and player['guesses']:
                    latest_guess = player['guesses'][-1]
                    if 'id' in latest_guess:
                        message_fingerprint = f"guess_{latest_guess['id']}"
                    break
        
        # 如果是已经处理过的消息，跳过
        if message_fingerprint and hasattr(self, 'processed_messages'):
            if message_fingerprint in self.processed_messages:
                print(f"跳过已处理的消息: {message_fingerprint}")
                return
            self.processed_messages.add(message_fingerprint)
        else:
            # 初始化处理过的消息集合
            if not hasattr(self, 'processed_messages'):
                self.processed_messages = set()
        
        # 正常分发消息
        message_type = message.get('type', '')
        if message_type in self.message_handlers:
            handler = self.message_handlers[message_type]
            if asyncio.iscoroutinefunction(handler):
                # 创建异步任务处理消息，避免阻塞
                asyncio.create_task(handler(message))
            else:
                handler(message)
        # 处理无类型但包含重要数据的消息
        elif contains_important_data and 'all' in self.message_handlers:
            handler = self.message_handlers['all']
            if asyncio.iscoroutinefunction(handler):
                asyncio.create_task(handler(message))
            else:
                handler(message)
                
    def register_handler(self, message_type: str, handler: Callable):
        self.message_handlers[message_type] = handler
        
    def unregister_handler(self, message_type: str):
        if message_type in self.message_handlers:
            del self.message_handlers[message_type]

    async def close(self):
        """安全关闭WebSocket连接"""
        await self.stop_receiver()
        
        if self.websocket:
            temp_ws = self.websocket
            self.websocket = None  # 立即清除引用避免重复关闭
            self.connected = False
            
            try:
                await temp_ws.close()
                print("已关闭与游戏服务器的连接")
            except Exception as e:
                print(f"关闭连接时出错 (可以忽略): {str(e)}")
    
    def reset_current_round_state(self):
        """只重置当前轮次状态，不累积约束条件"""
        self.guessing = False
        self.current_guess_result = None
        self.guess_success = False
        # 不清空guess_results和accumulated_constraints
        print("当前轮次状态已重置，保留了历史猜测结果和约束条件")
    
    def _handle_round_end(self, message):
        """处理轮次结束信息"""
        try:
            if 'meta' not in message:
                return False
            
            meta = message['meta']
            
            # 获取本轮获胜者ID
            round_winner_id = meta.get('currentRoundWinnerId')
            
            # 检查是否我方获胜，并且避免重复计数
            if round_winner_id and round_winner_id == self.connection_id:
                # 获取比赛模式信息
                best_of = meta.get("bestOf", "best_of_3")
                required_wins = self._calculate_required_wins(best_of)
                
                # 只有在之前未标记为成功的情况下才增加胜利次数
                if not self.guess_success:
                    self.player_wins += 1
                    self.guess_success = True
                    print(f"\n🏆 您赢得了本局游戏! 当前战绩: {self.player_wins}/{required_wins}")
                else:
                    print(f"\n🏆 已记录胜利! 当前战绩: {self.player_wins}/{required_wins}")
                
                # 检查是否已经赢得了整个比赛
                if self.player_wins >= required_wins:
                    print(f"\n🎊 恭喜! 您已经在{best_of}模式中获得了最终胜利! 🎊")
                    self.game_complete = True
                    return True
            
            # 显示轮次结束信息
            if 'players' in message:
                for player in message['players']:
                    if player.get('id') == self.connection_id:
                        if player.get('guesses') and any(g.get('isSuccess', False) for g in player['guesses']):
                            # 玩家猜对了
                            successful_guess = next((g for g in player['guesses'] if g.get('isSuccess', False)), None)
                            if successful_guess:
                                print(f"\n✅ 成功猜出正确答案: {successful_guess.get('firstName')} {successful_guess.get('lastName')}")
            
            # 触发状态更新，强制重置剩余猜测次数为8
            self.guess_results = []
            
            # 异步任务无法在同步方法中调用，所以在process_game_messages中处理
            
            return False
        
        except Exception as e:
            print(f"处理轮次结束消息时出错: {str(e)}")
            traceback.print_exc()
            return False

    def _calculate_required_wins(self, best_of):
        """根据best_of值计算需要获胜的轮数"""
        if best_of == "best_of_1":
            return 1
        elif best_of == "best_of_3":
            return 2
        elif best_of == "best_of_5":
            return 3
        elif best_of == "best_of_7":
            return 4
        else:
            # 默认计算方法
            try:
                total_rounds = int(best_of.split("_")[-1])
                return (total_rounds // 2) + 1
            except:
                return 1

    async def process_game_messages(self, message):
        """处理游戏相关消息，包括轮次变化和玩家动作"""
        message_type = message.get('type', '')
        state_changed = False
        update_data = {}
        
        # 记录处理的消息类型
        if message_type:
            print(f"处理游戏消息: 类型={message_type}")
        else:
            print("处理无类型游戏消息，尝试提取关键信息")
        
        # 捕获并保存元数据信息
        if 'meta' in message:
            self.game_meta = message['meta']
            print("提取元数据信息成功")
            if 'bestOf' in message['meta']:
                old_best_of = self.best_of
                self.best_of = message['meta']['bestOf']
                if old_best_of != self.best_of:
                    state_changed = True
                    update_data["best_of"] = self.best_of
                    update_data["required_wins"] = self._calculate_required_wins(self.best_of)
                    print(f"检测到游戏模式变化: {old_best_of} -> {self.best_of}")
        
        # 处理游戏阶段变化
        if 'phase' in message:
            old_phase = self.current_game_phase
            self.current_game_phase = message['phase']
            
            # 强制设置状态变化标志，确保每次阶段变化都会广播
            if old_phase != self.current_game_phase:
                state_changed = True
                update_data["game_phase"] = self.current_game_phase
                print(f"游戏阶段变化: {old_phase} -> {self.current_game_phase}")
            
            # 当阶段变为lobby时，重置胜利计数器
            if self.current_game_phase == 'lobby':
                old_wins = self.player_wins
                self.player_wins = 0
                self.game_complete = False
                print(f"🔄 检测到进入大厅(lobby)阶段，重置胜利计数 {old_wins} -> 0")
                
                # 添加到更新数据
                update_data["player_wins"] = 0
                
                # 重置累积的约束条件
                self.accumulated_constraints = {}
                self.guess_results = []
                print("🔄 重置所有累积约束条件和猜测记录")
            
            # 检测轮次结束，需要重置状态但保留约束条件
            elif self.current_game_phase == 'end' and old_phase == 'game':
                print(f"📢 检测到一局游戏结束，处理轮次结果")
                self._handle_round_end(message)
                print(f"📢 更新游戏状态，准备下一轮")
                self.reset_guess_state()  # 现在这个方法会保留约束条件
                
                # 强制添加重置后的猜测次数到更新数据
                update_data["remaining_guesses"] = 8
            
            # 检测新轮次开始，仅重置当前轮次状态，保留约束条件
            elif (self.current_game_phase == 'game' and old_phase in ['end', 'ready', 'starting', None]):
                print(f"📢 检测到新一轮游戏开始")
                if old_phase == 'end':
                    # 如果是从end阶段转到game阶段，只重置当前轮次状态
                    self.reset_current_round_state()
                else:
                    # 如果是新游戏，完全重置
                    self.reset_guess_state()
                    self.accumulated_constraints = {}  # 清空累积约束
            
            # 每次阶段变化后，无论如何都发送完整状态更新
            # 创建完整的更新数据包
            full_update_data = {
                "type": "STATE_UPDATE",
                "game_phase": self.current_game_phase,
                "best_of": self.best_of,
                "player_wins": self.player_wins,
                "required_wins": self._calculate_required_wins(self.best_of),
                "remaining_guesses": 8 - len(self.guess_results) if self.current_game_phase == 'game' else 8
            }
            
            # 立即广播完整状态
            from app.services.game_service import GameService
            await GameService.broadcast_update(self.room_id, full_update_data)
            print(f"📣 已广播完整状态更新: {full_update_data}")
            return  # 提前返回，避免后面重复广播
        
        # 如果状态发生变化，发送更新
        if state_changed:
            if not update_data:
                # 如果没有特定的更新数据，则发送完整状态
                update_data = {
                    "game_phase": self.current_game_phase,
                    "best_of": self.best_of,
                    "player_wins": self.player_wins,
                    "required_wins": self._calculate_required_wins(self.best_of),
                    "remaining_guesses": 8 - len(self.guess_results) if self.current_game_phase == 'game' else 8
                }
            
            # 添加消息类型
            update_data["type"] = "STATE_UPDATE"
            
            # 广播状态更新
            from app.services.game_service import GameService
            await GameService.broadcast_update(self.room_id, update_data)
        
        # 猜测结果处理
        if message_type == 'GUESS_RESULT' or ('players' in message and self.guessing):
            await self.handle_guess_result(message)
    
    async def handle_guess_result(self, message):
        """处理猜测结果消息，增强去重和错误处理"""
        if not self.guessing:
            print("⚠️ 收到猜测结果但当前不在猜测状态，忽略此消息")
            return False
        
        print(f"处理猜测结果消息: {message.get('type', '未知类型')}")
        
        # 提取猜测结果
        result = None
        
        # 尝试不同的消息格式
        if message.get('type') == 'GUESS_RESULT' and 'payload' in message:
            result = message['payload']
            print("从GUESS_RESULT类型消息中提取结果")
        elif 'payload' in message:
            result = message['payload']
            print("从简化消息格式中提取结果")
        elif 'players' in message:
            # 寻找玩家列表中的猜测记录
            conn_id = self.connection_id if self.connection_id else self.uuid
            for player in message['players']:
                if player.get('id') == conn_id and 'guesses' in player:
                    guesses = player['guesses']
                    if guesses:
                        # 在处理前检查这个猜测是否已经处理过
                        latest_guess = guesses[-1]
                        guess_id = latest_guess.get('id')
                        
                        # 使用猜测ID进行去重
                        if guess_id and hasattr(self, 'processed_guess_ids') and guess_id in self.processed_guess_ids:
                            print(f"🔄 此猜测结果({guess_id})已处理，跳过")
                            self.guessing = False
                            return False
                        
                        # 初始化处理过的猜测ID集合
                        if not hasattr(self, 'processed_guess_ids'):
                            self.processed_guess_ids = set()
                        
                        # 记录此ID为已处理
                        if guess_id:
                            self.processed_guess_ids.add(guess_id)
                        
                        result = latest_guess
                        print("从玩家列表中提取最新猜测结果")
                        break
        
        # 如果无法提取结果，则返回
        if not result:
            print("未能从消息中提取有效的猜测结果")
            return False
    
        
        # 打印猜测结果，便于调试
        print(f"\n猜测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # 确保结果中包含玩家ID，以便排除
        if 'id' not in result and 'playerId' in result:
            result['id'] = result['playerId']
        
        # 检查是否猜测成功
        if 'isSuccess' in result and result['isSuccess']:
            if not self.guess_success:
                self.player_wins += 1
            self.guess_success = True
            print(f"\n🎉 猜测成功! 正确答案是: {result.get('firstName', '')} {result.get('lastName', '')} ({result.get('nickname', '')}) 🎉")
        
        # 解析猜测约束条件
        result['constraints'] = self.parse_guess_result(result)
        
        # 保存结果用于后续猜测
        self.guess_results.append(result)
        self.current_guess_result = result
        
        # 广播猜测结果更新 - 确保每次猜测只广播一次
        update_data = {
            "type": "GUESS_RESULT",
            "result": result,
            "game_phase": self.current_game_phase,
            "remaining_guesses": 8 - len(self.guess_results) if self.current_game_phase == 'game' else 8,
            "player_wins": self.player_wins
        }
        
        from app.services.game_service import GameService
        await GameService.broadcast_update(self.room_id, update_data)
        
        # 重要：确保在处理完结果后设置guessing为False
        self.guessing = False
        print("猜测状态已重置，可以进行下一次猜测")
        return True
    
    def parse_guess_result(self, guess_result: Dict[str, Any]) -> Dict[str, Any]:
        """根据游戏规则解析猜测结果，提取约束条件"""
        constraints = {}
        
        # 解析国籍约束
        if 'nationality' in guess_result:
            nat_result = guess_result['nationality']['result']
            nat_value = guess_result['nationality'].get('value')
            
            if nat_result == "CORRECT":
                constraints['nationality'] = {'exact': nat_value}
            elif nat_result == "INCORRECT_CLOSE":
                # 同一区域
                region = self.get_country_region(nat_value)
                if region:
                    constraints['nationality_region'] = {'region': region}
                constraints['nationality'] = {'exclude': nat_value}
        
        # 解析团队约束
        if 'team' in guess_result:
            team_result = guess_result['team']['result']
            team_data = guess_result['team'].get('data')
            
            if team_result == "CORRECT":
                constraints['team'] = {'exact': team_data}
        
        # 解析年龄约束
        if 'age' in guess_result:
            age_result = guess_result['age']['result']
            age_value = guess_result['age'].get('value', 0)
            
            if age_result == "CORRECT":
                constraints['age'] = {'exact': age_value}
            elif age_result == "HIGH_CLOSE":
                constraints['age'] = {'min': age_value - 3, 'max': age_value - 1}
            elif age_result == "LOW_CLOSE":
                constraints['age'] = {'min': age_value + 1, 'max': age_value + 3}
            elif age_result == "HIGH_NOT_CLOSE":
                constraints['age'] = {'max': age_value - 4} # 这里没问题
            elif age_result == "LOW_NOT_CLOSE":
                constraints['age'] = {'min': age_value + 4} # 这里没问题
        
        # 解析角色约束
        if 'role' in guess_result:
            role_result = guess_result['role']['result']
            role_value = guess_result['role'].get('value')
            
            if role_result == "CORRECT":
                constraints['role'] = {'exact': role_value}
            else:
                constraints['role'] = {'exclude': role_value}
        
        # 解析Major出场次数约束
        if 'majorAppearances' in guess_result:
            major_result = guess_result['majorAppearances']['result']
            major_value = guess_result['majorAppearances'].get('value', 0)
            
            if major_result == "CORRECT":
                constraints['majorAppearances'] = {'exact': major_value}
            elif major_result == "HIGH_CLOSE":
                constraints['majorAppearances'] = {'min': major_value - 3, 'max': major_value - 1}
            elif major_result == "LOW_CLOSE":
                constraints['majorAppearances'] = {'min': major_value + 1, 'max': major_value + 3}
            elif major_result == "HIGH_NOT_CLOSE":
                # 不设置max=0，而是使用相对宽松的约束
                if major_value > 4:
                    constraints['majorAppearances'] = {'max': major_value - 4}
                else:
                    # 如果猜测值小于等于4，则设置较宽松的范围
                    constraints['majorAppearances'] = {'max': 3}
            elif major_result == "LOW_NOT_CLOSE":
                constraints['majorAppearances'] = {'min': major_value + 4}
        
        # 退役状态
        if 'isRetired' in guess_result:
            constraints['isRetired'] = {'exact': guess_result['isRetired']}
            
        return constraints
    
    def filter_players(self, players: List[Dict], constraints: Dict) -> List[Dict]:
        """根据约束条件筛选玩家"""
        filtered_players = []
        filtered_counts = {key: 0 for key in constraints.keys()}
        total_filtered = 0
        
        print(f"\n开始筛选玩家，共 {len(players)} 名玩家和 {len(constraints)} 个约束条件")
        print(f"约束条件: {json.dumps(constraints, indent=2)}")
        
        for player in players:
            match = True
            current_key = None  # 初始化当前键为None
            
            # 检查国籍
            if 'nationality' in constraints and match:
                current_key = 'nationality'  # 设置当前键
                if 'exact' in constraints['nationality']:
                    if player.get('nationality') != constraints['nationality']['exact']:
                        match = False
                if 'exclude' in constraints['nationality']:
                    if player.get('nationality') == constraints['nationality']['exclude']:
                        match = False
                if 'exclude_list' in constraints['nationality']:
                    if player.get('nationality') in constraints['nationality']['exclude_list']:
                        match = False
                
                # 如果该条件不匹配，更新过滤计数并跳过当前玩家
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查国家区域
            if 'nationality_region' in constraints and match:
                current_key = 'nationality_region'  # 设置当前键
                if 'region' in constraints['nationality_region']:
                    region = self.get_country_region(player.get('nationality'))
                    if region != constraints['nationality_region']['region']:
                        match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查团队
            if 'team' in constraints and match:
                current_key = 'team'  # 设置当前键
                if 'exact' in constraints['team']:
                    if player.get('team') != constraints['team']['exact']:
                        match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查年龄
            if 'age' in constraints and match:
                current_key = 'age'  # 设置当前键
                age = player.get('age', 0)
                if 'exact' in constraints['age']:
                    if age != constraints['age']['exact']:
                        match = False
                if 'min' in constraints['age'] and age < constraints['age']['min']:
                    match = False
                if 'max' in constraints['age'] and age > constraints['age']['max']:
                    match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查角色
            if 'role' in constraints and match:
                current_key = 'role'  # 设置当前键
                if 'exact' in constraints['role']:
                    if player.get('role') != constraints['role']['exact']:
                        match = False
                if 'exclude' in constraints['role']:
                    if player.get('role') == constraints['role']['exclude']:
                        match = False
                if 'exclude_list' in constraints['role']:
                    if player.get('role') in constraints['role']['exclude_list']:
                        match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查Major出场次数
            if 'majorAppearances' in constraints and match:
                current_key = 'majorAppearances'  # 设置当前键
                appearances = player.get('majorAppearances', 0)
                if 'exact' in constraints['majorAppearances']:
                    if appearances != constraints['majorAppearances']['exact']:
                        match = False
                if 'min' in constraints['majorAppearances'] and appearances < constraints['majorAppearances']['min']:
                    match = False
                if 'max' in constraints['majorAppearances'] and appearances > constraints['majorAppearances']['max']:
                    match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 检查退役状态
            if 'isRetired' in constraints and match:
                current_key = 'isRetired'  # 设置当前键
                if 'exact' in constraints['isRetired']:
                    if player.get('isRetired') != constraints['isRetired']['exact']:
                        match = False
                
                if not match:
                    filtered_counts[current_key] += 1
                    total_filtered += 1
                    continue
            
            # 如果所有条件都符合，则加入筛选结果
            if match:
                filtered_players.append(player)
        
        print(f"筛选结果: 共找到 {len(filtered_players)} 名匹配的玩家")
        print(f"每个约束条件过滤掉的玩家数量: {filtered_counts}")
        print(f"总共被过滤掉的玩家数量: {total_filtered}")
        
        return filtered_players
    
    async def get_next_guess(self, players_file="players_with_entropy.json") -> Optional[Dict]:
        """根据之前的猜测结果，确定下一个最佳猜测对象"""
        try:
            # 加载玩家数据
            with open(players_file, 'r', encoding='utf-8') as f:
                all_players = json.load(f)
            
            # 创建已猜测玩家ID集合
            guessed_player_ids = set()
            for result in self.guess_results:
                if 'id' in result:
                    guessed_player_ids.add(result['id'])
            
            # 排除已猜测的玩家
            available_players = [p for p in all_players if p.get('id') not in guessed_player_ids]
            print(f"排除已猜测玩家后剩余 {len(available_players)} 名可用玩家")
            
            # 合并当前轮次和累积的约束条件
            combined_constraints = self.accumulated_constraints.copy()
            
            # 从当前轮次的猜测结果中获取约束条件
            current_round_constraints = {}
            for result in self.guess_results:
                if 'constraints' in result:
                    # 使用新的合并方法逐步合并每个猜测结果的约束
                    current_round_constraints = self.merge_constraints(
                        current_round_constraints, 
                        result['constraints']
                    )
            
            # 再合并当前轮次和累积的约束条件
            combined_constraints = self.merge_constraints(
                combined_constraints, 
                current_round_constraints
            )
            
            print(f"合并后的约束条件: {json.dumps(combined_constraints, indent=2)}")
            
            # 使用合并的约束条件查找最佳候选人
            result = self.find_best_candidate(available_players, combined_constraints)
            
            # 如果没有找到匹配的候选人，尝试逐步放宽约束
            if not result:
                print("未找到匹配所有约束条件的候选人，尝试放宽约束...")
                
                # 首先尝试移除majorAppearances约束，这个约束可能最严格
                relaxed_constraints = combined_constraints.copy()
                if 'majorAppearances' in relaxed_constraints:
                    del relaxed_constraints['majorAppearances']
                    print("移除majorAppearances约束条件")
                    result = self.find_best_candidate(available_players, relaxed_constraints)
                
                # 如果仍然没有结果，尝试只保留国籍和角色约束
                if not result:
                    essential_constraints = {}
                    if 'nationality' in combined_constraints:
                        essential_constraints['nationality'] = combined_constraints['nationality']
                    if 'nationality_region' in combined_constraints:
                        essential_constraints['nationality_region'] = combined_constraints['nationality_region']
                    if 'role' in combined_constraints:
                        essential_constraints['role'] = combined_constraints['role']
                    
                    print(f"仅保留关键约束条件: {json.dumps(essential_constraints, indent=2)}")
                    result = self.find_best_candidate(available_players, essential_constraints)
                
                # 如果仍然没有结果，尝试只保留国籍约束
                if not result and ('nationality' in combined_constraints or 'nationality_region' in combined_constraints):
                    nationality_constraints = {}
                    if 'nationality' in combined_constraints:
                        nationality_constraints['nationality'] = combined_constraints['nationality']
                    if 'nationality_region' in combined_constraints:
                        nationality_constraints['nationality_region'] = combined_constraints['nationality_region']
                    
                    print(f"仅保留国籍约束条件: {json.dumps(nationality_constraints, indent=2)}")
                    result = self.find_best_candidate(available_players, nationality_constraints)
                
                # 如果一切尝试都失败，返回熵值最高的未猜测玩家
                if not result:
                    print("所有约束条件尝试都失败，选择熵值最高的未猜测玩家")
                    if available_players:
                        available_players.sort(key=lambda p: p.get('entropy_value', 0), reverse=True)
                        result = available_players[0]
                        print(f"选择熵值最高的玩家: {result.get('nickname')} (无约束匹配)")
            
            return result
        except Exception as e:
            print(f"获取下一个猜测出错: {str(e)}")
            traceback.print_exc()
            return None
    
    def find_best_candidate(self, players: List[Dict], constraints: Dict) -> Optional[Dict]:
        """根据约束条件和熵值找到最佳猜测候选人"""
        # 先筛选符合条件的玩家
        filtered_players = self.filter_players(players, constraints)
        
        if not filtered_players:
            return None
        
        # 按熵值排序，选择熵值最高的玩家
        filtered_players.sort(key=lambda p: p.get('entropy_value', 0), reverse=True)
        
        return filtered_players[0] if filtered_players else None
    
    def get_country_region(self, country_code):
        """获取国家所属的区域"""
        if not self.countries_data or country_code not in self.countries_data:
            return None
        return self.countries_data[country_code].get('region')
    
    def reset_guess_state(self):
        """重置猜测状态但保留累积约束条件"""
        # 使用改进的约束合并算法
        current_round_constraints = {}
        for result in self.guess_results:
            if 'constraints' in result:
                current_round_constraints = self.merge_constraints(
                    current_round_constraints, 
                    result['constraints']
                )
        
        # 重置之前，记录有多少条猜测结果
        old_results_len = len(self.guess_results)
        
        # 合并到累积约束条件
        if not hasattr(self, 'accumulated_constraints'):
            self.accumulated_constraints = {}
        
        self.accumulated_constraints = self.merge_constraints(
            self.accumulated_constraints,
            current_round_constraints
        )
        
        # 清除当前状态
        self.guess_results = []
        self.guessing = False
        self.current_guess_result = None
        self.guess_success = False
        
        # 清除消息处理相关的临时状态
        if hasattr(self, 'processed_guess_ids'):
            self.processed_guess_ids.clear()
        if hasattr(self, 'processed_messages'):
            self.processed_messages.clear()
        
        print(f"游戏状态已重置：清空了{old_results_len}个猜测结果，保留了{len(self.accumulated_constraints)}个约束条件")
        print(f"当前约束条件: {json.dumps(self.accumulated_constraints, indent=2)}")
    
    def merge_constraints(self, existing_constraints: Dict, new_constraints: Dict) -> Dict:
        """智能合并约束条件，处理多种复杂冲突情况"""
        result = existing_constraints.copy()
        
        for key, value in new_constraints.items():
            if key not in result:
                # 新约束，直接添加
                result[key] = value
                continue
                
            # 处理现有约束与新约束的合并
            existing = result[key]
            
            # 1. 精确约束 ('exact')
            if 'exact' in value:
                # 精确约束总是优先
                result[key] = value
                print(f"键 '{key}' 使用精确约束 {value['exact']}")
                continue
                
            # 2. 排除类约束 ('exclude', 'exclude_list')
            if ('exclude' in value or 'exclude_list' in value) and ('exclude' in existing or 'exclude_list' in existing):
                # 合并两个排除列表
                exclude_items = set()
                
                # 添加现有排除项
                if 'exclude' in existing:
                    exclude_items.add(existing['exclude'])
                if 'exclude_list' in existing:
                    exclude_items.update(existing['exclude_list'])
                    
                # 添加新排除项
                if 'exclude' in value:
                    exclude_items.add(value['exclude'])
                if 'exclude_list' in value:
                    exclude_items.update(value['exclude_list'])
                
                # 更新约束
                result[key] = {'exclude_list': list(exclude_items)}
                print(f"键 '{key}' 合并排除列表: {result[key]}")
                continue
                
            # 3. 范围约束 ('min', 'max')
            if ('min' in value or 'max' in value) and ('min' in existing or 'max' in existing):
                new_constraint = {}
                has_conflict = False
                
                # 处理最小值
                if 'min' in value and 'min' in existing:
                    new_constraint['min'] = max(value['min'], existing['min'])
                elif 'min' in value:
                    new_constraint['min'] = value['min']
                elif 'min' in existing:
                    new_constraint['min'] = existing['min']
                
                # 处理最大值
                if 'max' in value and 'max' in existing:
                    new_constraint['max'] = min(value['max'], existing['max'])
                elif 'max' in value:
                    new_constraint['max'] = value['max']
                elif 'max' in existing:
                    new_constraint['max'] = existing['max']
                
                # 检查冲突：min > max
                if 'min' in new_constraint and 'max' in new_constraint:
                    if new_constraint['min'] > new_constraint['max']:
                        print(f"⚠️ 约束冲突: {key} 的min({new_constraint['min']}) > max({new_constraint['max']})")
                        has_conflict = True
                
                # 特殊处理 majorAppearances 冲突
                if has_conflict and key == 'majorAppearances':
                    # 尝试更智能地解决冲突
                    if new_constraint['min'] > new_constraint['max']:
                        # 选择更可能的范围
                        if new_constraint['min'] >= 8:  # 高Major出场次数门槛
                            print(f"保留较高的majorAppearances最小值 {new_constraint['min']}")
                            result[key] = {'min': new_constraint['min']}
                        else:
                            print(f"保留较低的majorAppearances最大值 {new_constraint['max']}")
                            result[key] = {'max': new_constraint['max']}
                        continue
                
                # 对于其他字段或没有冲突的情况
                if not has_conflict:
                    result[key] = new_constraint
                else:
                    # 默认冲突处理：使用新约束
                    print(f"使用新约束代替冲突约束: {value}")
                    result[key] = value
                
                continue
            
            # 4. 其他情况：使用新约束替换旧约束
            result[key] = value
        
        # 打印合并结果
        print(f"合并约束条件结果: {json.dumps(result, indent=2)}")
        return result
    
    async def start_auto_guessing(self, max_guesses=8):
        """开始自动猜测流程"""
        # 总是重置猜测状态和成功标志
        guess_count = 0
        self.guess_success = False
        
        # 确保注册适当的处理器
        self.register_handler("GUESS_RESULT", self.handle_guess_result)
        self.register_handler("all", self.process_game_messages)
        
        while not self.guess_success and guess_count < max_guesses:
            guess_count += 1
            
            try:
                # 获取下一个最佳猜测
                next_player = await self.get_next_guess()
                if not next_player:
                    print("没有找到合适的猜测候选人，中止猜测")
                    return False
                    
                player_id = next_player.get('id')
                if not player_id:
                    print("错误: 候选人缺少ID，跳过")
                    continue
                
                print(f"自动猜测 [{guess_count}/{max_guesses}]: {next_player.get('nickname')} ({next_player.get('firstName', '')} {next_player.get('lastName', '')})")
                
                # 发送猜测请求
                self.guessing = True
                success = await self.send_guess(player_id)
                if not success:
                    print("发送猜测失败，重试...")
                    self.guessing = False
                    await asyncio.sleep(2)
                    continue
                
                # 等待猜测结果
                max_wait = 15  # 最多等待15秒
                wait_time = 0
                while self.guessing and wait_time < max_wait:
                    await asyncio.sleep(0.5)
                    wait_time += 0.5
                    
                    # 每隔1秒检查一次消息队列，并处理所有消息
                    if int(wait_time) != int(wait_time - 0.5):
                        messages = list(self.message_queue)  # 复制队列而不清空
                        for msg in messages:
                            if msg.get('type') == 'GUESS_RESULT' or 'players' in msg:
                                await self.handle_guess_result(msg)
                
                # 检查猜测是否成功
                if self.guess_success:
                    return True
                
                # 猜测间隔，避免请求过于频繁
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"猜测过程中出错: {str(e)}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(3)  # 出错后稍等片刻再继续
        
        return self.guess_success
    
    async def stop_receiver(self):
        """停止消息接收器"""
        self.stop_receiving = True
        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
            self.receiver_task = None
            print("消息接收器已停止")