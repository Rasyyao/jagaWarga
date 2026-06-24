import httpx
from shared.config import get_settings

settings = get_settings()

def _base_payload() -> dict:
    return {
        "user_code": settings.KIRIMI_USER_CODE,
        "secret": settings.KIRIMI_ID_API_KEY,
        "device_id": settings.KIRIMI_DEVICE_ID,
    }

async def send_text_message(phone: str, message: str) -> dict:
    """
    Kirim pesan teks ke nomor WA.
    Pakai /v1/send-message (dengan efek mengetik)
    """
    payload = {
        **_base_payload(),
        "phone": phone,
        "message": message,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.KIRIMI_BASE_URL}/v1/send-message",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_text_fast(phone: str, message: str) -> dict:
    """
    Kirim pesan teks tanpa efek mengetik — lebih cepat.
    Cocok untuk ACK / notifikasi otomatis.
    """
    payload = {
        **_base_payload(),
        "phone": phone,
        "message": message,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.KIRIMI_BASE_URL}/v1/send-message-fast",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_media_message(phone: str, media_url: str, caption: str = "") -> dict:
    """
    Kirim pesan dengan media (gambar/file) via URL.
    """
    payload = {
        **_base_payload(),
        "phone": phone,
        "message": caption,
        "media_url": media_url,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.KIRIMI_BASE_URL}/v1/send-message",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def broadcast_message(phones: list[str], message: str, delay: int = 3) -> dict:
    """
    Broadcast pesan ke banyak nomor sekaligus.
    delay = jeda antar pesan dalam detik (default 3)
    Dipakai oleh agent_broadcaster.
    """
    payload = {
        **_base_payload(),
        "phones": ",".join(phones),   # pisah koma sesuai docs
        "message": message,
        "delay": delay,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.KIRIMI_BASE_URL}/v1/broadcast-message",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ── Default reply messages ─────────────────────────────────────────────────────
DEFAULT_REPLIES = {
    "tidak_relevan": (
        "Maaf, pesan kamu tidak dapat kami proses. "
        "Kamu bisa melaporkan: penipuan, hoaks, atau pengaduan layanan publik.\n\n"
        "Ketik /help untuk panduan."
    ),
    "spam": (
        "Pesan terdeteksi sebagai spam. "
        "Jika ini kesalahan, coba kirim ulang laporanmu dengan lebih detail."
    ),
    "ack": (
        "✅ Laporan kamu sudah kami terima dan sedang diproses.\n"
        "Kami akan menghubungi kamu kembali dengan hasilnya."
    ),
    "error": (
        "Maaf, terjadi kesalahan saat memproses pesan kamu. "
        "Silakan coba lagi."
    ),
}