from fastapi import APIRouter, HTTPException
from app.models.schemas import RoomConnection, PlayerGuess, GuessResult, RecommendationResponse, ConstraintUpdate
from app.services.game_service import GameService

router = APIRouter(prefix="/api")

@router.post("/connect", response_model=GuessResult)
async def connect_to_room(connection: RoomConnection):
    """连接到游戏房间"""
    try:
        await GameService.get_client(connection.room_id)
        return GuessResult(success=True, message="成功连接到游戏房间")
    except Exception as e:
        return GuessResult(success=False, message=f"连接失败: {str(e)}")

@router.post("/disconnect", response_model=GuessResult)
async def disconnect_from_room(connection: RoomConnection):
    """断开与游戏房间的连接"""
    result = await GameService.close_client(connection.room_id)
    if result:
        return GuessResult(success=True, message="成功断开连接")
    return GuessResult(success=False, message="没有找到指定房间的连接")

@router.post("/manual-guess", response_model=GuessResult)
async def manual_guess(guess: PlayerGuess):
    """发送手动猜测"""
    try:
        result = await GameService.send_manual_guess(guess.room_id, guess.player_id)
        return GuessResult(success=result["success"], result=result.get("result"), message=result.get("message"))
    except HTTPException as e:
        return GuessResult(success=False, message=e.detail)
    except Exception as e:
        return GuessResult(success=False, message=f"猜测过程中出错: {str(e)}")

@router.post("/auto-guess", response_model=GuessResult)
async def auto_guess(connection: RoomConnection):
    """启动自动猜测流程"""
    try:
        result = await GameService.start_auto_guessing(connection.room_id)
        return GuessResult(success=result["success"], message=result["message"])
    except Exception as e:
        return GuessResult(success=False, message=f"自动猜测过程中出错: {str(e)}")

@router.post("/update-constraints", response_model=RecommendationResponse)
async def update_constraints(constraint_update: ConstraintUpdate, connection: RoomConnection):
    """更新约束条件并获取新的推荐"""
    try:
        recommendations = await GameService.get_recommendations(
            connection.room_id, 
            constraint_update.constraints
        )
        return RecommendationResponse(success=True, recommendations=recommendations)
    except Exception as e:
        return RecommendationResponse(success=False, message=f"更新约束条件失败: {str(e)}")
    
@router.post("/player-ready", response_model=GuessResult)
async def player_ready(connection: RoomConnection):
    """发送玩家准备就绪信号"""
    try:
        client = await GameService.get_client(connection.room_id)
        result = await client.player_ready()
        if result:
            return GuessResult(success=True, message="玩家已准备就绪")
        else:
            return GuessResult(success=False, message="准备就绪信号发送失败")
    except Exception as e:
        return GuessResult(success=False, message=f"准备失败: {str(e)}")
    
@router.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(connection: RoomConnection):
    """获取推荐玩家列表"""
    try:
        result = await GameService.get_recommendations(connection.room_id)
        return RecommendationResponse(
            success=True, 
            recommendations=result['recommendations'],
            game_metadata=result['game_metadata'],
            constraints=result['constraints']
        )
    except Exception as e:
        return RecommendationResponse(success=False, message=f"获取推荐失败: {str(e)}")
    
