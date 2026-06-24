import json
from typing import Dict, List

from agent_penipuan.schemas import EvidenceItem, FraudIndicators, PenipuanResult, UrlCheckResult
from shared.utils import safe_json_parse


ALLOWED_STATUS = {"confirmed_fraud", "suspicious", "confirmed_legit", "unverified"}
ALLOWED_FRAUD_TYPES = {
    "transfer_scam",
    "pinjol_ilegal",
    "fake_giveaway",
    "account_takeover",
    "credential_phishing",
    "malware_link",
    "unknown",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _has_useful_official_content(result: Dict[str, str]) -> bool:
    title = (result.get("title") or "").strip()
    snippet = (result.get("snippet") or "").strip()
    if snippet:
        return True
    return bool(title and not title.lower().startswith(("http://", "https://")))


def _url_check_payload(url_check_results: list[UrlCheckResult]) -> list[dict]:
    return [item.model_dump(exclude_none=True) for item in url_check_results]


def _url_check_evidence(item: UrlCheckResult) -> EvidenceItem:
    title = item.domain or item.final_url or item.original_url
    if item.status == "failed":
        return EvidenceItem(
            type="url_check",
            title=title,
            value=f"URL checker gagal membuka/menganalisis URL: {item.error or 'unknown error'}",
            source_url=item.original_url,
        )

    details = []
    if item.final_url and item.final_url != item.original_url:
        details.append(f"Redirect ke {item.final_url}")
    if item.verdict != "unknown":
        details.append(f"Verdict URL checker: {item.verdict}")
    if item.sensitive_fields:
        details.append(f"Field sensitif terdeteksi: {', '.join(item.sensitive_fields)}")
    if item.has_form:
        details.append("Halaman memiliki form/input")
    if item.reasoning:
        details.append(item.reasoning)
    if not details:
        details.append("URL berhasil dicek, tetapi tidak ada sinyal kuat dari hasil scraping.")

    return EvidenceItem(
        type="url_check",
        title=title,
        value=". ".join(details),
        source_url=item.final_url or item.original_url,
        score=item.risk_score if item.risk_score is not None else item.similarity_score,
    )


def reason_penipuan(
    report_id: str,
    text: str,
    urls: list[str],
    indicators: FraudIndicators,
    search_results: List[Dict[str, str]],
    url_check_results: list[UrlCheckResult] | None = None,
) -> PenipuanResult:
    from shared.llm import call_llm

    url_check_results = url_check_results or []
    results_text = (
        "Tidak ada hasil pencarian resmi yang cukup relevan dengan laporan."
        if not search_results
        else "\n\n".join(
            [
                f"Sumber {i + 1}:\n- Website: {r['url']}\n- Judul: {r['title']}\n- Konten: {r['snippet']}"
                for i, r in enumerate(search_results)
            ]
        )
    )

    response = call_llm(
        messages=[
            {
                "role": "system",
                "content": """
Kamu adalah Agent Penipuan JagaWarga untuk deteksi penipuan dan phishing di Indonesia.
Analisis laporan warga berdasarkan indikator awal, hasil URL checker, dan sumber resmi. Jangan mengarang bukti.
Gunakan url_check_results sebagai fakta dari URL laporan warga.
Jika url_check_results berstatus failed, sebutkan keterbatasannya dan jangan jadikan itu bukti phishing.
Gunakan official_search_results hanya jika isinya relevan dengan laporan.
Jika official_search_results kosong, jelaskan bahwa tidak ada sumber resmi relevan yang ditemukan.
Jangan membuat evidence official_search sendiri.

Klasifikasikan fraud_type ke salah satu:
- transfer_scam
- pinjol_ilegal
- fake_giveaway
- account_takeover
- credential_phishing
- malware_link
- unknown

Output HANYA JSON:
{"status":"confirmed_fraud|suspicious|confirmed_legit|unverified","fraud_type":"...","confidence":0.0,"risk_level":"low|medium|high|critical","reasoning":"alasan singkat","evidence":[{"type":"llm_reasoning","title":"Indikator","value":"..."}]}
""",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "report_id": report_id,
                        "report_text": text,
                        "urls": urls,
                        "rule_indicators": indicators.model_dump(),
                        "url_check_results": _url_check_payload(url_check_results),
                        "official_search_results": search_results,
                        "official_search_summary": results_text,
                        "locale": "id-ID",
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.2,
    )

    parsed = safe_json_parse(response)
    if not parsed:
        raise ValueError("LLM response tidak berisi JSON valid")

    status = parsed.get("status", "unverified")
    if status not in ALLOWED_STATUS:
        status = "unverified"

    fraud_type = parsed.get("fraud_type", "unknown")
    if fraud_type not in ALLOWED_FRAUD_TYPES:
        fraud_type = "unknown"

    risk_level = parsed.get("risk_level", "medium")
    if risk_level not in ALLOWED_RISK_LEVELS:
        risk_level = "medium"

    evidence = [
        EvidenceItem(
            type=str(item.get("type", "llm_reasoning")),
            title=item.get("title"),
            value=str(item.get("value", "")),
            source_url=item.get("source_url"),
            score=item.get("score"),
        )
        for item in parsed.get("evidence", [])
        if isinstance(item, dict) and item.get("value") and item.get("type") != "official_search"
    ]
    evidence.extend(_url_check_evidence(item) for item in url_check_results)
    evidence.extend(
        EvidenceItem(
            type="official_search",
            title=result.get("title"),
            value=result.get("snippet") or result.get("title", ""),
            source_url=result.get("url"),
        )
        for result in search_results
        if result.get("url") and _has_useful_official_content(result)
    )

    return PenipuanResult(
        report_id=report_id,
        status=status,
        fraud_type=fraud_type,
        confidence=float(parsed.get("confidence", 0.5)),
        risk_level=risk_level,
        indicators=indicators,
        evidence=evidence,
        reasoning=parsed.get("reasoning", "Tidak ada reasoning tersedia."),
    )
