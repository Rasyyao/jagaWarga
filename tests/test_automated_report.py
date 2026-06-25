"""
Test script for automated_report.py - run step by step.

Usage (from jagaWarga/ folder):
    python tests/test_automated_report.py --step login
    python tests/test_automated_report.py --step captcha
    python tests/test_automated_report.py --step form
    python tests/test_automated_report.py --step full
"""

import asyncio
import argparse
import sys
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

LAPORGUB_URL = "https://laporgub.jatengprov.go.id"
SESSION_FILE = Path(__file__).parent.parent / "agent_pengaduan/services/.laporgub_session.json"
SCREENSHOT_DIR = Path(__file__).parent.parent / "scripts/screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


async def test_login():
    print("\n=== TEST: Login ===")
    from agent_pengaduan.services.automated_report import _login

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{LAPORGUB_URL}/login")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_login_page.png"))
        print("Screenshot saved: 01_login_page.png")

        success = await _login(context)
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_after_login.png"))
        print(f"Screenshot saved: 02_after_login.png")
        print(f"Login result: {'SUCCESS' if success else 'FAILED'}")
        print(f"Current URL: {page.url}")

        if success:
            print(f"Session saved to: {SESSION_FILE}")

        await browser.close()


async def test_captcha():
    print("\n=== TEST: Captcha Solving ===")
    from agent_pengaduan.services.automated_report import _solve_captcha

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{LAPORGUB_URL}/login")
        await page.wait_for_load_state("networkidle")

        captcha_el = page.locator("img[src*='/captcha/']")
        await captcha_el.wait_for()

        captcha_bytes = await captcha_el.screenshot()
        with open(SCREENSHOT_DIR / "captcha.png", "wb") as f:
            f.write(captcha_bytes)
        print("Captcha screenshot saved: scripts/screenshots/captcha.png")
        print("(Open this file to see what the captcha looks like)")

        result = await _solve_captcha(page)
        print(f"Captcha solved: '{result}'")

        await browser.close()


async def test_form():
    print("\n=== TEST: Form Filling (no submit) ===")

    if not SESSION_FILE.exists():
        print("ERROR: No session file found. Run --step login first.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(SESSION_FILE))

        page = await context.new_page()
        await page.goto(f"{LAPORGUB_URL}/buat-aduan")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_form_page.png"))
        print(f"Current URL: {page.url}")
        print("Screenshot saved: 03_form_page.png")

        if "/login" in page.url:
            print("ERROR: Session expired. Run --step login first.")
            await browser.close()
            return

        print("Session valid, on form page")

        # Fill step 1: Aduan
        print("\n--- Filling Step 1: Aduan ---")

        isi_aduan = "TEST: Jalan berlubang di Jalan Pandanaran, Semarang Tengah. Sudah berbahaya untuk pengendara."
        test_image_path = SCREENSHOT_DIR / "03_form_page.png"

        # Test lampiran (pakai screenshot yang sudah ada)
        try:
            await page.set_input_files("#hidden-input", str(test_image_path))
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(SCREENSHOT_DIR / "04a_lampiran_filled.png"))
            print(f"Lampiran uploaded: OK ({test_image_path.name})")
        except Exception as e:
            print(f"ERROR uploading lampiran: {e}")

        try:
            quill_editor = page.locator("#aduan-editor .ql-editor")
            await quill_editor.wait_for()
            await quill_editor.click()
            await quill_editor.fill(isi_aduan)
            await page.evaluate(
                "(text) => { document.getElementById('aduan').value = text; }",
                isi_aduan
            )
            await page.screenshot(path=str(SCREENSHOT_DIR / "04_isi_filled.png"))
            print("Isi aduan filled: OK")
        except Exception as e:
            print(f"ERROR filling isi_aduan: {e}")

        try:
            # Select2 with AJAX search - click dropdown, type, wait for results, click first option
            await page.click(".select2-container--tailwind, .select2-selection, [aria-labelledby*='lokasi']")
            await page.wait_for_timeout(500)

            select2_search = page.locator(".select2-search__field, input.select2-search__field")
            await select2_search.wait_for()
            await select2_search.fill("Semarang Tengah")

            await page.wait_for_selector(".select2-results__option:not(.select2-results__option--disabled)", timeout=5000)

            options = await page.locator(".select2-results__option").all()
            option_texts = [await o.text_content() for o in options[:5]]
            print(f"Lokasi options found: {option_texts}")

            await page.locator(".select2-results__option").first.click()
            await page.screenshot(path=str(SCREENSHOT_DIR / "05_lokasi_filled.png"))
            print("Lokasi filled: OK")
        except Exception as e:
            print(f"ERROR filling lokasi: {e}")

        try:
            await page.select_option("#jenis", "1")
            print("Jenis aduan set to Public: OK")
        except Exception as e:
            print(f"ERROR setting jenis: {e}")

        await page.screenshot(path=str(SCREENSHOT_DIR / "06_form_filled.png"))
        print("\nScreenshot saved: 06_form_filled.png")
        print("Inspect screenshots to verify form filling is correct.")
        print("NOT submitting - test stopped before submit.")

        input("\nPress Enter to close browser...")
        await browser.close()


async def test_full():
    print("\n=== TEST: Full End-to-End (ACTUAL SUBMISSION) ===")
    print("WARNING: This will submit a real report to LaporGub Jateng!")
    confirm = input("Type 'yes' to continue: ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    from agent_pengaduan.services.automated_report import submit_report, ReportPayload

    payload = ReportPayload(
        isi_aduan="Di beberapa lampu merah di daerah Sokaraja, masih ada beberapa pengamen. Mohon ditindaklanjuti.",
        lokasi_aduan="Sokaraja",
        jenis_aduan="Public",
    )

    print("Submitting report...")
    result = await submit_report(payload)

    print(f"\nResult:")
    print(f"  Success: {result.success}")
    print(f"  Ticket:  {result.ticket_number}")
    print(f"  Error:   {result.error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["login", "captcha", "form", "full"], required=True)
    args = parser.parse_args()

    steps = {
        "login": test_login,
        "captcha": test_captcha,
        "form": test_form,
        "full": test_full,
    }

    asyncio.run(steps[args.step]())
