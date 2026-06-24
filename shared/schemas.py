from shared.enums import InputType, IntentLabel, ReportType, PipelineStatus
from pydantic import BaseModel, Field
from typing import List, Optional
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

class ClaimExtraction(BaseModel):
    claims: List[str]
    context: str


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    date: Optional[str] = None

class PengaduanResult(BaseModel):
    status: str
    source: List[SearchResult]
    laporan_text: str
    reasoning: str
    confidence: float

class HoaxResult(BaseModel):
    hoax_topic: str
    data_source: List[SearchResult]
    reasoning: str
    confidence: float
    
class IntentResult(BaseModel):
    label: IntentLabel
    confidence: float
    all_scores: dict[str, float]