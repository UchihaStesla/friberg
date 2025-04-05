from pydantic import BaseModel
from typing import Optional, Dict, List, Any

class RoomConnection(BaseModel):
    room_id: str

class PlayerGuess(BaseModel):
    player_id: str
    room_id: str

class GuessResult(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class Recommendation(BaseModel):
    player_id: str
    first_name: str
    last_name: str
    nickname: str
    nationality: str
    team: Optional[str] = None
    age: Optional[int] = None
    role: Optional[str] = None
    is_retired: Optional[bool] = None
    entropy_value: Optional[float] = None
    image_url: Optional[str] = None

# class RecommendationResponse(BaseModel):
#     success: bool
#     recommendations: List[Recommendation] = []
#     message: Optional[str] = None

class ConstraintUpdate(BaseModel):
    constraints: Dict[str, Any]
    
class GameMetadata(BaseModel):
    best_of: str = "best_of_3"
    current_wins: int = 0
    required_wins: int = 2
    current_phase: Optional[str] = None
    remaining_guesses: int = 8

class RecommendationResponse(BaseModel):
    success: bool
    recommendations: List[Recommendation] = []
    game_metadata: Optional[GameMetadata] = None
    constraints: Optional[Dict[str, Any]] = None
    message: Optional[str] = None