from typing import List, Dict
from shared.llm import call_llm
from shared.utils import safe_json_parse
from agent_pengaduan.schemas import ClaimExtraction


EXTRACT_MESSAGES: List[Dict[str, str]] = lambda text: [
    {
        "role": "system",
        "content": (
            "Kamu adalah asisten yang mengekstrak inti pengaduan layanan publik dari teks. "
            "Tugasmu: buat SATU kalimat search query yang merangkum masalah pengaduan. "
            "Pertahankan SEMUA detail penting: jenis masalah, lokasi, waktu, institusi terkait. "
            "Query harus spesifik dan cocok untuk dicari di Google. "
            "Contoh teks: Listrik di rumahku mati dari pagi. Aku tinggal di Jakarta Selatan."
            "Contoh inti pengaduan: Pemadaman listrik di Jakarta Selatan hari ini"
            "Output PURE JSON saja. "
            'Format: {"claims": ["satu query pengaduan"], "context": "ringkasan singkat"}'
        ),
    },
    {
        "role": "user",
        "content": f"Buat search query dari pengaduan berikut:\n\n{text}\n\nOutput JSON only.",
    },
]


def extract_claim(text: str) -> ClaimExtraction:
    response = call_llm(messages=EXTRACT_MESSAGES(text), temperature=0.3)
    parsed = safe_json_parse(response)

    if "claims" not in parsed or not isinstance(parsed["claims"], list):
        return ClaimExtraction(claims=[text[:500]], context=text[:200])

    return ClaimExtraction(
        claims=parsed.get("claims", [text[:500]]),
        context=parsed.get("context", text[:200]),
    )
