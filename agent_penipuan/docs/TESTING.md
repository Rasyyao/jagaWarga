# Testing Agent Penipuan

## Unit Test

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.test_agent_penipuan
```

Test memakai mock LLM, `search_results=[]`, dan `url_check_results=[]`/mock scraper, jadi tidak butuh API LLM, SerpAPI, browser, atau network.

Unit test saat ini menguji implementasi URL checker tanpa network sungguhan. Scraping halaman dan Playwright real tetap masuk kategori integration test.

Testing dipisah seperti ini:

- unit test untuk ekstraksi indikator, reasoning, URL checker dengan scraper mock, dan wiring evidence,
- integration test Playwright dengan `URL_CHECK_BROWSER=firefox`,
- integration test fallback `URL_CHECK_BROWSER=chromium`,
- test semantic similarity embedding jika nanti mengganti token overlap sederhana,
- test CLIP jika pipeline memakai screenshot/logo halaman.

Expected output:

```text
.................
----------------------------------------------------------------------
Ran 17 tests in ...s

OK
```

## Detail Skenario Unit Test

| Test | Tujuan | Dependency eksternal |
| --- | --- | --- |
| `test_extract_urls_normalizes_www_and_deduplicates` | Memastikan URL `www.` dinormalisasi ke `https://` dan duplikat dibuang. | Tidak ada |
| `test_extract_urls_detects_bare_shortlink` | Memastikan shortlink tanpa `https://`, seperti `bit.ly/...`, tetap terdeteksi sebagai URL. | Tidak ada |
| `test_rule_indicators_detect_sensitive_request` | Memastikan indikator OTP, PIN, NIK, urgency, dan impersonasi bank terbaca. | Tidak ada |
| `test_analyze_text_returns_llm_result` | Memastikan `analyze_text` mengembalikan hasil dari LLM mock, bukan rule-based fallback. | Mock `shared.llm` |
| `test_analyze_text_does_not_add_irrelevant_official_search_evidence` | Memastikan URL resmi yang kosong/tidak relevan tidak otomatis masuk sebagai `official_search` evidence. | Mock `shared.llm` |
| `test_analyze_text_raises_when_llm_unavailable` | Memastikan error LLM dinaikkan sebagai error. | Mock `shared.llm` error |
| `test_url_checker_uses_scraped_url_facts_and_llm` | Memastikan URL checker memakai fakta hasil scraping, mendeteksi field sensitif, dan menyimpan verdict LLM. | Mock scraper dan mock `shared.llm` |
| `test_url_checker_returns_failed_result_when_scrape_fails` | Memastikan kegagalan scraping URL diakui sebagai `status=failed`, bukan bukti phishing palsu. | Mock scraper error |
| `test_analyze_text_adds_url_check_evidence` | Memastikan hasil URL checker masuk sebagai evidence `url_check` pada output agent. | Mock `shared.llm` dan input `UrlCheckResult` |
| `test_process_penipuan_raises_when_llm_unavailable` | Memastikan task tidak membuat hasil palsu saat LLM mati. | Mock `shared.llm` error |
| `test_process_penipuan_writes_metadata` | Memastikan output sukses ditulis ke `metadata["penipuan_result"]`. | Mock `shared.llm` dan mock search |
| `test_shared_celery_registers_agent_penipuan_task` | Memastikan `agent_penipuan.tasks` terdaftar di Celery shared. | Tidak ada |
| `test_shared_searcher_supports_current_serpapi_client` | Memastikan `shared.searcher` kompatibel dengan package `serpapi` yang terpasang sekarang. | Mock `serpapi` |
| `test_penipuan_search_filters_irrelevant_official_results` | Memastikan search Agent Penipuan membuang hasil resmi yang tidak relevan dan hanya menyimpan sumber yang nyambung. | Mock `shared.searcher` |
| `test_excalidraw_agent_1_documents_target_url_check_pipeline` | Memastikan diagram Agent 1 mendokumentasikan desain target tool check URL, Playwright, dan semantic similarity. | Tidak ada |
| `test_shared_llm_supports_deepseek_openai_compatible_api` | Memastikan `shared.llm` bisa memanggil DeepSeek API yang kompatibel dengan format OpenAI chat completions. | Mock `httpx.post` |
| `test_markdown_docs_describe_current_agent_scope` | Memastikan dokumentasi menyebut LLM, `shared.searcher`, scope tanpa database, dan error tanpa fallback. | Tidak ada |

## Compile Check

```bash
PYTHONDONTWRITEBYTECODE=1 python -m compileall agent_penipuan shared tests/test_agent_penipuan.py
```

Tujuannya memastikan file Python bisa di-import/compile setelah perubahan struktur.

## Smoke Test Dengan LLM Aktif

```bash
python - <<'PY'
from agent_penipuan.tasks import analyze_text

result = analyze_text(
    "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
    report_id="demo-001",
    search_results=[],
    url_check_results=[],
)

print(result.model_dump())
PY
```

Jika LLM tidak aktif, command ini akan error. Itu perilaku yang diharapkan.

Smoke test di atas tidak menjalankan web search atau URL checker karena memakai `search_results=[]` dan `url_check_results=[]`. Untuk mencoba mode pipeline normal dengan search resmi dan URL checker, pastikan `.env` memiliki `SERPAPI_KEY` dan konfigurasi LLM, lalu panggil tanpa parameter tersebut.

```python
result = analyze_text(
    "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
    report_id="demo-001",
)
```

Mode normal membutuhkan:

- `LLM_API_KEY`
- `LLM_MODEL`
- `SERPAPI_KEY`
- `URL_CHECK_BROWSER` jika ingin memaksa Firefox/Chromium

## Yang Tidak Diuji di Unit Test

- Koneksi real ke provider LLM.
- Koneksi real ke SerpAPI.
- Scraping isi URL laporan lewat network sungguhan.
- Playwright/browser rendering.
- Konfigurasi browser Firefox/Chromium untuk URL checker.
- CLIP untuk screenshot/logo halaman.
- Semantic similarity berbasis embedding antara halaman laporan dan sumber resmi.
- Dispatch dari webhook/input handler ke task `agent_penipuan.process`.
- Agent Validator dan Agent Broadcaster.

Bagian itu berada di integration test atau end-to-end test pipeline.
