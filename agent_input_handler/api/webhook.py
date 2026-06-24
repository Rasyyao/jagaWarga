from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional
from shared.config import get_settings
from shared.schemas import IncomingMessage
from shared.wa_client import send_text_message

router = APIRouter()
settings = get_settings()


# ── Kirimi.id payload schema ───────────────────────────────────────────────────
class KirimiPayload(BaseModel):
    event: str = ""
    deviceId: Optional[str] = None
    msgId: Optional[str] = None
    sender: str = Field("", alias="from")
    name: Optional[str] = None
    message: Optional[str] = None
    isFromGroup: bool = False
    isFromMe: bool = False
    messageType: str = "text"
    mediaUrl: Optional[str] = None
    senderAlt: Optional[str] = None
    originLid: Optional[str] = None
    datetime_wib: Optional[str] = None

    model_config = {"populate_by_name": True, "extra": "allow"}


# ── Session state ──────────────────────────────────────────────────────────────
_sessions: dict = {}


def get_session(wa_id: str) -> dict:
    if wa_id not in _sessions:
        _sessions[wa_id] = {
            "state": "new",
            "name": None,
            "address": None,
            "report_buffer": [],
        }
    return _sessions[wa_id]


# ── Command handler ────────────────────────────────────────────────────────────
async def handle_command(payload: KirimiPayload) -> str | None:
    wa_id = payload.sender
    text = (payload.message or "").strip()
    session = get_session(wa_id)

    if text == "/help":
        return (
            "📋 *Panduan JagaWarga*\n\n"
            "/daftar → Registrasi nama & alamat\n"
            "/start  → Mulai sesi laporan\n"
            "/end    → Selesai & kirim laporan\n"
            "/status → Cek status laporan terakhir\n"
            "/help   → Tampilkan panduan ini\n\n"
            "Kamu bisa kirim teks, foto, atau link sebagai laporan."
        )

    if text == "/daftar":
        session["state"] = "awaiting_name"
        return (
            "👋 Halo! Selamat datang di JagaWarga.\n\n"
            "Silakan isi biodata kamu:\n"
            "Ketik nama lengkap kamu sekarang 👇"
        )

    if session["state"] == "awaiting_name":
        session["name"] = text
        session["state"] = "awaiting_address"
        return (
            f"Terima kasih *{text}*! 😊\n\n"
            "Sekarang ketik alamat kamu (kelurahan/kecamatan) 👇"
        )

    if session["state"] == "awaiting_address":
        session["address"] = text
        session["state"] = "ready"
        return (
            f"✅ Biodata tersimpan!\n\n"
            f"Nama    : {session['name']}\n"
            f"Alamat  : {session['address']}\n\n"
            "Ketik /start untuk mulai membuat laporan."
        )

    if text == "/start":
        if session["state"] == "new":
            return "⚠️ Kamu belum terdaftar. Ketik /daftar dulu ya!"
        session["state"] = "in_report"
        session["report_buffer"] = []
        return (
            "📝 Sesi laporan dimulai!\n\n"
            "Silakan kirim laporan kamu sekarang.\n"
            "Bisa teks, foto, atau link.\n"
            "Boleh kirim lebih dari satu pesan.\n\n"
            "Ketik /end jika sudah selesai."
        )

    if text == "/end":
        if session["state"] != "in_report":
            return "⚠️ Kamu belum memulai laporan. Ketik /start dulu ya!"
        buffer = session["report_buffer"]
        if not buffer:
            return "⚠️ Laporan kosong! Kirim pesan dulu sebelum /end."
        session["state"] = "ready"
        session["report_buffer"] = []
        await dispatch_to_pipeline(wa_id, session, buffer)
        return (
            "✅ Laporan kamu sudah diterima!\n"
            "Sedang kami proses... 🔍\n\n"
            "Kami akan menghubungi kamu kembali dengan hasilnya."
        )

    if text == "/status":
        return "🔄 Fitur status laporan segera hadir!"

    return None


# ── Pipeline dispatcher ────────────────────────────────────────────────────────
async def dispatch_to_pipeline(wa_id: str, session: dict, buffer: list):
    all_texts = [item["text"] for item in buffer if item.get("text")]
    combined_text = " ".join(all_texts) if all_texts else None
    media_item = next((item for item in buffer if item.get("media_url")), None)

    incoming = IncomingMessage(
        message_id=f"batch-{wa_id}-{len(buffer)}",
        sender_wa_id=wa_id,
        sender_name=session.get("name"),
        raw_text=combined_text,
        media_id=media_item["media_url"] if media_item else None,
        media_mime_type="image/jpeg" if media_item else None,
    )

    incoming_dict = incoming.model_dump(mode="json")
    incoming_dict["metadata"] = {
        "address": session.get("address"),
        "buffer_count": len(buffer),
    }

    # Celery dispatch — uncomment setelah Celery jalan
    # from agent_input_handler.tasks import process_incoming_message
    # process_incoming_message.delay(incoming_dict)

    print("DISPATCH TO PIPELINE:", incoming_dict)


# ── Webhook endpoint ───────────────────────────────────────────────────────────
@router.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    print("PAYLOAD:", body)
    

    try:
        payload = KirimiPayload(**body)
    except Exception as e:
        print("PARSE ERROR:", e)
        return {"status": "ok"}
    

    if payload.sender == settings.WA_BOT_NUMBER:
        return {"status": "ignored"}

    if payload.event != "message":
        return {"status": "ignored"}

    wa_id = payload.sender
    if not wa_id:
        return {"status": "ignored"}

    session = get_session(wa_id)
    text = (payload.message or "").strip()

    # Cek command
    if text.startswith("/"):
        reply = await handle_command(payload)
        if reply:
            await send_text_message(wa_id, reply)
        return {"status": "ok"}

    # User belum daftar
    if session["state"] == "new":
        await send_text_message(
            wa_id,
            "👋 Halo! Selamat datang di *JagaWarga*.\n\n"
            "Ketik /daftar untuk registrasi\n"
            "Ketik /help untuk bantuan"
        )
        return {"status": "ok"}

    # Proses biodata
    if session["state"] in ("awaiting_name", "awaiting_address"):
        reply = await handle_command(payload)
        if reply:
            await send_text_message(wa_id, reply)
        return {"status": "ok"}

    # Kumpulkan pesan kalau in_report
    if session["state"] == "in_report":
        session["report_buffer"].append({
            "text": text if text else None,
            "media_url": payload.mediaUrl if payload.mediaUrl else None,
            "message_type": payload.messageType,
        })
        await send_text_message(
            wa_id,
            "📥 Pesan diterima! Lanjutkan atau ketik /end jika selesai."
        )
        return {"status": "ok"}

    # State ready
    if session["state"] == "ready":
        await send_text_message(
            wa_id,
            "Ketik /start untuk mulai laporan\n"
            "Ketik /help untuk bantuan"
        )
        return {"status": "ok"}

    return {"status": "ok"}