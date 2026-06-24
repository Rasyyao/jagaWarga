import sys
import os
import json
import time
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_input_handler.services.ocr_service import extract_text, extract_text_from_url


async def test_ocr_folder(folder: str):
    print(f"\n=== TEST OCR semua gambar di {folder}/ ===")

    extensions = (".jpg", ".jpeg", ".png", ".webp")
    files = sorted([
        f for f in os.listdir(folder)
        if f.lower().endswith(extensions)
    ])

    if not files:
        print(f"❌ Tidak ada gambar di folder {folder}/")
        return

    print(f"Ditemukan {len(files)} gambar\n")

    json_results = []
    total_start = time.time()

    for fname in files:
        path = os.path.join(folder, fname)
        size_kb = os.path.getsize(path) / 1024

        with open(path, "rb") as f:
            image_bytes = f.read()

        start = time.time()
        try:
            text = await extract_text(image_bytes)
            elapsed = round((time.time() - start) * 1000)

            status = "✅" if text else "⚠️ "
            preview = f"{text[:80]}..." if len(text) > 80 else text
            print(f"{status} {fname} ({size_kb:.1f}KB) | {elapsed}ms")
            print(f"   {len(text)} chars → '{preview}'")

            json_results.append({
                "file": fname,
                "size_kb": round(size_kb, 1),
                "elapsed_ms": elapsed,
                "char_count": len(text),
                "text": text,
                "status": "ok" if text else "empty",
            })

        except Exception as e:
            elapsed = round((time.time() - start) * 1000)
            print(f"❌ {fname} ({size_kb:.1f}KB) | {elapsed}ms → ERROR: {e}")
            json_results.append({
                "file": fname,
                "size_kb": round(size_kb, 1),
                "elapsed_ms": elapsed,
                "char_count": 0,
                "text": "",
                "status": "error",
                "error": str(e),
            })

        print()

    total_elapsed = round((time.time() - total_start) * 1000)

    # ── Summary ────────────────────────────────────────────────────────────────
    success = sum(1 for r in json_results if r["status"] == "ok")
    empty   = sum(1 for r in json_results if r["status"] == "empty")
    errors  = sum(1 for r in json_results if r["status"] == "error")
    avg_ms  = round(sum(r["elapsed_ms"] for r in json_results) / len(json_results)) if json_results else 0

    print("=" * 50)
    print(f"  Total    : {len(files)} gambar")
    print(f"  Ada teks : {success}")
    print(f"  Kosong   : {empty}")
    print(f"  Error    : {errors}")
    print(f"  Avg time : {avg_ms}ms per gambar")
    print(f"  Total    : {total_elapsed}ms")
    print("=" * 50)

    # ── Save JSON ──────────────────────────────────────────────────────────────
    output = {
        "summary": {
            "total": len(files),
            "success": success,
            "empty": empty,
            "errors": errors,
            "avg_ms": avg_ms,
            "total_ms": total_elapsed,
        },
        "results": json_results,
    }

    out_path = os.path.join(os.path.dirname(__file__), "ocr_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Results saved → tests/ocr_results.json")
    return output


async def test_ocr_url():
    print("\n=== TEST OCR dari URL ===")
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Handwritten_Text.jpg/320px-Handwritten_Text.jpg"
    print(f"URL: {url}")

    start = time.time()
    try:
        text = await extract_text_from_url(url)
        elapsed = round((time.time() - start) * 1000)
        status = "✅" if text else "⚠️ "
        print(f"{status} {elapsed}ms → '{text[:100]}'")
    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        print(f"❌ {elapsed}ms → ERROR: {e}")


async def test_ocr_invalid():
    print("\n=== TEST OCR invalid bytes ===")
    try:
        await extract_text(b"ini bukan gambar")
        print("⚠️  Tidak ada error (Google Vision mungkin return empty)")
    except Exception as e:
        print(f"✅ Error caught: {type(e).__name__}: {str(e)[:80]}")


async def main():
    await test_ocr_invalid()
    await test_ocr_url()

    folder = sys.argv[1] if len(sys.argv) > 1 else "test_img"
    await test_ocr_folder(folder)

    print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())