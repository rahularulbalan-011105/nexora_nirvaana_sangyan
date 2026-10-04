"""Batch Analysis: check several messages, links, images and PDFs at once.

POST /api/batch                multipart: label, messages, links, files[] (+ file_texts[])
GET  /api/batch/{id}           progress + items of the signed-in user's job (404 otherwise)
POST /api/batch/{id}/journal   save a summary of a finished job to the user's journal
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.deps import DbDep, RequireUser, ThrottleApi, verify_csrf
from app.models.enums import JobStatus
from app.page_context import batch as ctx
from app.page_context.check_a_message import status_meta
from app.services import batch as service
from app.services import analysis_inputs as inputs
from app.services import i18n, jobs, ui_translate
from app.templating import resolve_language, templates

router = APIRouter(prefix="/api/batch", tags=["batch"])

PROCESS_TARGET = "app.services.batch:process_job"


def _error(code: str, message: str, status_code: int = 422) -> JSONResponse:
    return JSONResponse({"detail": message, "code": code}, status_code=status_code)


def _render_results(request: Request, user, view: dict) -> str:
    language = resolve_language(request, user)
    html = templates.get_template("pages/_batch_results.html").render(
        {"t": i18n.translator(language), "lang_code": language, **view}
    )
    if language != i18n.DEFAULT_LANGUAGE:
        html = ui_translate.translate_html(html, language)
    return html


@router.post("", dependencies=[Depends(verify_csrf), ThrottleApi])
async def create_batch(
    request: Request,
    db: DbDep,
    user: RequireUser,
    label: str = Form(""),
    messages: str = Form(""),
    links: str = Form(""),
    files: list[UploadFile] | None = File(None),
    file_texts: list[str] | None = Form(None),
):
    texts = service.split_messages(messages)
    urls = service.split_links(links)
    uploads = [f for f in (files or []) if f is not None and (f.filename or f.size)]
    file_texts = file_texts or []
    count = len(texts) + len(urls) + len(uploads)
    if count == 0:
        return _error("empty", "Please add at least one message, link, image or PDF.")
    if count > service.MAX_ITEMS:
        return _error(
            "too_many", f"A batch can hold up to {service.MAX_ITEMS} items. You added {count}."
        )

    prepared: list[service.PreparedItem] = []
    limit = inputs.max_bytes()
    try:
        n = 0
        for text in texts:
            n += 1
            prepared.append(service.prepare_text(text, n))
        for url in urls:
            n += 1
            prepared.append(service.prepare_link(url, n))
        for index, upload in enumerate(uploads):
            n += 1
            data = await upload.read(limit + 1)
            typed = file_texts[index] if index < len(file_texts) else ""
            # OCR (when installed) and PDF parsing are CPU-bound; keep the event loop free.
            prepared.append(
                await run_in_threadpool(
                    service.prepare_file, data, upload.filename or "", upload.content_type or "", typed, n
                )
            )
        job = service.create_job(
            db, user, prepared, label=label, language=resolve_language(request, user)
        )
    except service.BatchError as exc:
        db.rollback()
        return _error(exc.code, str(exc))

    db.commit()
    jobs.enqueue(PROCESS_TARGET, str(job.id))
    return {"id": str(job.id), "status": job.status, "total": job.total_items}


@router.get("/{job_id}", dependencies=[ThrottleApi])
def batch_status(job_id: str, request: Request, db: DbDep, user: RequireUser):
    job = ctx.own_job(db, user, job_id)
    if job is None:
        return _error("not_found", "That batch could not be found.", 404)
    view = ctx.job_view(db, user, job)
    return {
        "id": str(job.id),
        "label": job.label,
        "status": job.status,
        "running": view["batch_running"],
        "total": job.total_items,
        "completed": job.completed_items,
        "failed": job.failed_items,
        "progress": job.progress_percent,
        "counts": view["batch_counts"],
        "items": [
            {
                "position": item["obj"].position,
                "name": item["name"],
                "status": item["obj"].status,
                "result_status": item["result"],
                "error": item["error"],
            }
            for item in view["batch_items"]
        ],
        "html": _render_results(request, user, view),
    }


@router.post("/{job_id}/journal", dependencies=[Depends(verify_csrf), ThrottleApi])
def save_to_journal(job_id: str, request: Request, db: DbDep, user: RequireUser):
    from app.models.reflection import JournalEntry

    job = ctx.own_job(db, user, job_id)
    if job is None:
        return _error("not_found", "That batch could not be found.", 404)
    if job.status not in service.TERMINAL:
        return _error("not_finished", "This batch is still being analysed. Please wait until it finishes.", 409)

    view = ctx.job_view(db, user, job)
    counts = view["batch_counts"]
    title = "Batch check: " + (job.label or f"{counts['total']} items")
    lines = [
        f"Items checked: {counts['total']}",
        f"No obvious warning signals: {counts['clean']}",
        f"Needs verification: {counts['verify']}",
        f"Multiple warning signals: {counts['multiple']}",
    ]
    if job.failed_items:
        lines.append(f"Could not be analysed: {job.failed_items}")
    lines.append("")
    for item in view["batch_items"]:
        if item["result"]:
            outcome = status_meta(item["result"])["label"]
        elif item["obj"].status == JobStatus.FAILED.value:
            outcome = "Could not be analysed"
        else:
            outcome = "Not analysed"
        lines.append(f"{item['obj'].position + 1}. {item['name']}: {outcome}")
    entry = JournalEntry(
        user_id=user.id,
        title=title[:200],
        body="\n".join(lines),
        language=resolve_language(request, user),
    )
    db.add(entry)
    db.commit()
    return {"saved": True, "journal_id": str(entry.id)}
