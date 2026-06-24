from typing import Literal

from pydantic import BaseModel, Field


AgentStatus = Literal["confirmed_fraud", "suspicious", "confirmed_legit", "unverified"]
FraudType = Literal[
    "transfer_scam",
    "pinjol_ilegal",
    "fake_giveaway",
    "account_takeover",
    "credential_phishing",
    "malware_link",
    "unknown",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
UrlCheckStatus = Literal["checked", "failed"]
UrlVerdict = Literal["phishing", "suspicious", "legit", "unknown"]


class EvidenceItem(BaseModel):
    type: str
    title: str | None = None
    value: str
    source_url: str | None = None
    score: float | None = None


class FraudIndicators(BaseModel):
    has_url: bool = False
    asks_for_otp: bool = False
    asks_for_nik_kk: bool = False
    asks_for_pin_password: bool = False
    asks_for_transfer: bool = False
    uses_urgency: bool = False
    impersonates_institution: str | None = None


class UrlCheckResult(BaseModel):
    original_url: str
    final_url: str | None = None
    domain: str | None = None
    status: UrlCheckStatus = "checked"
    verdict: UrlVerdict = "unknown"
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    title: str | None = None
    description: str | None = None
    has_form: bool = False
    sensitive_fields: list[str] = Field(default_factory=list)
    similarity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reasoning: str | None = None
    error: str | None = None


class PenipuanResult(BaseModel):
    agent: Literal["fraud_phishing"] = "fraud_phishing"
    report_id: str
    status: AgentStatus
    fraud_type: FraudType
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    indicators: FraudIndicators
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reasoning: str
    next_action: Literal["validator"] = "validator"
