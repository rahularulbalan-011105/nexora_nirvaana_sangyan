"""Check a Message: analyse text, a link, an image or a PDF; reopen past results.

POST /api/check            multipart: mode=text|link|image|pdf (+ text / url / file / typed_text)
GET  /api/check/{id}       a past result of the signed-in user, as the result-card HTML
POST /api/check/{id}/journal   save a summary of a stored result to the user's journal
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.deps import DbDep, RequireUser, ThrottleApi, verify_csrf
from app.models.analysis import MessageAnalysis
from app.models.enums import InputKind
from app.page_context import check_a_message as ctx
from app.services import analysis as engine
from app.services import analysis_inputs as inputs
from app.services import i18n, ui_translate
from app.templating import resolve_language, templates

router = APIRouter(prefix="/api/check", tags=["check"])

MODES = {"text": InputKind.TEXT, "link": InputKind.URL, "image": InputKind.IMAGE, "pdf": InputKind.PDF}


def _error(code: str, message: str, status_code: int = 422) -> JSONResponse:
    # ``code`` lets the page show its own (translated) wording for the message.
    return JSONResponse({"detail": message, "code": code}, status_code=status_code)


def _render(request: Request, user, macro: str, *args) -> str:
    language = resolve_language(request, user)
    module = templates.env.get_template("pages/_check_result.html").make_module(
        {"t": i18n.translator(language), "lang_code": language}
    )
    html = str(getattr(module, macro)(*args))
    if language != i18n.DEFAULT_LANGUAGE:
        html = ui_translate.translate_html(html, language)
    return html


def _privacy(user) -> tuple[bool, bool]:
    p = user.privacy
    store_history = True if p is None else bool(p.store_analysis_history)
    store_files = False if p is None else bool(p.store_uploaded_files)
    return store_history, store_files


async def _read_upload(file: UploadFile | None) -> bytes:
    if file is None:
        return b""
    limit = inputs.max_bytes()
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise inputs.InputError(f"The file is larger than {inputs.settings.max_upload_mb} MB.")
    return data


@router.post("", dependencies=[Depends(verify_csrf), ThrottleApi])
async def check(
    request: Request,
    db: DbDep,
    user: RequireUser,
    mode: str = Form("text"),
    text: str = Form(""),
    url: str = Form(""),
    typed_text: str = Form(""),
    file: UploadFile | None = File(None),
):
    kind = MODES.get((mode or "").lower())
    if kind is None:
        return _error("bad_mode", "Please choose what you want to check.")
    language = resolve_language(request, user)
    store_history, store_files = _privacy(user)
    data = engine.CheckInput(kind=kind.value)
    upload_bytes = b""
    upload_type = ""

    try:
        if kind is InputKind.TEXT:
            data.text = (text or "").strip()
            if not data.text:
                return _error("empty_text", "Please paste or type the message you want to check.")
            if len(data.text) > engine.MAX_TEXT_CHARS:
                return _error("too_long", "That message is too long. Please check up to 10,000 characters at a time.")

        elif kind is InputKind.URL:
            problem = engine.validate_url(url)
            if problem:
                return _error("bad_url", problem)
            data.url = url.strip()

        elif kind is InputKind.IMAGE:
            upload_bytes = await _read_upload(file)
            if not upload_bytes:
                return _error("no_file", "Please choose an image to check.")
            upload_type = inputs.validate_image(upload_bytes)
            typed = (typed_text or "").strip()
            if inputs.ocr_available():
                ocr_text, conf = inputs.run_ocr(upload_bytes)
                data.ocr_used = True
                data.ocr_confidence = conf
                data.ocr_text = ocr_text
                data.text = typed or ocr_text
                if not data.text:
                    return _error("no_image_text", "No text could be read from this image. Please type the text you see in it.")
            else:
                if not typed:
                    return _error("need_typed", "Automatic text reading is not available. Please type the text you see in the image.")
                data.text = typed
                data.notes.append(
                    "Automatic text reading (OCR) is not available, so only the text you typed "
                    "from the image was checked. The image itself was not analysed."
                )
            if len(data.text) > engine.MAX_TEXT_CHARS:
                return _error("too_long", "That message is too long. Please check up to 10,000 characters at a time.")

        elif kind is InputKind.PDF:
            upload_bytes = await _read_upload(file)
            if not upload_bytes:
                return _error("no_file", "Please choose a PDF to check.")
            text_out, pages = inputs.extract_pdf_text(upload_bytes)
            upload_type = "application/pdf"
            if not text_out.strip():
                return _error(
                    "pdf_no_text",
                    "We could not find any text in this PDF. It may be a scanned image. "
                    "You can type the important lines in the Text Snippet tab instead.",
                )
            data.text = text_out
            if pages > inputs.MAX_PDF_PAGES or len(text_out) >= inputs.MAX_EXTRACT_CHARS:
                data.notes.append("This PDF is long, so only its first part was checked.")
    except inputs.InputError as exc:
        return _error("bad_file", str(exc))

    if upload_bytes and store_history:
        row = inputs.record_upload(
            db, user,
            data=upload_bytes,
            filename=(file.filename if file else "") or "upload",
            content_type=upload_type,
            kind=kind.value,
            keep_bytes=store_files,
        )
        data.uploaded_file_id = row.id

    analysis = engine.analyse(db, user, data, language=language, persist=store_history)
    if store_history:
        db.commit()

    view = ctx.analysis_view(analysis)
    scan_count = int(
        db.execute(
            select(func.count()).select_from(MessageAnalysis).where(MessageAnalysis.user_id == user.id)
        ).scalar() or 0
    )
    return {
        "id": str(analysis.id) if store_history else None,
        "stored": store_history,
        "status": analysis.status,
        "text": analysis.source_url or analysis.text_for_display,
        "kind_label": view["kind_label"],
        "html": _render(request, user, "result_card", view, store_history),
        "row_html": _render(request, user, "history_row", ctx.history_item(analysis)) if store_history else None,
        "scan_count": scan_count,
    }


def _own_analysis(db, user, analysis_id: str) -> MessageAnalysis | None:
    try:
        key = uuid.UUID(analysis_id)
    except ValueError:
        return None
    return db.execute(
        select(MessageAnalysis).where(MessageAnalysis.id == key, MessageAnalysis.user_id == user.id)
    ).scalar_one_or_none()


@router.get("/{analysis_id}", dependencies=[ThrottleApi])
def past_result(analysis_id: str, request: Request, db: DbDep, user: RequireUser):
    analysis = _own_analysis(db, user, analysis_id)
    if analysis is None:
        return _error("not_found", "That check could not be found.", 404)
    view = ctx.analysis_view(analysis)
    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "text": analysis.source_url or analysis.text_for_display,
        "kind_label": view["kind_label"],
        "html": _render(request, user, "result_card", view, True),
    }


@router.post("/{analysis_id}/journal", dependencies=[Depends(verify_csrf), ThrottleApi])
def save_to_journal(analysis_id: str, db: DbDep, user: RequireUser):
    from app.models.reflection import JournalEntry
    from app.page_context import _activity as act

    analysis = _own_analysis(db, user, analysis_id)
    if analysis is None:
        return _error("not_found", "That check could not be found.", 404)
    meta = ctx.status_meta(analysis.status)
    title = ctx.KIND_TITLE.get(analysis.input_kind, "Checked a message") + ": " + meta["label"]
    lines = [
        "Content: " + act.snippet(analysis.source_url or analysis.text_for_display, 300),
        "",
        "What we detected: " + (analysis.what_we_detected or ""),
    ]
    if analysis.what_to_verify:
        lines += ["", "What to verify:", analysis.what_to_verify]
    entry = JournalEntry(
        user_id=user.id,
        title=title[:200],
        body="\n".join(lines),
        language=analysis.detected_language or "en",
    )
    db.add(entry)
    db.commit()
    return {"saved": True, "journal_id": str(entry.id)}
