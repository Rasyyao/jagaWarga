from agent_penipuan.tasks import analyze_text

result = analyze_text(
    "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
    report_id="demo-001",
    search_results=[],
)

print(result.model_dump())
