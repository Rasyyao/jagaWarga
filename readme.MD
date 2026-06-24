# 🛡️ JagaWarga — Agent Input Handler

> Sistem multi-agent AI untuk verifikasi hoaks, deteksi penipuan, dan pengaduan layanan publik via WhatsApp.
> Dibangun untuk **LKS Nasional Eksibisi AI 2026**.

---

## 📋 Daftar Isi

- [Overview](#overview)
- [Arsitektur](#arsitektur)
- [Tech Stack](#tech-stack)
- [Struktur Project](#struktur-project)
- [Setup Development](#setup-development)
- [Menjalankan Project](#menjalankan-project)
- [Flow Pengguna](#flow-pengguna)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Environment Variables](#environment-variables)

---

## Overview

JagaWarga adalah sistem multi-agent AI yang memungkinkan warga melaporkan penipuan, hoaks, dan pengaduan layanan publik melalui WhatsApp. Sistem ini menggunakan IndoBERT yang di-fine-tune untuk klasifikasi intent bahasa Indonesia, dan memproses laporan secara asynchronous menggunakan Celery.

**Fitur utama:**
- 🤖 Intent classification dengan IndoBERT (fine-tuned)
- 📱 Integrasi WhatsApp via kirimi.id
- ⚡ Async processing dengan Celery + Redis
- 🔍 Semantic deduplication laporan
- 👥 Session management per user
- 🗄️ Vector storage dengan pgvector

---

## Arsitektur

```
User kirim WA
      ↓
kirimi.id Webhook
      ↓
FastAPI /webhook
      ↓
Session Manager
  /daftar → registrasi nama & alamat
  /start  → buka sesi laporan
  /end    → tutup sesi → dispatch ke pipeline
      ↓
[Redis Queue]
      ↓
Celery Worker — Agent Input Handler
  → Deteksi input type (MIME/regex URL)
  → Intent Classifier (IndoBERT fine-tuned)
  → Confidence Gate (drop spam/tidak relevan)
  → OCR via LLM (jika image)
  → Semantic Dedup (hash + cosine similarity)
  → LLM Router (klasifikasi tipe laporan)
      ↓
Dispatch ke Agent (via Celery group)
  → Agent Penipuan
  → Agent Hoaks
  → Agent Pengaduan
      ↓
Agent Validator → Agent Broadcaster
```

---

## Tech Stack

| Komponen | Teknologi |
|---|---|
| API | FastAPI + Uvicorn |
| Queue | Celery + Redis |
| NLP | IndoBERT (`indobenchmark/indobert-base-p1`) fine-tuned |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` |
| Vector DB | PostgreSQL + pgvector |
| WhatsApp | kirimi.id |
| Infra | Docker Compose + Nginx |
| Training | HuggingFace Trainer + MPS (Apple Silicon) |

---

## Struktur Project

```
jagawarga/
│
├── shared/                          # Shared code semua agent
│   ├── schemas.py                   # Pydantic schemas
│   ├── enums.py                     # Label & status enums
│   ├── config.py                    # Settings dari .env
│   ├── celery_app.py                # Celery instance
│   └── wa_client.py                 # kirimi.id API helper
│
├── agent_input_handler/             # Layer 1: terima & klasifikasi input
│   ├── main.py                      # FastAPI entry point
│   ├── api/
│   │   └── webhook.py               # POST /webhook (kirimi.id)
│   ├── services/
│   │   ├── input_detector.py        # MIME & URL detector
│   │   ├── intent_classifier.py     # IndoBERT inference
│   │   ├── ocr_service.py           # OCR via LLM
│   │   └── dedup_service.py         # Semantic deduplication
│   └── tasks.py                     # Celery pipeline orchestrator
│
├── agent_penipuan/                  # Layer 2a: analisis penipuan
├── agent_hoaks/                     # Layer 2b: verifikasi hoaks
├── agent_pengaduan/                 # Layer 2c: pengaduan layanan
├── agent_validator/                 # Layer 3: agregasi & verdict
├── agent_broadcaster/               # Layer 4: broadcast ke user
│
├── data/
│   └── intent_dataset.csv           # Dataset training IndoBERT (283 rows)
│
├── models/
│   └── indobert-intent/             # Fine-tuned model (git-ignored)
│
├── scripts/
│   └── train_classifier.py          # Script fine-tune IndoBERT
│
├── tests/
│   └── test_intent_classifier.py    # Test suite classifier
│
├── infra/
│   ├── docker-compose.yml           # Production
│   ├── docker-compose.dev.yml       # Development
│   ├── Dockerfile.api               # Image FastAPI
│   ├── Dockerfile.worker            # Image Celery worker
│   └── nginx.conf                   # Reverse proxy
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup Development

### 1. Clone repo

```bash
git clone https://github.com/username/jagawarga.git
cd jagawarga
```

### 2. Setup virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Setup environment variables

```bash
cp .env.example .env
# Edit .env dengan credentials kamu
```

### 4. Fine-tune IndoBERT

```bash
python scripts/train_classifier.py
# Model tersimpan di models/indobert-intent/
# Estimasi waktu: 5-10 menit (Apple Silicon MPS)
```

### 5. Jalankan infrastruktur

```bash
# Jalankan Redis + PostgreSQL
docker compose -f infra/docker-compose.dev.yml up redis postgres -d

# Cek status
docker compose -f infra/docker-compose.dev.yml ps
```

---

## Menjalankan Project

### Development (tanpa Docker)

```bash
# Terminal 1 — Celery worker
celery -A shared.celery_app.celery_app worker -Q pipeline,agents -c 2 -l info

# Terminal 2 — FastAPI
uvicorn agent_input_handler.main:app --reload --port 8000

# Terminal 3 — Expose ke internet (untuk kirimi.id webhook)
ngrok http 8000
```

### Development (dengan Docker)

```bash
docker compose -f infra/docker-compose.dev.yml up -d
```

### Production

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

---

## Flow Pengguna

```
User chat pertama kali
→ Bot: "Halo! Ketik /daftar untuk registrasi"

/daftar
→ Bot: "Ketik nama lengkap kamu"
→ User: "Budi Santoso"
→ Bot: "Ketik alamat kamu"
→ User: "Purwokerto Utara"
→ Bot: "Terdaftar! Ketik /start untuk laporan"

/start
→ Bot: "Sesi laporan dimulai! Kirim laporan kamu..."
→ User kirim teks / foto / link (boleh lebih dari satu)

/end
→ Bot: "Laporan diterima! Sedang diproses..."
→ Pipeline berjalan di background
→ Bot kirim hasil analisis
```

**Commands yang tersedia:**

| Command | Fungsi |
|---|---|
| `/daftar` | Registrasi nama & alamat |
| `/start` | Mulai sesi laporan |
| `/end` | Selesai & kirim laporan ke pipeline |
| `/status` | Cek status laporan terakhir |
| `/help` | Panduan penggunaan |

---

## API Endpoints

| Method | Endpoint | Fungsi |
|---|---|---|
| `POST` | `/webhook` | Terima pesan dari kirimi.id |
| `GET` | `/health` | Health check API + Celery |

### Contoh payload kirimi.id

```json
{
  "event": "message",
  "deviceId": "D-ABC123",
  "msgId": "3EB0A1B2C3D4E5F60718",
  "from": "6281234567890",
  "name": "Budi",
  "message": "ada penipuan transfer rekening palsu",
  "isFromGroup": false,
  "isFromMe": false,
  "messageType": "text",
  "mediaUrl": ""
}
```

---

## Testing

```bash
# Test intent classifier
python tests/test_intent_classifier.py
```

**Hasil test classifier (IndoBERT fine-tuned):**

| Label | Accuracy |
|---|---|
| laporan_penipuan | 100% |
| laporan_hoaks | 100% |
| laporan_pengaduan_layanan | 100% |
| tidak_relevan | 100% |
| spam | 100% |
| **Overall** | **100%** |

---

## Environment Variables

```env
# App
APP_ENV=development
DEBUG=true

# WhatsApp — kirimi.id
WA_PHONE_NUMBER_ID=your_device_id
WA_ACCESS_TOKEN=your_api_key
WA_VERIFY_TOKEN=your_verify_token

# Celery + Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://jagawarga:password@localhost:5432/jagawarga

# IndoBERT
CLASSIFIER_MODEL_PATH=./models/indobert-intent
CLASSIFIER_CONFIDENCE_THRESHOLD=0.35
CLASSIFIER_DROP_THRESHOLD=0.65

# LLM
LLM_PROVIDER=groq
LLM_API_KEY=your_groq_key
LLM_MODEL=llama-3.1-8b-instant
LLM_TIMEOUT=30

# OCR
OCR_PROVIDER=llm
```

---

## Author

**Naufal Qathafa Rasya Hidayat** — IntechCode Enterprise
SMK Telkom Purwokerto · LKS Nasional Eksibisi AI 2026