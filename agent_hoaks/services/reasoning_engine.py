from typing import List, Dict
from shared.llm import call_llm
from shared.utils import safe_json_parse
from agent_hoaks.schemas import HoaxResult, SearchResult


def reason_hoax(claims: List[str], search_results: List[Dict[str, str]]) -> HoaxResult:
    main_claim = claims[0] if claims else ""

    results_text = (
        "Tidak ada hasil pencarian ditemukan dari website resmi."
        if not search_results
        else "\n\n".join([
            f"Sumber {i+1}:\n- Website: {r['url']}\n- Judul: {r['title']}\n- Konten: {r['snippet']}"
            for i, r in enumerate(search_results)
        ])
    )

    response = call_llm(
        messages=[
            {
                "role": "system",
                "content": ("""
Kamu adalah fact-checker profesional. Tugasmu:
1. Analisis dan bandingkan klaim dengan informasi dari hasil pencarian
2. Tentukan klasifikasi:
   - 'verified': Jika klaim terbukti BENAR berdasarkan sumber terpercaya
   - 'not_verified': Jika klaim adalah hoax, misleading, atau tidak terbukti
3. Buat teks reasoning yang merangkum hasil pencarian. Perhatikan masalahnya, lokasi, waktu klaim. Ambil hanya hasil pencarian yang relevan dan sesuai
4. Tentukan confidence:
   - 0.9-1.0: Ada konfirmasi jelas dari sumber terpercaya
   - 0.7-0.89: Ada indikasi kuat dari sumber
   - 0.5-0.69: Tidak ada informasi pendukung dari hasil pencarian
   - 0.3-0.49: Informasi terbatas
   - 0.0-0.29: Tidak dapat disimpulkan
5. Output HANYA JSON, tanpa text lain:
{"hoax_topic": "verified atau not_verified", "reasoning": "penjelasan singkat beberapa kalimat", "confidence": 0.8}
                """),
            },
            {
                "role": "user",
                "content": f"""Analisis klaim berikut berdasarkan hasil pencarian:

KLAIM UTAMA:
{main_claim}

HASIL PENCARIAN:
{results_text}
""",
            },
        ],
        temperature=0.2,
    )

    parsed = safe_json_parse(response)
    hoax_topic = parsed.get("hoax_topic", "not_verified")
    if hoax_topic not in ["verified", "not_verified"]:
        hoax_topic = "not_verified"

    return HoaxResult(
        hoax_topic=hoax_topic,
        data_source=[
            SearchResult(url=r["url"], title=r["title"], snippet=r["snippet"], date=r.get("date"))
            for r in search_results
        ],
        reasoning=parsed.get("reasoning", "Tidak ada reasoning tersedia"),
        confidence=float(parsed.get("confidence", 0.5)),
    )
