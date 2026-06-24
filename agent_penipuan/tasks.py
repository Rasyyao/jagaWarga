from agent_penipuan.schemas import PenipuanResult, UrlCheckResult
from agent_penipuan.services.indicators import extract_rule_indicators, extract_urls
from agent_penipuan.services.reasoning_engine import reason_penipuan
from agent_penipuan.services.url_checker import check_urls
from agent_penipuan.services.web_searcher import search_penipuan
from shared.celery_app import celery_app
from shared.enums import PipelineStatus
from shared.schemas import PipelineContext


@celery_app.task(name="agent_penipuan.process")
def process_penipuan(context_dict: dict) -> dict:
    context = PipelineContext(**context_dict)
    context.status = PipelineStatus.PROCESSING

    text = context.extracted_text or context.message.raw_text or ""
    if not text.strip():
        context.status = PipelineStatus.FAILED
        context.metadata["error"] = "No text to process"
        return context.model_dump()

    result = analyze_text(text, report_id=context.message.message_id)

    context.status = PipelineStatus.COMPLETED
    context.metadata["penipuan_result"] = result.model_dump()
    return context.model_dump()


def analyze_text(
    text: str,
    *,
    report_id: str,
    search_results: list[dict[str, str]] | None = None,
    url_check_results: list[UrlCheckResult | dict] | None = None,
    run_url_check: bool = True,
) -> PenipuanResult:
    urls = extract_urls(text)
    indicators = extract_rule_indicators(text, urls)
    results = search_results if search_results is not None else search_penipuan([text])
    url_checks = _build_url_checks(urls, results, url_check_results, run_url_check)
    return reason_penipuan(
        report_id=report_id,
        text=text,
        urls=urls,
        indicators=indicators,
        search_results=results,
        url_check_results=url_checks,
    )


def _build_url_checks(
    urls: list[str],
    search_results: list[dict[str, str]],
    provided_results: list[UrlCheckResult | dict] | None,
    run_url_check: bool,
) -> list[UrlCheckResult]:
    if provided_results is not None:
        return [item if isinstance(item, UrlCheckResult) else UrlCheckResult(**item) for item in provided_results]
    if not run_url_check or not urls:
        return []
    return check_urls(urls, search_results)
