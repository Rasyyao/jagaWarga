import os
import re
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from agent_penipuan.schemas import UrlCheckResult
from shared.utils import safe_json_parse


SENSITIVE_FIELD_PATTERNS = {
    "nik": re.compile(r"\bnik\b|nomor induk kependudukan|ktp", re.IGNORECASE),
    "kk": re.compile(r"\bkk\b|kartu keluarga", re.IGNORECASE),
    "otp": re.compile(r"\botp\b|kode verifikasi", re.IGNORECASE),
    "pin": re.compile(r"\bpin\b|password|kata sandi|cvv", re.IGNORECASE),
    "phone": re.compile(r"nomor telepon|no\.?\s*hp|whatsapp|wa\b|phone", re.IGNORECASE),
    "address": re.compile(r"\balamat\b|domisili", re.IGNORECASE),
    "bank_account": re.compile(r"rekening|nomor rekening|atas nama", re.IGNORECASE),
}

GOVERNMENT_CONTEXT_PATTERN = re.compile(
    r"\b(bansos|kip|pemerintah|kemensos|kemendikbud|kemdikbud|dukcapil|bpjs|"
    r"pajak|polri|ojk|kominfo|komdigi|pln|bumn|bank indonesia)\b",
    re.IGNORECASE,
)

TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.input_parts: list[str] = []
        self.links: list[str] = []
        self.description: str | None = None
        self.form_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            meta_name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if meta_name in {"description", "og:description"} and attrs_dict.get("content"):
                self.description = attrs_dict["content"]
        elif tag == "a" and attrs_dict.get("href") and len(self.links) < 25:
            self.links.append(attrs_dict["href"])
        elif tag == "form":
            self.form_count += 1
        elif tag in {"input", "textarea", "select"}:
            values = [
                tag,
                attrs_dict.get("type", ""),
                attrs_dict.get("name", ""),
                attrs_dict.get("id", ""),
                attrs_dict.get("placeholder", ""),
                attrs_dict.get("aria-label", ""),
            ]
            self.input_parts.append(" ".join(value for value in values if value))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        if data.strip():
            self.text_parts.append(data)


def check_urls(urls: Iterable[str], official_results: list[dict[str, str]] | None = None) -> list[UrlCheckResult]:
    results = []
    for url in urls:
        results.append(check_url(url, official_results or []))
    return results


