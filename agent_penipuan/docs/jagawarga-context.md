# JagaWarga Agent Penipuan Context

Dokumen ini mencatat konteks teknis singkat untuk bagian **Agent Penipuan dan Phishing**.

## Posisi Target di Pipeline

```text
Agent Input Handler
  -> intent: laporan_penipuan
  -> agent_penipuan.process
  -> Agent Validator
  -> Agent Broadcaster
```

Input ke agent berupa teks. Jika laporan berasal dari gambar, OCR dilakukan lebih dulu di `agent_input_handler`.

Folder `agent_penipuan` hanya menyediakan task `agent_penipuan.process`. Dispatch dari input handler/orchestrator ke task ini berada di luar scope agent.

File diagram: `pipeline-lks-ai.excalidraw`. Bagian Agent 1 di diagram adalah desain target. Implementasi saat ini sudah memuat versi awal tool check URL, tetapi belum memuat CLIP/screenshot matching dan semantic similarity embedding.

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
```

Struktur ini sengaja mengikuti `agent_hoaks` dan `agent_pengaduan`.

## Flow Agent

Flow implementasi saat ini:

```text
PipelineContext
  -> ambil context.extracted_text atau context.message.raw_text
  -> extract_urls
  -> extract_rule_indicators
  -> search_penipuan memakai shared.searcher.web_search
  -> check_urls membuka URL laporan jika ada link
  -> reason_penipuan memakai shared.llm.call_llm ke DeepSeek API sebagai LLM reasoning
  -> context.metadata["penipuan_result"]
```

Flow target Agent 1:

```text
PipelineContext
  -> ambil text/link
  -> extract_urls + extract_rule_indicators
  -> tool check URL untuk membuka URL laporan
  -> scraping konten halaman/redirect/form
  -> search sumber resmi
  -> semantic similarity dengan sumber resmi
  -> opsional CLIP untuk screenshot/logo halaman
  -> LLM klasifikasi final
  -> context.metadata["penipuan_result"]
```

## Prinsip Implementasi

- Tidak memakai database di agent.
- Tidak menjalankan microservice sendiri.
- Tidak membuat keputusan final hanya dari rule-based jika LLM error.
- Rule-based hanya menjadi indikator awal untuk LLM.
- Search memakai `shared.searcher` untuk referensi resmi.
- Tool check URL berbeda dari search: tool itu membuka URL laporan warga dan menganalisis isi halaman.
- Playwright target bisa dikonfigurasi memakai Firefox atau Chromium.
- Jika Playwright/browser tidak tersedia, URL checker fallback ke HTTP client.
- CLIP hanya menjadi sinyal tambahan untuk visual/screenshot/logo, bukan pengganti scraping teks.
- Konfigurasi search memakai `SERPAPI_KEY`.
- Konfigurasi URL checker memakai `URL_CHECK_BROWSER`, `URL_CHECK_HEADLESS`, `URL_CHECK_TIMEOUT_MS`, `URL_CHECK_MAX_TEXT_CHARS`, dan `URL_CHECK_USE_LLM`.
- Konfigurasi LLM memakai DeepSeek API: `LLM_PROVIDER=deepseek`, `LLM_BASE_URL=https://api.deepseek.com`, `LLM_API_KEY`, dan `LLM_MODEL`.
- Output memakai schema `PenipuanResult`.
- Jika LLM error, agent ikut error dan tidak mengarang hasil dari rule indicator.

## Output Minimal

```json
{
  "agent": "fraud_phishing",
  "report_id": "message-id",
  "status": "confirmed_fraud",
  "fraud_type": "credential_phishing",
  "confidence": 0.86,
  "risk_level": "critical",
  "indicators": {
    "has_url": false,
    "asks_for_otp": true,
    "asks_for_nik_kk": false,
    "asks_for_pin_password": true,
    "asks_for_transfer": false,
    "uses_urgency": true,
    "impersonates_institution": "bank"
  },
  "evidence": [],
  "reasoning": "Alasan singkat berbasis bukti.",
  "next_action": "validator"
}
```
