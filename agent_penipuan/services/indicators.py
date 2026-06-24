import re

from agent_penipuan.schemas import FraudIndicators


URL_PATTERN = re.compile(
    r"https?://\S+|www\.\S+|(?<!@)\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?",
    re.IGNORECASE,
)

OTP_PATTERN = re.compile(r"\b(otp|one time password|kode verifikasi|kode rahasia)\b", re.IGNORECASE)
NIK_KK_PATTERN = re.compile(r"\b(nik|nomor induk kependudukan|ktp|kartu keluarga|\bkk\b)\b", re.IGNORECASE)
PIN_PASSWORD_PATTERN = re.compile(r"\b(pin|password|kata sandi|passcode|cvv)\b", re.IGNORECASE)
TRANSFER_PATTERN = re.compile(r"\b(transfer|rekening|tf|dana|ovo|gopay|shopeepay|virtual account|va)\b", re.IGNORECASE)
URGENCY_PATTERN = re.compile(
    r"\b(segera|urgent|hari ini|limited|terbatas|blokir|dibekukan|hangus|menang|hadiah|claim|klaim)\b",
    re.IGNORECASE,
)

INSTITUTIONS = {
    "bank": re.compile(r"\b(bca|bri|bni|mandiri|cimb|permata|bank)\b", re.IGNORECASE),
    "ojk": re.compile(r"\b(ojk|otoritas jasa keuangan)\b", re.IGNORECASE),
    "kurir": re.compile(r"\b(jne|jnt|j&t|sicepat|anteraja|pos indonesia|kurir|paket)\b", re.IGNORECASE),
    "pemerintah": re.compile(r"\b(komdigi|kominfo|dukcapil|pajak|polri|bpjs|pln)\b", re.IGNORECASE),
    "e-wallet": re.compile(r"\b(dana|ovo|gopay|linkaja|shopeepay)\b", re.IGNORECASE),
}


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.findall(text):
        url = match.rstrip(").,;]")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        urls.append(url)
    return list(dict.fromkeys(urls))


def extract_rule_indicators(text: str, urls: list[str]) -> FraudIndicators:
    combined = text or ""
    institution = None
    for name, pattern in INSTITUTIONS.items():
        if pattern.search(combined):
            institution = name
            break

    return FraudIndicators(
        has_url=bool(urls),
        asks_for_otp=bool(OTP_PATTERN.search(combined)),
        asks_for_nik_kk=bool(NIK_KK_PATTERN.search(combined)),
        asks_for_pin_password=bool(PIN_PASSWORD_PATTERN.search(combined)),
        asks_for_transfer=bool(TRANSFER_PATTERN.search(combined)),
        uses_urgency=bool(URGENCY_PATTERN.search(combined)),
        impersonates_institution=institution,
    )
