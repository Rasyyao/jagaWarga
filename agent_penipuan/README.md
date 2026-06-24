# Agent Penipuan JagaWarga

Agent untuk pipeline **Penipuan dan Phishing**. Struktur dibuat sederhana mengikuti pola `agent_hoaks` dan `agent_pengaduan`: task Celery di `tasks.py`, schema di `schemas.py`, dan logic domain di `services/`.

Agent ini tidak punya database dan tidak punya microservice. Hasilnya ditulis ke `PipelineContext.metadata["penipuan_result"]`.

Scope folder ini adalah menyediakan task `agent_penipuan.process`. Dispatch dari webhook/input handler ke task agent berada di layer pipeline/orchestrator.

Diagram pipeline ada di [`docs/pipeline-lks-ai.excalidraw`](docs/pipeline-lks-ai.excalidraw). Bagian **Agent 1 - Penipuan dan Phishing** di diagram adalah desain target. Implementasi kode saat ini sudah memuat versi awal `tool check URL`, lalu keputusan final tetap memakai LLM DeepSeek.

## Struktur

```text
agent_penipuan/
  tasks.py
  schemas.py
  services/
    indicators.py
    url_checker.py
    web_searcher.py
    reasoning_engine.py
  docs/
    pipeline-lks-ai.excalidraw
    USAGE.md
    TECHNICAL.md
    TESTING.md
```

## Flow

Flow implementasi saat ini:

```text
PipelineContext
  -> process_penipuan
  -> extract_urls + extract_rule_indicators
  -> search_penipuan memakai shared.searcher.web_search
  -> check_urls membuka URL laporan warga jika ada link
  -> reason_penipuan memakai shared.llm.call_llm sebagai LLM reasoning
  -> context.metadata["penipuan_result"]
```

Detail implementasi saat ini:

- `extract_urls`: mengambil URL dari teks laporan.
- `extract_rule_indicators`: membuat indikator awal seperti OTP, PIN, NIK/KK, urgency, transfer, dan impersonasi institusi.
- `search_penipuan`: mengambil referensi resmi lewat `shared.searcher`, lalu membuang hasil yang tidak relevan.
- `check_urls`: membuka URL laporan, mengikuti redirect/shortlink, mengambil title/teks/form, mendeteksi field sensitif, dan meminta LLM menilai halaman.
- `reason_penipuan`: meminta LLM DeepSeek API mengeluarkan JSON final berisi `status`, `fraud_type`, `confidence`, `risk_level`, `evidence`, dan `reasoning`.

Klasifikasi utama dilakukan oleh LLM DeepSeek. Rule indicator dan URL checker menjadi konteks/bukti, bukan fallback keputusan final.
Jika tidak ada sumber resmi yang relevan, agent tidak memaksa membuat `official_search` evidence.

Desain target Agent 1 di Excalidraw:

```text
Input teks/link
  -> ekstraksi indikator awal
  -> tool check URL jika laporan memuat link
  -> scraping isi halaman URL laporan
  -> web search sumber resmi
  -> semantic similarity antara isi URL laporan dan sumber resmi
  -> LLM klasifikasi final
  -> output status/fraud_type/confidence/evidence
```

Maksud `tool check URL` bukan sekadar mencari sumber resmi. Tool ini membuka URL yang dikirim warga, mengikuti redirect, mengambil konten halaman, membaca judul/form/teks halaman, lalu mengecek apakah halaman tersebut berindikasi phishing. Playwright dipakai jika tersedia; jika tidak, checker fallback ke HTTP client. Browser target bisa dikonfigurasi ke Firefox atau Chromium. Semantic similarity saat ini masih token overlap ringan untuk konteks pemerintah, sedangkan CLIP belum diimplementasikan dan tetap menjadi opsi tambahan jika pipeline nanti mengambil screenshot/logo halaman.

## Pemakaian Lokal

```python
from agent_penipuan.tasks import analyze_text

result = analyze_text(
    "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
    report_id="demo-001",
    search_results=[],
    url_check_results=[],
)

print(result.model_dump())
```

`search_results=[]` dipakai untuk demo/test tanpa memanggil SerpAPI. `url_check_results=[]` dipakai untuk demo/test tanpa membuka URL sungguhan. Di pipeline normal, `analyze_text` akan memanggil `search_penipuan` dan `check_urls` jika laporan memuat URL.

## Error LLM

Agent ini tidak membuat keputusan dari rule-based saja saat LLM error. Jika `shared.llm.call_llm` gagal atau response LLM bukan JSON valid, exception akan naik seperti agent lain.

Ini sengaja dibuat eksplisit supaya hasil demo tidak terlihat seolah-olah model berhasil padahal API LLM sedang mati.

## Env Yang Dipakai

Agent Penipuan tidak punya database/env service terpisah. Ia memakai konfigurasi shared:

- `LLM_PROVIDER=deepseek`, `LLM_BASE_URL=https://api.deepseek.com`, `LLM_API_KEY`, dan `LLM_MODEL` untuk `shared.llm.call_llm`
- `SERPAPI_KEY` untuk `shared.searcher.web_search`
- `URL_CHECK_BROWSER`, `URL_CHECK_HEADLESS`, `URL_CHECK_TIMEOUT_MS`, `URL_CHECK_MAX_TEXT_CHARS`, dan `URL_CHECK_USE_LLM` untuk URL checker

Dokumentasi teknikal: [`docs/TECHNICAL.md`](docs/TECHNICAL.md)  
Panduan testing: [`docs/TESTING.md`](docs/TESTING.md)
