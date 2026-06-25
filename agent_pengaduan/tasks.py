from shared.celery_app import celery_app
from shared.schemas import PipelineContext
from shared.enums import PipelineStatus
from agent_pengaduan.services.claim_extractor import extract_claim
from agent_pengaduan.services.web_searcher import search_complaint
from agent_pengaduan.services.report_generator import generate_report
from agent_pengaduan.services.automated_report import submit_report, ReportPayload
import asyncio


@celery_app.task(name="agent_pengaduan.process")
def process_pengaduan(context_dict: dict) -> dict:
    context = PipelineContext(**context_dict)
    context.status = PipelineStatus.PROCESSING

    text = context.extracted_text or ""
    if not text.strip():
        context.status = PipelineStatus.FAILED
        context.metadata["error"] = "No text to process"
        return context.model_dump()

    extraction = extract_claim(text)
    search_results = search_complaint(extraction.claims)
    result = generate_report(text, search_results)

    payload = ReportPayload(
        isi_aduan=result.laporan_text,
        lokasi_aduan=extraction.context,
    )
    submission = asyncio.run(submit_report(payload))

    context.status = PipelineStatus.COMPLETED
    context.metadata["pengaduan_result"] = result.model_dump()
    context.metadata["submission"] = {
        "success": submission.success,
        "ticket_number": submission.ticket_number,
        "error": submission.error,
    }

    return context.model_dump()
