import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_input_handler.services.dedup_service import (
    check_duplicate,
    compute_hash,
    compute_embedding,
    cosine_similarity,
)


# ── Helper ─────────────────────────────────────────────────────────────────────
def print_result(label: str, result: dict):
    status = "✅ DUPLICATE" if result["is_duplicate"] else "🆕 UNIQUE"
    print(f"{status} | {label}")
    if result["is_duplicate"]:
        print(f"   match_type      : {result['match_type']}")
        print(f"   similar_to      : {result['similar_report_id']}")
        print(f"   similarity_score: {result['similarity_score']}")
    else:
        print(f"   cache_key       : {result['cache_key'][:16]}...")


# ── Test 1: Hash ───────────────────────────────────────────────────────────────
def test_compute_hash():
    print("\n=== TEST COMPUTE HASH ===")

    h1 = compute_hash("ada penipuan transfer rekening palsu")
    h2 = compute_hash("ada penipuan transfer rekening palsu")   # sama
    h3 = compute_hash("ADA PENIPUAN TRANSFER REKENING PALSU")  # uppercase
    h4 = compute_hash("hoaks vaksin covid berbahaya")           # beda

    print(f"{'✅' if h1 == h2 else '❌'} Teks sama → hash sama")
    print(f"{'✅' if h1 == h3 else '❌'} Case insensitive → hash sama")
    print(f"{'✅' if h1 != h4 else '❌'} Teks beda → hash beda")
    print(f"   Hash length: {len(h1)} chars (harusnya 64)")


# ── Test 2: Cosine similarity ──────────────────────────────────────────────────
def test_cosine_similarity():
    print("\n=== TEST COSINE SIMILARITY ===")
    print("Loading embedding model... (pertama kali agak lama)")

    # Kalimat mirip
    e1 = compute_embedding("ada penipuan transfer rekening palsu")
    e2 = compute_embedding("saya kena tipu transfer ke rekening tidak dikenal")
    e3 = compute_embedding("hoaks vaksin covid mengandung microchip")
    e4 = compute_embedding("ada penipuan transfer rekening palsu")  # identik sama e1

    s12 = cosine_similarity(e1, e2)
    s13 = cosine_similarity(e1, e3)
    s14 = cosine_similarity(e1, e4)

    print(f"{'✅' if s14 > 0.99 else '❌'} Identik     → similarity {s14:.4f} (harusnya ~1.0)")
    print(f"{'✅' if s12 > 0.70 else '❌'} Mirip       → similarity {s12:.4f} (harusnya > 0.7)")
    print(f"{'✅' if s13 < 0.70 else '❌'} Beda topik  → similarity {s13:.4f} (harusnya < 0.7)")


# ── Test 3: Exact duplicate ────────────────────────────────────────────────────
def test_exact_duplicate():
    print("\n=== TEST EXACT DUPLICATE ===")

    text = "ada penipuan transfer rekening BCA palsu minta OTP"
    report_id = "report-exact-001"

    # Pertama kali → unik
    start = time.time()
    result1 = check_duplicate(text, report_id)
    elapsed1 = round((time.time() - start) * 1000)
    print(f"{'✅' if not result1['is_duplicate'] else '❌'} Pertama kali → UNIQUE ({elapsed1}ms)")

    # Kedua kali → duplikat
    start = time.time()
    result2 = check_duplicate(text, "report-exact-002")
    elapsed2 = round((time.time() - start) * 1000)
    print(f"{'✅' if result2['is_duplicate'] else '❌'} Kedua kali → DUPLICATE ({elapsed2}ms)")
    print(f"   match_type: {result2.get('match_type')} (harusnya 'exact')")
    print(f"   score     : {result2.get('similarity_score')} (harusnya 1.0)")


# ── Test 4: Semantic duplicate ─────────────────────────────────────────────────
def test_semantic_duplicate():
    print("\n=== TEST SEMANTIC DUPLICATE ===")

    original = "lampu jalan di depan rumah saya mati sudah seminggu tidak diperbaiki"
    similar  = "penerangan jalan umum mati sudah lama tidak ada yang benerin"
    different = "ada penipuan transfer rekening bank palsu"

    # Simpan original dulu
    r1 = check_duplicate(original, "report-sem-001")
    print_result("Original (harus UNIQUE)", r1)

    # Cek yang mirip
    r2 = check_duplicate(similar, "report-sem-002")
    print_result("Similar (harusnya DUPLICATE)", r2)

    # Cek yang beda
    r3 = check_duplicate(different, "report-sem-003")
    print_result("Different (harusnya UNIQUE)", r3)


# ── Test 5: Multiple laporan berbeda ──────────────────────────────────────────
def test_multiple_unique():
    print("\n=== TEST MULTIPLE UNIQUE REPORTS ===")

    reports = [
        ("report-multi-001", "ada penipuan investasi bodong minta transfer dulu"),
        ("report-multi-002", "hoaks berita banjir jakarta ternyata foto lama"),
        ("report-multi-003", "jalan berlubang di jalan sudirman tidak diperbaiki"),
        ("report-multi-004", "sampah tidak diangkut sudah 4 hari menumpuk bau"),
        ("report-multi-005", "air PDAM tidak mengalir sudah 3 hari"),
    ]

    for report_id, text in reports:
        start = time.time()
        result = check_duplicate(text, report_id)
        elapsed = round((time.time() - start) * 1000)
        status = "✅ UNIQUE" if not result["is_duplicate"] else "⚠️  DUPLICATE"
        print(f"{status} ({elapsed}ms) → '{text[:50]}...'")


# ── Test 6: Performance ────────────────────────────────────────────────────────
def test_performance():
    print("\n=== TEST PERFORMANCE ===")

    text = "test performa dedup service dengan teks ini"

    # Exact match (hash lookup)
    check_duplicate(text, "perf-001")  # simpan dulu
    
    start = time.time()
    for _ in range(10):
        check_duplicate(text, "perf-test")
    elapsed = round((time.time() - start) * 1000)
    avg = elapsed / 10

    print(f"Exact match  : {avg:.1f}ms avg (10 runs)")
    status = "✅" if avg < 50 else "⚠️ "
    print(f"{status} Target < 50ms per lookup")


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Pastikan Redis sudah jalan:")
    print("docker compose -f infra/docker-compose.dev.yml up redis -d\n")

    try:
        test_compute_hash()
        test_cosine_similarity()
        test_exact_duplicate()
        test_semantic_duplicate()
        test_multiple_unique()
        test_performance()
        print("\n=== DONE ===")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Pastikan Redis sudah jalan!")
        import traceback
        traceback.print_exc()