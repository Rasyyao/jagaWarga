from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing  import Optional
from shared.config import get_settings
from shared.schemas import IncomingMessage
from shared.enums import PipelineStatus

router = APIRouter()
setting = get_settings()

class KirimiPayload(BaseModel):
    event: str
    deviceId : str
    msgId : str
    sender : str = Field(alias="from")
    name : Optional[str] = None
    message : Optional[str] = None
    isFromGroup : bool = False
    isFromMe : bool = False
    messageType: str = "text"
    mediaUrl : Optional[str] = None
    
    class Config:
        populate_by_name = True
        
_sessions : dict = {}

def get_session(wa_id: str) -> dict:
    if wa_id not in _sessions:
        _sessions[wa_id] = {
            "state": "new",
            "name": None,
            "address": None,
            "report_buffer": [],
        }
    return _sessions[wa_id]


    