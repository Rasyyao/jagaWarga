from shared.celery_app import celery_app
from shared.schemas import PipelineContext
from shared.enums import PipelineStatus
from agent_hoaks.services.claim_extractor import extract_claim
from agent_hoaks.services.web_searcher import search_hoax
from agent_hoaks.services.reasoning_engine import reason_hoax


@celery_app.task(name="agent_hoaks.process")
def process_hoaks(context_dict: dict) -> dict:
    context = PipelineContext(**context_dict)
    context.status = PipelineStatus.PROCESSING

    text = context.extracted_text or ""
    if not text.strip():
        context.status = PipelineStatus.FAILED
        context.metadata["error"] = "No text to process"
        return context.model_dump()

    extraction = extract_claim(text)
    search_results = search_hoax(extraction.claims)
    result = reason_hoax(extraction.claims, search_results)

    context.status = PipelineStatus.COMPLETED
    context.metadata["hoaks_result"] = result.model_dump()

    return context.model_dump()
