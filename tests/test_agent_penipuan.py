from datetime import datetime
import os
from pathlib import Path
import sys
import types
from unittest import TestCase
from unittest.mock import patch

from agent_penipuan.schemas import UrlCheckResult
from agent_penipuan.services.indicators import extract_rule_indicators, extract_urls
from agent_penipuan.services.url_checker import check_url
from agent_penipuan.services.web_searcher import search_penipuan
from agent_penipuan.tasks import analyze_text, process_penipuan
from shared.enums import PipelineStatus
from shared.llm import call_llm
from shared.searcher import web_search
from shared.schemas import IncomingMessage, PipelineContext


class TestAgentPenipuan(TestCase):
    def test_extract_urls_normalizes_www_and_deduplicates(self) -> None:
        urls = extract_urls("Cek www.contoh.com, lalu https://bank-palsu.test/login.")

        self.assertEqual(urls, ["https://www.contoh.com", "https://bank-palsu.test/login"])

    def test_extract_urls_detects_bare_shortlink(self) -> None:
        urls = extract_urls("Registrasi bansos di bit.ly/bansospawaimbg sekarang.")

        self.assertEqual(urls, ["https://bit.ly/bansospawaimbg"])

    def test_rule_indicators_detect_sensitive_request(self) -> None:
        text = "Akun bank dibekukan. Segera kirim OTP, PIN, dan NIK untuk klaim."
        indicators = extract_rule_indicators(text, [])

        self.assertTrue(indicators.asks_for_otp)
        self.assertTrue(indicators.asks_for_pin_password)
        self.assertTrue(indicators.asks_for_nik_kk)
        self.assertTrue(indicators.uses_urgency)
        self.assertEqual(indicators.impersonates_institution, "bank")

    def test_analyze_text_returns_llm_result(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: """
        {
          "status": "suspicious",
          "fraud_type": "credential_phishing",
          "confidence": 0.78,
          "risk_level": "critical",
          "indicators": {"asks_for_otp": true, "asks_for_pin_password": true},
          "reasoning": "Pesan meminta OTP dan PIN untuk klaim hadiah.",
          "evidence": [{"type": "llm_reasoning", "title": "Indikator", "value": "Meminta OTP dan PIN"}]
        }
        """

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            result = analyze_text(
                "Selamat Anda menang hadiah bank. Segera kirim OTP dan PIN untuk klaim.",
                report_id="demo-001",
                search_results=[],
            )

        self.assertEqual(result.status, "suspicious")
        self.assertEqual(result.fraud_type, "credential_phishing")
        self.assertEqual(result.risk_level, "critical")
        self.assertTrue(result.indicators.asks_for_otp)
        self.assertTrue(result.indicators.asks_for_pin_password)
        self.assertEqual(result.next_action, "validator")

    def test_analyze_text_does_not_add_irrelevant_official_search_evidence(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: """
        {
          "status": "confirmed_fraud",
          "fraud_type": "credential_phishing",
          "confidence": 0.91,
          "risk_level": "high",
          "reasoning": "Tidak ada sumber resmi relevan, tetapi indikator phishing kuat.",
          "evidence": [
            {"type": "llm_reasoning", "title": "Indikator", "value": "Meminta NIK melalui tautan pendek."},
            {"type": "official_search", "title": "Sumber tidak valid", "value": "Harus diabaikan", "source_url": "https://example.com"}
          ]
        }
        """

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            result = analyze_text(
                "Ayo ambil bansos pendidikan di https://bit.ly/kipkindonesia2026, masukkan NIK.",
                report_id="demo-search",
                search_results=[
                    {
                        "url": "https://kontak157.ojk.go.id/appkpublicportal/website/articlelist/view/10001",
                        "title": "https://kontak157.ojk.go.id/appkpublicportal/websi...",
                        "snippet": "",
                    }
                ],
                url_check_results=[],
            )

        self.assertEqual([item.type for item in result.evidence], ["llm_reasoning"])

    def test_analyze_text_raises_when_llm_unavailable(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM offline"))

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            with self.assertRaises(RuntimeError):
                analyze_text(
                    "Cek hadiah palsu di https://bit.ly/contoh dan jangan bagikan NIK.",
                    report_id="demo-002",
                    search_results=[],
                    url_check_results=[],
                )

    def test_url_checker_uses_scraped_url_facts_and_llm(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: """
        {
          "verdict": "phishing",
          "risk_score": 0.93,
          "reasoning": "Halaman meminta NIK dan nomor telepon untuk klaim bansos."
        }
        """
        snapshot = {
            "original_url": "https://bit.ly/bansos-palsu",
            "final_url": "https://bansos-pendidikan.example/form",
            "domain": "bansos-pendidikan.example",
            "title": "Bansos Pendidikan",
            "description": "Klaim bantuan sekarang",
            "visible_text": "Masukkan NIK, nomor telepon, dan alamat untuk klaim KIP.",
            "input_signals": ["input text nik", "input tel nomor telepon", "textarea alamat"],
            "has_form": True,
        }

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            with patch("agent_penipuan.services.url_checker._scrape_url", return_value=snapshot):
                result = check_url(
                    "https://bit.ly/bansos-palsu",
                    [
                        {
                            "url": "https://kip-kuliah.kemdikbud.go.id",
                            "title": "KIP Kuliah",
                            "snippet": "Informasi resmi KIP dari pemerintah.",
                        }
                    ],
                )

        self.assertEqual(result.status, "checked")
        self.assertEqual(result.final_url, "https://bansos-pendidikan.example/form")
        self.assertEqual(result.verdict, "phishing")
        self.assertEqual(result.risk_score, 0.93)
        self.assertTrue(result.has_form)
        self.assertIn("nik", result.sensitive_fields)
        self.assertIn("phone", result.sensitive_fields)

    def test_url_checker_returns_failed_result_when_scrape_fails(self) -> None:
        with patch("agent_penipuan.services.url_checker._scrape_url", side_effect=RuntimeError("timeout")):
            result = check_url("https://bit.ly/error")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.domain, "bit.ly")
        self.assertIn("RuntimeError: timeout", result.error)

    def test_analyze_text_adds_url_check_evidence(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: """
        {
          "status": "confirmed_fraud",
          "fraud_type": "credential_phishing",
          "confidence": 0.89,
          "risk_level": "high",
          "reasoning": "URL checker menemukan halaman phishing.",
          "evidence": []
        }
        """
        url_check = UrlCheckResult(
            original_url="https://bit.ly/bansos-palsu",
            final_url="https://bansos-pendidikan.example/form",
            domain="bansos-pendidikan.example",
            verdict="phishing",
            risk_score=0.93,
            has_form=True,
            sensitive_fields=["nik", "phone"],
            reasoning="Halaman meminta NIK dan nomor telepon untuk klaim bansos.",
        )

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            result = analyze_text(
                "Ayo daftar bansos di https://bit.ly/bansos-palsu dan isi NIK.",
                report_id="demo-url-check",
                search_results=[],
                url_check_results=[url_check],
            )

        self.assertEqual(result.status, "confirmed_fraud")
        self.assertIn("url_check", [item.type for item in result.evidence])
        self.assertEqual(result.evidence[0].source_url, "https://bansos-pendidikan.example/form")

    def test_process_penipuan_raises_when_llm_unavailable(self) -> None:
        context = PipelineContext(
            message=IncomingMessage(
                message_id="msg-error",
                sender_wa_id="628123456789",
                raw_text="Segera kirim OTP dan PIN untuk klaim hadiah bank.",
                received_at=datetime(2026, 6, 24),
            ),
            extracted_text=None,
            intent=None,
        )

        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM offline"))

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            with patch("agent_penipuan.tasks.search_penipuan", return_value=[]):
                with self.assertRaises(RuntimeError):
                    process_penipuan(context.model_dump())

    def test_process_penipuan_writes_metadata(self) -> None:
        fake_llm = types.ModuleType("shared.llm")
        fake_llm.call_llm = lambda *args, **kwargs: """
        {
          "status": "suspicious",
          "fraud_type": "credential_phishing",
          "confidence": 0.78,
          "risk_level": "critical",
          "indicators": {"asks_for_otp": true, "asks_for_pin_password": true},
          "reasoning": "Pesan meminta OTP dan PIN untuk klaim hadiah.",
          "evidence": []
        }
        """
        context = PipelineContext(
            message=IncomingMessage(
                message_id="msg-001",
                sender_wa_id="628123456789",
                raw_text="Segera kirim OTP dan PIN untuk klaim hadiah bank.",
                received_at=datetime(2026, 6, 24),
            ),
            extracted_text=None,
            intent=None,
        )

        with patch.dict(sys.modules, {"shared.llm": fake_llm}):
            with patch("agent_penipuan.tasks.search_penipuan", return_value=[]):
                output = process_penipuan(context.model_dump())

        self.assertEqual(output["status"], PipelineStatus.COMPLETED)
        self.assertIn("penipuan_result", output["metadata"])
        self.assertEqual(output["metadata"]["penipuan_result"]["status"], "suspicious")

    def test_shared_celery_registers_agent_penipuan_task(self) -> None:
        celery_app_source = Path("shared/celery_app.py").read_text()

        self.assertIn('"agent_penipuan.tasks"', celery_app_source)

    def test_shared_searcher_supports_current_serpapi_client(self) -> None:
        fake_serpapi = types.ModuleType("serpapi")

        class FakeResults:
            def as_dict(self):
                return {
                    "organic_results": [
                        {
                            "link": "https://www.ojk.go.id/waspada-investasi",
                            "title": "OJK Waspada Investasi",
                            "snippet": "Daftar informasi resmi OJK.",
                        },
                        {
                            "link": "https://example.com/tidak-resmi",
                            "title": "Tidak Resmi",
                            "snippet": "Tidak masuk whitelist.",
                        },
                    ]
                }

        fake_serpapi.search = lambda params: FakeResults()

        with patch.dict(os.environ, {"SERPAPI_KEY": "test-key"}):
            with patch.dict(sys.modules, {"serpapi": fake_serpapi}):
                results = web_search("penipuan otp", ["ojk.go.id"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://www.ojk.go.id/waspada-investasi")

    def test_penipuan_search_filters_irrelevant_official_results(self) -> None:
        with patch(
            "shared.searcher.web_search",
            return_value=[
                {
                    "url": "https://kontak157.ojk.go.id/appkpublicportal/website/articlelist/view/10001",
                    "title": "https://kontak157.ojk.go.id/appkpublicportal/websi...",
                    "snippet": "",
                },
                {
                    "url": "https://www.komdigi.go.id/berita/waspada-phishing-bansos",
                    "title": "Waspada phishing bansos dan pencurian NIK",
                    "snippet": "Masyarakat diminta waspada tautan palsu bansos yang meminta NIK.",
                },
            ],
        ):
            results = search_penipuan(
                [
                    "Ayo ambil bansos pendidikan sekarang di https://bit.ly/kipkindonesia2026 "
                    "tinggal masukan alamat, nomor telefon, dan NIK"
                ]
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://www.komdigi.go.id/berita/waspada-phishing-bansos")

    def test_excalidraw_agent_1_documents_target_url_check_pipeline(self) -> None:
        source = Path("agent_penipuan/docs/pipeline-lks-ai.excalidraw").read_text()

        self.assertIn("Agent 1 - Penipuan dan Phising", source)
        self.assertIn("LLM DeepSeek API", source)
        self.assertNotIn("SLM detection", source)
        self.assertIn("Tool check URL", source)
        self.assertIn("WHOIS", source)
        self.assertIn("Playwright", source)
        self.assertIn("CLIP", source)
        self.assertIn("Semantic similarity", source)
        self.assertIn("Output\\n(type, confidence, evidence)", source)

    def test_shared_llm_supports_deepseek_openai_compatible_api(self) -> None:
        fake_settings = types.SimpleNamespace(
            LLM_PROVIDER="deepseek",
            LLM_BASE_URL="https://api.deepseek.com",
            LLM_API_KEY="test-key",
            LLM_MODEL="deepseek-chat",
            LLM_TIMEOUT=30,
            LLM_MAX_TOKENS=4096,
        )

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"choices": [{"message": {"content": '{"status":"unverified"}'}}]}

        with patch("shared.llm.get_settings", return_value=fake_settings):
            with patch("shared.llm.httpx.post", return_value=FakeResponse()) as post:
                result = call_llm([{"role": "user", "content": "halo"}], temperature=0.2)

        self.assertEqual(result, '{"status":"unverified"}')
        post.assert_called_once()
        call_args = post.call_args
        self.assertEqual(call_args.args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(call_args.kwargs["json"]["model"], "deepseek-chat")

    def test_markdown_docs_describe_current_agent_scope(self) -> None:
        doc_paths = [
            Path("agent_penipuan/README.md"),
            Path("agent_penipuan/docs/TECHNICAL.md"),
            Path("agent_penipuan/docs/USAGE.md"),
            Path("agent_penipuan/docs/TESTING.md"),
            Path("agent_penipuan/docs/jagawarga-context.md"),
        ]
        docs = "\n".join(path.read_text() for path in doc_paths)

        self.assertIn("LLM", docs)
        self.assertIn("shared.searcher", docs)
        self.assertIn("tidak membuat keputusan", docs)
        self.assertIn("tidak punya database", docs)
