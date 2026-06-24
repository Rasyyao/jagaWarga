# Usage Agent Penipuan

Agent Penipuan mengikuti pola agent lain:

- `tasks.py` untuk Celery task.
- `schemas.py` untuk model hasil.
- `services/` untuk logic domain.
- Tidak ada database, FastAPI, atau storage khusus.

## Dependency

Agent memakai dependency shared:

- `shared.llm.call_llm`
- `shared.utils.safe_json_parse`
- `shared.searcher.web_search`
- `httpx`
- `playwright` jika browser scraping tersedia

LLM dipakai untuk klasifikasi akhir. Rule indicator dan URL checker hanya menjadi konteks/bukti untuk LLM.

`tool check URL` sudah berjalan sebagai implementasi awal: agent membuka URL dari laporan, mengikuti redirect/shortlink, scraping title/teks/form, mendeteksi field sensitif, lalu meminta LLM menilai halaman. Jika Playwright/browser tidak tersedia, checker fallback ke HTTP client.

Env dari `.env.example` yang relevan:

```bash
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=30
LLM_MAX_TOKENS=4096
SERPAPI_KEY=
URL_CHECK_BROWSER=firefox
URL_CHECK_HEADLESS=true
URL_CHECK_TIMEOUT_MS=15000
URL_CHECK_MAX_TEXT_CHARS=6000
URL_CHECK_USE_LLM=true
```

Install dependency Python:

```bash
pip install -r requirements.txt
```

Jika ingin URL checker memakai Firefox lewat Playwright, install browser Playwright Firefox:

```bash
python -m playwright install firefox
```

Jika command ini belum dijalankan atau Firefox Playwright gagal launch, URL checker tetap mencoba fallback HTTP client. Fallback ini cukup untuk halaman HTML biasa, tetapi halaman phishing yang butuh JavaScript/rendering browser lebih baik dicek dengan Playwright.

## Pipeline Task

```python
from agent_penipuan.tasks import process_penipuan

result_context = process_penipuan(context.model_dump())
```

Output sukses disimpan ke:

```python
context.metadata["penipuan_result"]
```

Task ini akan menjalankan web search normal melalui `shared.searcher`, sehingga membutuhkan `SERPAPI_KEY`. Jika laporan berisi URL, task juga menjalankan URL checker.

Web search mencari referensi resmi. URL checker berbeda: ia membuka URL laporan warga dengan Playwright/HTTP client dan membuat evidence dari halaman tersebut.

## Pemakaian Lokal

```python
from agent_penipuan.tasks import analyze_text

result = analyze_text(
    "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
    report_id="demo-001",
    search_results=[],
    url_check_results=[],
)

print(result.status)
print(result.model_dump())
```

`search_results=[]` berarti tidak menjalankan web search. `url_check_results=[]` berarti tidak membuka URL sungguhan. Jika parameter itu tidak dikirim, agent akan memakai `search_penipuan` dan menjalankan URL checker jika ada URL.

Untuk testing lokal tanpa network, gunakan `search_results=[]` dan `url_check_results=[]` agar yang diuji hanya ekstraksi indikator dan LLM reasoning. Untuk pipeline normal, jangan kirim parameter itu supaya search resmi dan URL checker tetap berjalan.

Jika laporan berisi URL seperti shortlink, agent akan mencoba membuka URL itu, mengikuti redirect, mengambil konten halaman, dan membuat evidence dari hasil scraping. Jika URL tidak bisa dibuka, hasil URL checker berstatus `failed` dan tidak dipakai sebagai bukti phishing.

## Service Langsung

```python
from agent_penipuan.services.indicators import extract_rule_indicators, extract_urls
from agent_penipuan.services.reasoning_engine import reason_penipuan

text = "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim."
urls = extract_urls(text)
indicators = extract_rule_indicators(text, urls)

result = reason_penipuan(
    report_id="demo-001",
    text=text,
    urls=urls,
    indicators=indicators,
    search_results=[],
    url_check_results=[],
)
```

## Error

Jika LLM mati, API key salah, dependency LLM belum ada, atau response LLM bukan JSON valid, agent akan error. Ini sengaja supaya pipeline tidak menganggap hasil rule-based sebagai keputusan final.

Jika `SERPAPI_KEY` belum ada dan `search_results` tidak diisi manual, agent juga akan error dari layer search. Itu sesuai desain karena search memakai library shared.

Jika URL tidak bisa dibuka karena timeout/browser/network, URL checker mengembalikan `status="failed"` untuk URL tersebut. Itu bukan fallback keputusan; final classification tetap bergantung pada LLM.
