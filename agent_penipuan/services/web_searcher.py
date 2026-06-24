from typing import Dict, List
import re


FRAUD_REFERENCE_WEBSITES = [
    "ojk.go.id",
    "komdigi.go.id",
    "kominfo.go.id",
    "bi.go.id",
    "polri.go.id",
    "bca.co.id",
    "bri.co.id",
    "bankmandiri.co.id",
    "bni.co.id",
]

GENERIC_STOPWORDS = {
    "yang",
    "dan",
    "atau",
    "untuk",
    "dengan",
    "sekarang",
    "tinggal",
    "akan",
    "kami",
    "anda",
    "kamu",
    "nomor",
    "telefon",
    "telepon",
    "masukan",
    "masukin",
    "ambil",
    "ayo",
}

OFFICIAL_RELEVANCE_TERMS = {
    "penipuan",
    "phishing",
    "palsu",
    "modus",
    "waspada",
    "hoaks",
    "scam",
    "data pribadi",
    "nik",
    "ktp",
    "kk",
    "bansos",
    "kip",
    "pinjol",
    "otp",
    "rekening",
    "transfer",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) >= 3 and word not in GENERIC_STOPWORDS}


def _result_content(result: Dict[str, str]) -> str:
    return " ".join(
        [
            result.get("title", ""),
            result.get("snippet", ""),
        ]
    ).strip()


def _has_relevant_content(query: str, result: Dict[str, str]) -> bool:
    content = _result_content(result)
    if not content:
        return False

    lower_content = content.lower()
    query_tokens = _tokens(query)
    content_tokens = _tokens(content)

    if len(query_tokens.intersection(content_tokens)) >= 2:
        return True

    if any(term in lower_content for term in OFFICIAL_RELEVANCE_TERMS):
        return bool(query_tokens.intersection(content_tokens)) or any(
            term in query.lower() for term in OFFICIAL_RELEVANCE_TERMS
        )

    return False


def search_penipuan(claims: List[str]) -> List[Dict[str, str]]:
    query = claims[0] if claims else ""
    if not query:
        return []

    from shared.searcher import web_search

    results = web_search(query, FRAUD_REFERENCE_WEBSITES)
    return [result for result in results if _has_relevant_content(query, result)]
