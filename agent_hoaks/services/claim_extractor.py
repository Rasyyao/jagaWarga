from typing import List, Dict
from shared.llm import call_llm
from shared.utils import safe_json_parse
from shared.schemas import ClaimExtraction


EXTRACT_MESSAGES: List[Dict[str, str]] = lambda text: [
    {
        "role": "system",
        "content": (
            "Kamu adalah asisten yang mengekstrak SATU klaim utama dari teks yang berpotensi hoax. "
            "Tugasmu: identifikasi klaim faktual inti yang perlu diverifikasi. "
            "Pertahankan SEMUA detail penting: angka, nama, tanggal, lokasi, institusi. "
            "Jangan tambahkan opini atau interpretasi. "
            "Output PURE JSON saja. "
            'Format: {"claims": ["satu klaim lengkap"], "context": "ringkasan singkat"}'
            "Contoh teks: Apa? Jokowi perintahkan mentri dan BUMN untuk berikan bansos seperti beras dan telur ke 20% orang miskin"
            "Contoh klaim: Jokowi perintahkan mentri dan BUMN untuk berikan bansos ke 20% orang miskin"
        ),
    },
    {
        "role": "user",
        "content": f"Ekstrak klaim utama yang perlu diverifikasi dari teks berikut:\n\n{text}\n\nOutput JSON only.",
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
