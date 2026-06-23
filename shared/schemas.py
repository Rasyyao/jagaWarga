from shared.enums import InputType, IntentLabel, ReportType, PipelineStatus
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class IncomingMessage(BaseModel):
    message_id : str
    sender_wa_id : str
    sender_name : Optional[str] = None
    raw_text : Optional[str] = None
    media_id : Optional[str] = None
    media_mime_type : Optional[str] = None
    received_at : datetime = Field(default_factory=datetime.utcnow)
    
    
class PipelineContext(BaseModel):
    message : IncomingMessage
    input_type : Optional[InputType] = None
    extracted_text : Optional[str] = None
    intent : Optional[IntentLabel]
    intent_confidence : Optional[float] = None
    report_type : Optional[ReportType] = None
    cache_hit : bool = False
    status : PipelineStatus = PipelineStatus.RECEIVED
    metadata: dict =Field(default_factory=dict)
    
