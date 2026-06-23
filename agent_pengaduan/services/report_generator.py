from typing import List, Dict
from shared.llm import call_llm
from shared.utils import safe_json_parse
from agent_pengaduan.schemas import PengaduanResult, SearchResult


def generate_report(complaint_text: str, search_results: List[Dict[str, str]]) -> PengaduanResult:
    results_text = (
        "Tidak ada hasil pencarian ditemukan dari sumber resmi."
        if not search_results
        else "\n\n".join([
            f"Sumber {i+1}:\n- Website: {r['url']}\n- Judul: {r['title']}\n- Konten: {r['snippet']}\n- Tanggal: {r.get('date', '-')}"
            for i, r in enumerate(search_results)
        ])
    )

    response = call_llm(
        messages=[
            {
                "role": "system",
                "content": ("""
Kamu adalah asisten layanan publik yang memproses pengaduan warga. Tugasmu:
1. Klasifikasikan status pengaduan:
   - 'verified': Ada konfirmasi resmi/berita bahwa masalah ini nyata dan/atau sudah ditangani
   - 'not_verified': Tidak ada informasi resmi yang mengkonfirmasi
2. Dari teks pengaduan yang dikirim, buatkan laporan formal untuk kebutuhan pengaduan ke situs pemerintahan (3-4 kalimat) yang mencakup: apa masalahnya, lokasi (jika ada), waktu (jika ada)
3. Buat teks reasoning yang merangkum hasil pencarian. Perhatikan masalahnya, lokasi, waktu masalah atau pengaduan. Ambil hanya hasil pencarian yang relevan dan sesuai
4. Confidence:
   - 0.9-1.0: Konfirmasi jelas dari sumber resmi
   - 0.7-0.89: Ada indikasi dari berita/sumber terpercaya
   - 0.5-0.69: Tidak ada informasi relevan
   - 0.0-0.49: Informasi terlalu terbatas
5. Output HANYA JSON, tanpa text lain:
{"status": "verified atau not_verified", "laporan_text": "teks laporan formal", "reasoning": "penjelasan beberapa kalimat", "confidence": 0-1}
                """),
            },
            {
                "role": "user",
                "content": f"""Analisis pengaduan berikut berdasarkan hasil pencarian:

TEKS PENGADUAN:
{complaint_text}

HASIL PENCARIAN DARI SUMBER RESMI:
{results_text}
""",
            },
        ],
        temperature=0.4,
    )

    parsed = safe_json_parse(response)
    status = parsed.get("status", "not_verified")
    if status not in ["verified", "not_verified"]:
        status = "not_verified"

    return PengaduanResult(
        status=status,
        source=[
            SearchResult(url=r["url"], title=r["title"], snippet=r["snippet"], date=r.get("date"))
            for r in search_results
        ],
        laporan_text=parsed.get("laporan_text", "Laporan tidak dapat dibuat."),
        reasoning=parsed.get("reasoning", "Tidak ada reasoning tersedia."),
        confidence=float(parsed.get("confidence", 0.5)),
    )