def check_url(url: str, official_results: list[dict[str, str]] | None = None) -> UrlCheckResult:
    try:
        snapshot = _scrape_url(url)
    except Exception as exc:
        return UrlCheckResult(
            original_url=url,
            final_url=None,
            domain=_domain_from_url(url),
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    content_for_detection = " ".join(
        [
            snapshot.get("title", ""),
            snapshot.get("description", ""),
            snapshot.get("visible_text", ""),
            " ".join(snapshot.get("input_signals", [])),
        ]
    )
    sensitive_fields = _detect_sensitive_fields(content_for_detection)
    similarity_score = _official_similarity_score(snapshot, official_results or [])
    verdict = "unknown"
    risk_score: float | None = None
    reasoning: str | None = None

    if _env_bool("URL_CHECK_USE_LLM", True):
        llm_result = _judge_url_with_llm(snapshot, sensitive_fields, similarity_score)
        verdict = _valid_verdict(llm_result.get("verdict"))
        risk_score = _clamp_score(llm_result.get("risk_score"))
        reasoning = _optional_text(llm_result.get("reasoning"))

    return UrlCheckResult(
        original_url=url,
        final_url=snapshot.get("final_url"),
        domain=snapshot.get("domain"),
        status="checked",
        verdict=verdict,
        risk_score=risk_score,
        title=_optional_text(snapshot.get("title")),
        description=_optional_text(snapshot.get("description")),
        has_form=bool(snapshot.get("has_form")),
        sensitive_fields=sensitive_fields,
        similarity_score=similarity_score,
        reasoning=reasoning,
    )


def _scrape_url(url: str) -> dict[str, Any]:
    browser = os.getenv("URL_CHECK_BROWSER", "firefox").lower().strip()
    if browser in {"firefox", "chromium", "webkit"}:
        try:
            return _scrape_with_playwright(url, browser)
        except Exception:
            return _scrape_with_httpx(url)
    return _scrape_with_httpx(url)


def _scrape_with_httpx(url: str) -> dict[str, Any]:
    timeout_seconds = _env_int("URL_CHECK_TIMEOUT_MS", 15000) / 1000
    response = httpx.get(
        url,
        follow_redirects=True,
        headers={"User-Agent": "JagaWarga-AgentPenipuan/1.0"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    parsed = _parse_html(response.text)
    final_url = str(response.url)
    return {
        "original_url": url,
        "final_url": final_url,
        "domain": _domain_from_url(final_url),
        "status_code": response.status_code,
        **parsed,
    }


def _scrape_with_playwright(url: str, browser_name: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    timeout_ms = _env_int("URL_CHECK_TIMEOUT_MS", 15000)
    headless = _env_bool("URL_CHECK_HEADLESS", True)
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        browser = browser_type.launch(headless=headless)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 3000))
            except Exception:
                pass
            title = page.title()
            visible_text = page.locator("body").inner_text(timeout=2000)
            input_signals = page.locator("input, textarea, select").evaluate_all(
                """
                els => els.slice(0, 50).map(el => [
                  el.tagName,
                  el.type || '',
                  el.name || '',
                  el.id || '',
                  el.placeholder || '',
                  el.getAttribute('aria-label') || ''
                ].filter(Boolean).join(' '))
                """
            )
            html_snapshot = _parse_html(page.content())
            final_url = page.url
            return {
                "original_url": url,
                "final_url": final_url,
                "domain": _domain_from_url(final_url),
                "title": _normalize_whitespace(title) or html_snapshot.get("title"),
                "description": html_snapshot.get("description"),
                "visible_text": _limit_text(visible_text),
                "input_signals": input_signals or html_snapshot.get("input_signals", []),
                "links": html_snapshot.get("links", []),
                "has_form": bool(input_signals) or bool(html_snapshot.get("has_form")),
            }
        finally:
            browser.close()


def _parse_html(html: str) -> dict[str, Any]:
    parser = _PageParser()
    parser.feed(html)
    return {
        "title": _normalize_whitespace(" ".join(parser.title_parts)),
        "description": _normalize_whitespace(parser.description or ""),
        "visible_text": _limit_text(_normalize_whitespace(" ".join(parser.text_parts))),
        "input_signals": [_normalize_whitespace(value) for value in parser.input_parts if value.strip()],
        "links": parser.links,
        "has_form": parser.form_count > 0 or bool(parser.input_parts),
    }


def _judge_url_with_llm(
    snapshot: dict[str, Any],
    sensitive_fields: list[str],
    similarity_score: float | None,
) -> dict[str, Any]:
    from shared.llm import call_llm

    response = call_llm(
        messages=[
            {
                "role": "system",
                "content": """
Kamu adalah URL checker untuk Agent Penipuan JagaWarga.
Nilai hanya berdasarkan fakta hasil scraping URL laporan. Jangan mengarang isi halaman.
Jika fakta tidak cukup, gunakan verdict unknown atau suspicious dengan reasoning singkat.
Output HANYA JSON:
{"verdict":"phishing|suspicious|legit|unknown","risk_score":0.0,"reasoning":"alasan singkat"}
""",
            },
            {
                "role": "user",
                "content": _json_payload(
                    {
                        "original_url": snapshot.get("original_url"),
                        "final_url": snapshot.get("final_url"),
                        "domain": snapshot.get("domain"),
                        "title": snapshot.get("title"),
                        "description": snapshot.get("description"),
                        "text_sample": snapshot.get("visible_text"),
                        "has_form": snapshot.get("has_form"),
                        "input_signals": snapshot.get("input_signals", []),
                        "detected_sensitive_fields": sensitive_fields,
                        "official_similarity_score": similarity_score,
                        "locale": "id-ID",
                    }
                ),
            },
        ],
        temperature=0.1,
    )
    parsed = safe_json_parse(response)
    if not parsed:
        raise ValueError("LLM URL checker tidak mengembalikan JSON valid")
    return parsed


def _official_similarity_score(
    snapshot: dict[str, Any],
    official_results: list[dict[str, str]],
) -> float | None:
    page_text = " ".join(
        [
            snapshot.get("title", ""),
            snapshot.get("description", ""),
            snapshot.get("visible_text", ""),
        ]
    )
    if not official_results or not GOVERNMENT_CONTEXT_PATTERN.search(page_text):
        return None

    page_tokens = _tokens(page_text)
    if not page_tokens:
        return None

    best_score = 0.0
    for result in official_results:
        reference_text = " ".join([result.get("title", ""), result.get("snippet", "")])
        reference_tokens = _tokens(reference_text)
        if not reference_tokens:
            continue
        intersection = len(page_tokens & reference_tokens)
        union = len(page_tokens | reference_tokens)
        best_score = max(best_score, intersection / union if union else 0.0)
    return round(best_score, 4) if best_score else 0.0


def _detect_sensitive_fields(text: str) -> list[str]:
    fields = [name for name, pattern in SENSITIVE_FIELD_PATTERNS.items() if pattern.search(text)]
    return sorted(set(fields))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text) if len(token) > 2}


def _domain_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc.lower() or None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _limit_text(value: str) -> str:
    max_chars = _env_int("URL_CHECK_MAX_TEXT_CHARS", 6000)
    return value[:max_chars]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _valid_verdict(value: Any) -> str:
    if value in {"phishing", "suspicious", "legit", "unknown"}:
        return str(value)
    return "unknown"


def _clamp_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_payload(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)
