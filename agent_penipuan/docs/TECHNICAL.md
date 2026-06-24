# Technical Notes Agent Penipuan

## Tujuan

`agent_penipuan` menganalisis laporan penipuan/phishing setelah input handler atau orchestrator menentukan laporan masuk ke kategori penipuan.

Input utama adalah teks. Jika user mengirim gambar, OCR dilakukan di `agent_input_handler`; agent ini tidak memproses gambar langsung.

Folder ini hanya menyediakan task `agent_penipuan.process` dan helper lokal. Routing dari webhook/input handler ke task agent berada di luar scope agent.

Diagram pipeline ada di `docs/pipeline-lks-ai.excalidraw`. Bagian Agent 1 di diagram adalah desain target. Implementasi saat ini sudah memuat versi awal `tool check URL`; indikator awal, hasil URL checker, dan hasil pencarian resmi dikirim ke LLM DeepSeek untuk klasifikasi final.

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
    TESTING.md
```

Peran file:

- `tasks.py`: entrypoint Celery dan helper `analyze_text`.
- `schemas.py`: `PenipuanResult`, `FraudIndicators`, `EvidenceItem`, `UrlCheckResult`.
- `services/indicators.py`: ekstraksi URL dan indikator awal.
- `services/url_checker.py`: resolve shortlink/redirect, scraping URL laporan, deteksi field sensitif, similarity ringan, dan LLM URL verdict.
- `services/web_searcher.py`: pencarian sumber resmi memakai `shared.searcher.web_search`.
- `services/reasoning_engine.py`: prompt LLM, parsing JSON, validasi enum, dan mapping ke `PenipuanResult`.

## Flow

Flow implementasi saat ini:

```text
process_penipuan(context_dict)
  -> ambil text
  -> analyze_text(text, report_id)
  -> extract_urls(text)
  -> extract_rule_indicators(text, urls)
  -> search_penipuan([text])
  -> check_urls(urls, official_results)
  -> reason_penipuan(...)
  -> context.metadata["penipuan_result"]
