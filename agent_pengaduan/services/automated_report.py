import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext

LAPORGUB_URL = "https://laporgub.jatengprov.go.id"
SESSION_FILE = Path(__file__).parent / ".laporgub_session.json"


@dataclass
class ReportPayload:
    isi_aduan: str
    lokasi_aduan: str
    jenis_aduan: str = "Public"
    lampiran_path: Optional[str] = None


@dataclass
class ReportResult:
    success: bool
    ticket_number: Optional[str] = None
    error: Optional[str] = None


async def _solve_captcha(page: Page) -> str:
    """Solve captcha using LLM vision. Uses desktop version (visible in headless browser)."""
    from shared.config import get_settings
    import httpx

    # Use desktop captcha image (visible in desktop viewport)
    await page.locator("#img-captcha-desktop").wait_for(state="visible", timeout=10000)
    b64 = base64.b64encode(await page.locator("#img-captcha-desktop").screenshot()).decode("utf-8")

    settings = get_settings()
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": "Read the captcha text in this image. Reply with ONLY the captcha text, nothing else. No spaces, no punctuation."},
                    ],
                }
            ],
            "max_tokens": 20,
        },
    )
    result = response.json()
    if "choices" not in result:
        raise ValueError(f"Groq captcha solve failed: {result}")
    return result["choices"][0]["message"]["content"].strip()


async def _fill_captcha(page: Page, captcha_text: str) -> None:
    """Fill both mobile and desktop captcha inputs."""
    for captcha_id in ["captcha", "captcha-desktop"]:
        await page.evaluate(f"""
            () => {{
                const el = document.getElementById('{captcha_id}');
                if (el) {{
                    el.value = '{captcha_text}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}
        """)


async def _dismiss_swal(page: Page) -> None:
    """Dismiss SweetAlert popup if present."""
    try:
        swal_confirm = page.locator(".swal2-confirm")
        if await swal_confirm.count() > 0:
            await swal_confirm.click()
            await page.wait_for_timeout(500)
    except Exception:
        pass


async def _login(context: BrowserContext) -> bool:
    """Login to LaporGub and save session. Returns True if successful."""
    from shared.config import get_settings
    settings = get_settings()

    if not settings.LAPORGUB_EMAIL or not settings.LAPORGUB_PASSWORD:
        raise ValueError("LAPORGUB_EMAIL and LAPORGUB_PASSWORD must be set in environment variables")

    page = await context.new_page()
    await page.goto(f"{LAPORGUB_URL}/login")
    await page.wait_for_load_state("networkidle")

    await page.fill("input[type='tel'], input[type='email']", settings.LAPORGUB_EMAIL)
    await page.fill("input[type='password']", settings.LAPORGUB_PASSWORD)

    # Login page uses #img-captcha (mobile layout), not desktop
    captcha_el = page.locator("#img-captcha, #img-captcha-desktop")
    await captcha_el.first.wait_for(state="attached", timeout=5000)
    b64 = base64.b64encode(await captcha_el.first.screenshot()).decode("utf-8")

    from shared.config import get_settings as gs
    import httpx
    s = gs()
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {s.LLM_API_KEY}"},
        json={
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "Read the captcha text. Reply ONLY with the captcha text, no spaces, no explanation."},
            ]}],
            "max_tokens": 20,
        },
    )
    login_captcha = resp.json()["choices"][0]["message"]["content"].strip()
    await page.fill("#captcha", login_captcha)
    await page.click("button[type='submit']")
    await page.wait_for_load_state("networkidle")

    if "/login" in page.url:
        await page.close()
        return False

    await context.storage_state(path=str(SESSION_FILE))
    await page.close()
    return True


async def _is_session_valid(context: BrowserContext) -> bool:
    page = await context.new_page()
    await page.goto(f"{LAPORGUB_URL}/buat-aduan")
    await page.wait_for_load_state("networkidle")
    is_valid = "/login" not in page.url
    await page.close()
    return is_valid


