import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_input_handler.services.intent_classifier import classify_intent, should_drop
from shared.enums import IntentLabel


def assert_label(text: str, expected: IntentLabel):
    result = classify_intent(text)
    status = "✅" if result.label == expected else "❌"
    print(f"{status} [{result.label.value} | {result.confidence:.3f}] → '{text}'")
    if result.label != expected:
        print(f"   Expected: {expected.value}")
        print(f"   Scores  : {result.all_scores}")
    return result.label == expected


def test_penipuan():
    print("\n=== LAPORAN PENIPUAN ===")
    cases = [
        "ada yang minta transfer ke rekening tidak dikenal",
        "saya kena tipu belanja online barang tidak datang",
        "nomor asing minta kode OTP katanya dari bank",
        "investasi online minta deposit dulu baru untung",
        "dapat WA menang hadiah minta foto KTP",
        "pinjol ilegal ancam sebar data ke keluarga",
    ]
    results = [assert_label(t, IntentLabel.LAPORAN_PENIPUAN) for t in cases]
    score = sum(results)
    print(f"Score: {score}/{len(results)} | Accuracy: {score/len(results)*100:.1f}%")
    return score, len(results)


def test_hoaks():
    print("\n=== LAPORAN HOAKS ===")
    cases = [
        "ini berita benar tidak tolong cek",
        "foto viral ini asli atau hoaks",
        "video bencana ini dari mana aslinya",
        "informasi obat ini valid tidak ada sumbernya",
        "broadcast WA soal gempa besok beneran tidak",
        "berita artis meninggal ini hoaks atau bukan",
    ]
    results = [assert_label(t, IntentLabel.LAPORAN_HOAKS) for t in cases]
    score = sum(results)
    print(f"Score: {score}/{len(results)} | Accuracy: {score/len(results)*100:.1f}%")
    return score, len(results)


def test_pengaduan():
    print("\n=== LAPORAN PENGADUAN LAYANAN ===")
    cases = [
        "lampu jalan di RT saya mati sudah lama",
        "air tidak mengalir sudah 2 hari",
        "jalan depan sekolah rusak parah berlubang",
        "sampah belum diangkut sudah 4 hari bau",
        "listrik mati terus di kampung saya",
        "pelayanan kelurahan lambat dan dipersulit",
    ]
    results = [assert_label(t, IntentLabel.LAPORAN_PENGADUAN_LAYANAN) for t in cases]
    score = sum(results)
    print(f"Score: {score}/{len(results)} | Accuracy: {score/len(results)*100:.1f}%")
    return score, len(results)


def test_tidak_relevan():
    print("\n=== TIDAK RELEVAN ===")
    cases = [
        "halo selamat pagi",
        "makasih ya",
        "oke",
        "permisi numpang tanya",
        "test 123",
    ]
    results = [assert_label(t, IntentLabel.TIDAK_RELEVAN) for t in cases]
    score = sum(results)
    print(f"Score: {score}/{len(results)} | Accuracy: {score/len(results)*100:.1f}%")
    return score, len(results)


def test_spam():
    print("\n=== SPAM ===")
    cases = [
        "beli followers Instagram murah",
        "slot gacor hari ini maxwin",
        "obat kuat cod area jakarta",
        "jasa hack akun terpercaya",
    ]
    results = [assert_label(t, IntentLabel.SPAM) for t in cases]
    score = sum(results)
    print(f"Score: {score}/{len(results)} | Accuracy: {score/len(results)*100:.1f}%")
    return score, len(results)


def test_should_drop():
    print("\n=== CONFIDENCE GATE ===")
    cases_drop = [
        "halo",
        "beli followers murah",
        "oke siap",
    ]
    cases_pass = [
        "ada penipuan transfer rekening palsu",
        "foto ini hoaks atau bukan",
        "lampu jalan mati sudah seminggu",
    ]

    drop_results = []
    print("-- Harus di-drop:")
    for t in cases_drop:
        result = classify_intent(t)
        drop = should_drop(result)
        status = "✅ DROP" if drop else "❌ LOLOS (harusnya drop)"
        print(f"  {status} [{result.label.value} | {result.confidence:.3f}] → '{t}'")
        drop_results.append(drop)

    pass_results = []
    print("-- Harus lolos:")
    for t in cases_pass:
        result = classify_intent(t)
        drop = should_drop(result)
        status = "✅ LOLOS" if not drop else "❌ DROP (harusnya lolos)"
        print(f"  {status} [{result.label.value} | {result.confidence:.3f}] → '{t}'")
        pass_results.append(not drop)

    score = sum(drop_results) + sum(pass_results)
    total = len(drop_results) + len(pass_results)
    print(f"Score: {score}/{total} | Accuracy: {score/total*100:.1f}%")
    return score, total


if __name__ == "__main__":
    print("Loading model... (pertama kali agak lama)")

    scores = []
    scores.append(test_penipuan())
    scores.append(test_hoaks())
    scores.append(test_pengaduan())
    scores.append(test_tidak_relevan())
    scores.append(test_spam())
    scores.append(test_should_drop())

    # ── Overall accuracy ───────────────────────────────────────────────────────
    total_correct = sum(s[0] for s in scores)
    total_cases   = sum(s[1] for s in scores)
    overall_acc   = total_correct / total_cases * 100

    print("\n" + "="*50)
    print(f"  OVERALL ACCURACY: {total_correct}/{total_cases} ({overall_acc:.1f}%)")
    if overall_acc >= 90:
        print("  🟢 EXCELLENT — siap production")
    elif overall_acc >= 75:
        print("  🟡 GOOD — tambah data CSV untuk improve")
    else:
        print("  🔴 NEEDS IMPROVEMENT — tambah lebih banyak data")
    print("="*50)