```

Mapping implementasi saat ini ke kode:

- `Ekstraksi indikator awal` -> `services/indicators.py`
- `Tool check URL` -> `services/url_checker.py`
- `Web Search resmi (shared.searcher)` -> `services/web_searcher.py`
- `LLM klasifikasi` -> `services/reasoning_engine.py`
- `Output status/fraud_type/confidence/evidence` -> `schemas.py`

Tidak ada model khusus fraud yang dilatih di folder ini. Keputusan klasifikasi dilakukan oleh LLM DeepSeek lewat `shared.llm.call_llm`.

## Desain Target Excalidraw

Pada diagram, **Tool check URL** berarti tool yang bekerja pada URL laporan warga, bukan hanya web search sumber resmi.

Implementasi awal tool check URL:

- Mendeteksi URL dari laporan warga.
- Mengikuti redirect dari shortlink seperti `bit.ly`.
- Membuka halaman tujuan dengan Playwright jika tersedia, lalu fallback ke HTTP client jika browser tidak tersedia/gagal.
- Mengambil `final_url`, domain, title, meta description, teks halaman, link keluar, dan sinyal form/input.
- Mendeteksi permintaan data sensitif seperti NIK, KK, OTP, PIN, password, nomor telepon, alamat, atau rekening.
- Meminta LLM DeepSeek memberi verdict URL: `phishing`, `suspicious`, `legit`, atau `unknown`.
- Menghitung semantic similarity ringan berbasis token overlap ketika konten halaman berbau layanan pemerintah.
- Menghasilkan evidence dari isi halaman yang benar-benar diambil dari URL laporan.

Konfigurasi URL checker:

- `URL_CHECK_BROWSER=firefox|chromium`
- `URL_CHECK_HEADLESS=true|false`
- `URL_CHECK_TIMEOUT_MS=15000`
- `URL_CHECK_MAX_TEXT_CHARS=6000`
- `URL_CHECK_USE_LLM=true|false`

Firefox bisa dipakai sebagai browser utama jika environment menyediakan binary/browser Playwright Firefox. Chromium tetap berguna sebagai fallback karena umumnya paling stabil untuk scraping headless.

Peran LLM pada tool check URL:

- Playwright/HTTP client hanya mengambil fakta halaman.
- LLM DeepSeek menilai fakta tersebut: apakah halaman meminta data sensitif, menyerupai instansi resmi, memakai domain mencurigakan, atau berisi alur phishing.
- Evidence harus berasal dari fakta hasil scraping, bukan tebakan LLM saja.

Peran CLIP:

- CLIP relevan jika pipeline mengambil screenshot halaman atau gambar/logo.
- CLIP bisa dipakai untuk membandingkan screenshot/logo halaman phishing dengan tampilan/logo instansi resmi.
- CLIP bukan pengganti scraping teks; ia menjadi sinyal tambahan untuk kasus halaman yang visualnya meniru situs resmi.

Semantic similarity saat ini:

- Search sumber resmi tetap dipakai untuk mengambil referensi dari domain seperti OJK, Komdigi/Kominfo, BI, Polri, bank, atau situs pemerintah terkait.
- Konten dari URL laporan dibandingkan dengan title/snippet sumber resmi memakai token overlap sederhana.
- Jika tidak ada sumber resmi yang relevan, pipeline harus jujur menyatakan tidak ada sumber resmi relevan.
- URL resmi tidak boleh dijadikan evidence hanya karena domainnya whitelist; isi sumber harus relevan dengan laporan.

Yang belum diimplementasikan:

- Embedding semantic similarity production-grade.
- CLIP/screenshot/logo matching.
- Penyimpanan screenshot atau cache hasil scraping.
- WHOIS/domain age.

## Schema

`PenipuanResult` berisi:

- `agent`
- `report_id`
- `status`
- `fraud_type`
- `confidence`
- `risk_level`
- `indicators`
- `evidence`
- `reasoning`
- `next_action`

Status valid:

- `confirmed_fraud`
- `suspicious`
- `confirmed_legit`
- `unverified`

Fraud type valid:

- `transfer_scam`
- `pinjol_ilegal`
- `fake_giveaway`
- `account_takeover`
- `credential_phishing`
- `malware_link`
- `unknown`

## Indikator Awal

`extract_rule_indicators` hanya membuat sinyal awal untuk konteks LLM, bukan keputusan final.

Sinyal yang dicari:

- URL.
- OTP.
- NIK/KTP/KK.
- PIN/password/CVV.
- Transfer/rekening.
- Urgency.
- Impersonasi institusi.

## Search

`search_penipuan` memakai `shared.searcher.web_search` dengan whitelist domain resmi seperti OJK, Komdigi/Kominfo, BI, Polri, dan beberapa bank besar.

Hasil search difilter lagi oleh Agent Penipuan. Domain resmi saja tidak cukup; title/snippet hasil search harus relevan dengan isi laporan. Jika tidak ada hasil yang cukup relevan, `official_search_results` dikirim kosong ke LLM.

Evidence `official_search` hanya dibuat jika hasil search punya konten berguna. URL resmi yang kosong, generic, atau tidak nyambung tidak dimasukkan sebagai evidence.

Konfigurasi search memakai `SERPAPI_KEY` dari `.env`.

Search ini berbeda dari target `tool check URL`. Search mencari referensi resmi; tool check URL membuka dan menganalisis URL yang dilaporkan warga.

## URL Checker

`check_urls(urls, official_results)` mengembalikan list `UrlCheckResult`.

Field utama:

- `original_url`: URL yang muncul di laporan.
- `final_url`: URL setelah redirect/shortlink.
- `domain`: domain final.
- `status`: `checked` atau `failed`.
- `verdict`: `phishing`, `suspicious`, `legit`, atau `unknown`.
- `risk_score`: skor dari LLM URL checker.
- `has_form`: apakah halaman punya form/input.
- `sensitive_fields`: field sensitif yang terdeteksi dari teks/form.
- `similarity_score`: skor token overlap terhadap hasil search resmi jika konteksnya layanan pemerintah.
- `reasoning`: alasan singkat dari LLM URL checker.
- `error`: pesan error jika scraping gagal.

Jika scraping URL gagal, agent tidak mengarang isi halaman. `UrlCheckResult.status` menjadi `failed` dan reasoning final mendapat konteks bahwa URL tidak berhasil dicek.

## LLM Reasoning

`reason_penipuan` memanggil `shared.llm.call_llm` dan meminta output JSON.

Jika response kosong atau bukan JSON valid, fungsi akan raise error.

Agent tidak membuat keputusan dari rule-based saja saat LLM error.

Konfigurasi LLM memakai DeepSeek API dari `.env`:

- `LLM_PROVIDER=deepseek`
- `LLM_BASE_URL=https://api.deepseek.com`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_MAX_TOKENS`

Payload yang dikirim ke LLM berisi:

- `report_id`
- `report_text`
- `urls`
- `rule_indicators`
- `url_check_results`
- `official_search_results`
- `official_search_summary`
- `locale`

## Database

Agent ini tidak menggunakan database. State pipeline dibawa lewat `PipelineContext.metadata`.