async def _fill_step1(page: Page, payload: ReportPayload) -> None:
    # Lampiran (optional)
    if payload.lampiran_path:
        await page.set_input_files("#hidden-input", payload.lampiran_path)
        await page.wait_for_timeout(500)

    # Isi Aduan via Quill editor
    quill_editor = page.locator("#aduan-editor .ql-editor")
    await quill_editor.wait_for(state="visible", timeout=10000)
    await quill_editor.click()
    await quill_editor.fill(payload.isi_aduan)
    # Sync to hidden textarea and trigger quill text-change event
    await page.evaluate("""
        (text) => {
            document.getElementById('aduan').value = text;
            if (window.quillEditor) {
                window.quillEditor.setText(text);
            }
        }
    """, payload.isi_aduan)

    # Lokasi - Select2 with AJAX search
    await page.click(".select2-container--tailwind, [aria-labelledby*='lokasi'], .select2-selection")
    await page.wait_for_timeout(500)
    select2_search = page.locator(".select2-search__field").first
    await select2_search.wait_for(state="visible", timeout=5000)
    await select2_search.fill(payload.lokasi_aduan)
    await page.wait_for_selector(
        ".select2-results__option:not(.select2-results__option--disabled):not(.select2-results__message)",
        timeout=5000
    )
    await page.locator(".select2-results__option").first.click()

    # Jenis Aduan
    jenis_value = "1" if payload.jenis_aduan.lower() == "public" else "0"
    await page.select_option("#jenis", jenis_value)

    # Submit step 1
    await page.locator("#btn-step1").click()
    await page.locator("#step2-content").wait_for(state="visible", timeout=15000)


async def _fill_step2(page: Page) -> None:
    """auto-filled from account"""
    await page.locator("#form-step2").wait_for(state="visible", timeout=10000)
    await page.locator("#form-step2 button[type='submit']").click()
    await page.locator("#step3-content").wait_for(state="visible", timeout=15000)


async def _submit_step3(page: Page) -> ReportResult:
    """Fill captcha and submit step 3. Retries up to 3 times on captcha failure."""
    await page.locator("#form-step3").wait_for(state="visible", timeout=10000)

    for attempt in range(3):
        # Wait for captcha image to fully load
        await page.locator("#img-captcha-desktop").wait_for(state="visible", timeout=10000)
        await page.wait_for_timeout(300)

        captcha_text = await _solve_captcha(page)
        await _fill_captcha(page, captcha_text)

        # Submit and wait for AJAX response
        await page.locator("#btn-step3").click()

        # Wait for either: success redirect, or error (captcha wrong)
        try:
            await page.wait_for_url(
                f"{LAPORGUB_URL}/aduan-berhasil/**",
                timeout=10000
            )
            # Extract ticket from URL
            ticket = page.url.split("/aduan-berhasil/")[-1].strip("/")
            return ReportResult(success=True, ticket_number=ticket if ticket else None)

        except Exception:
            # Not redirected - check if captcha error via SweetAlert or still on form
            await _dismiss_swal(page)
            await page.wait_for_timeout(500)

            # Check if we somehow landed on success page anyway
            if "/aduan-berhasil/" in page.url:
                ticket = page.url.split("/aduan-berhasil/")[-1].strip("/")
                return ReportResult(success=True, ticket_number=ticket if ticket else None)

            # Still on form - captcha failed, retry
            if attempt < 2:
                print(f"Captcha attempt {attempt + 1} failed ('{captcha_text}'), retrying...")
                # Wait for captcha to refresh
                await page.wait_for_timeout(1000)
            else:
                return ReportResult(success=False, error=f"Captcha failed after 3 attempts")

    return ReportResult(success=False, error="Captcha failed after 3 attempts")


async def submit_report(payload: ReportPayload) -> ReportResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Setup context with session if available
        if SESSION_FILE.exists():
            context = await browser.new_context(storage_state=str(SESSION_FILE))
            if not await _is_session_valid(context):
                await context.close()
                context = await browser.new_context()
                if not await _login(context):
                    await browser.close()
                    return ReportResult(success=False, error="Login failed")
        else:
            context = await browser.new_context()
            if not await _login(context):
                await browser.close()
                return ReportResult(success=False, error="Login failed")

        page = await context.new_page()

        try:
            await page.goto(f"{LAPORGUB_URL}/buat-aduan")
            await page.wait_for_load_state("networkidle")

            # Guard: session might have expired mid-flow
            if "/login" in page.url:
                await browser.close()
                return ReportResult(success=False, error="Session expired")

            await _fill_step1(page, payload)
            await _fill_step2(page)
            result = await _submit_step3(page)

            # Save updated session
            await context.storage_state(path=str(SESSION_FILE))
            return result

        except Exception as e:
            return ReportResult(success=False, error=str(e))

        finally:
            await page.close()
            await browser.close()
