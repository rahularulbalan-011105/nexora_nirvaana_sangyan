"""Batch Analysis: check up to 20 messages, links, images and PDFs in one go.

The request handler (``app.routers.feature_batch``) validates every item and
turns uploads into text up front, using the same honest rules as Check a
Message (PDF text layer only; OCR only when an engine is installed, otherwise
the text the user typed). Sensitive details are masked before anything is
written. The prepared inputs wait in ``BatchJob.summary["pending"]`` until
:func:`process_job` runs them through the existing engine
(``app.services.analysis.analyse``) and then removes them.

``process_job`` is safe to retry: it only touches items that are not finished,
claims each item before analysing it, and recomputes the counts from the items.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models.analysis import BatchItem, BatchJob, MessageAnalysis
from app.models.enums import AnalysisStatus, InputKind, JobStatus
from app.services import account
from app.services import analysis as engine
from app.services import analysis_inputs as inputs
from app.services import responsible_ai as rai

log = logging.getLogger("nirvaan.batch")

MAX_ITEMS = 20
MAX_LABEL_CHARS = 160
# A line holding only three or more dashes separates pasted messages.
SEPARATOR_RE = re.compile(r"^[ \t]*-{3,}[ \t]*$", re.MULTILINE)
# An item claimed by a worker that has not finished within this time is retried.
STALE_AFTER = timedelta(minutes=5)

TERMINAL = {JobStatus.COMPLETED.value, JobStatus.FAILED.value}
ITEM_FAILED_MESSAGE = "This item could not be analysed. Please try checking it on its own."
MISSING_INPUT_MESSAGE = "The content of this item is no longer available, so it could not be analysed."

KIND_WORD = {
    InputKind.TEXT.value: "Message",
    InputKind.URL.value: "Link",
    InputKind.IMAGE.value: "Image",
    InputKind.PDF.value: "PDF",
}


class BatchError(ValueError):
    """A user-facing reason the batch cannot be created."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class PreparedItem:
    """One validated item, already reduced to the text the engine will check."""

    kind: str
    text: str = ""
    url: str | None = None
    filename: str = ""
    notes: list[str] = field(default_factory=list)
    ocr_used: bool = False
    ocr_confidence: float | None = None
    ocr_text: str | None = None
    upload: bytes = b""
    content_type: str = ""


# ---------------------------------------------------------------------------
# Splitting and validating input
# ---------------------------------------------------------------------------


def split_messages(raw: str) -> list[str]:
    """Pasted messages, separated by a line of dashes. Empty parts are dropped."""
    return [part.strip() for part in SEPARATOR_RE.split(raw or "") if part.strip()]


def split_links(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def _too_long(n: int) -> BatchError:
    return BatchError(
        "too_long",
        f"Item {n} is too long. Please check up to 10,000 characters per item.",
    )


def prepare_text(text: str, n: int) -> PreparedItem:
    if len(text) > engine.MAX_TEXT_CHARS:
        raise _too_long(n)
    return PreparedItem(kind=InputKind.TEXT.value, text=text)


def prepare_link(url: str, n: int) -> PreparedItem:
    problem = engine.validate_url(url)
    if problem:
        raise BatchError("bad_url", f"Item {n}: {problem}")
    return PreparedItem(kind=InputKind.URL.value, url=url.strip())


def prepare_file(data: bytes, filename: str, content_type: str, typed_text: str, n: int) -> PreparedItem:
    """Validate an image or PDF and extract its text, honestly."""
    name = (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1][:200] or "upload"
    if not data:
        raise BatchError("bad_file", f"Item {n} ({name}): the file is empty.")
    if len(data) > inputs.max_bytes():
        raise BatchError(
            "bad_file", f"Item {n} ({name}): the file is larger than {inputs.settings.max_upload_mb} MB."
        )
    try:
        if data.lstrip()[:5] == b"%PDF-":
            text, pages = inputs.extract_pdf_text(data)
            if not text.strip():
                raise BatchError(
                    "pdf_no_text",
                    f"Item {n} ({name}): we could not find any text in this PDF. It may be a "
                    "scanned image. Please paste the important lines as a message instead.",
                )
            item = PreparedItem(
                kind=InputKind.PDF.value, text=text, filename=name, upload=data,
                content_type="application/pdf",
            )
            if pages > inputs.MAX_PDF_PAGES or len(text) >= inputs.MAX_EXTRACT_CHARS:
                item.notes.append("This PDF is long, so only its first part was checked.")
            return item

        if inputs.sniff_image(data) is None:
            raise BatchError(
                "bad_file", f"Item {n} ({name}): please choose a JPG, PNG or WebP image, or a PDF."
            )
        kind = inputs.validate_image(data)
        typed = (typed_text or "").strip()
        item = PreparedItem(kind=InputKind.IMAGE.value, filename=name, upload=data, content_type=kind)
        if inputs.ocr_available():
            ocr_text, conf = inputs.run_ocr(data)
            item.ocr_used = True
            item.ocr_confidence = conf
            item.ocr_text = ocr_text
            item.text = typed or ocr_text
            if not item.text:
                raise BatchError(
                    "no_image_text",
                    f"Item {n} ({name}): no text could be read from this image. "
                    "Please type the text you see in it.",
                )
        else:
            if not typed:
                raise BatchError(
                    "need_typed",
                    f"Item {n} ({name}): automatic text reading is not available. "
                    "Please type the text you see in the image.",
                )
            item.text = typed
            item.notes.append(
                "Automatic text reading (OCR) is not available, so only the text you typed "
                "from the image was checked. The image itself was not analysed."
            )
        if len(item.text) > engine.MAX_TEXT_CHARS:
            raise _too_long(n)
        return item
    except inputs.InputError as exc:
        raise BatchError("bad_file", f"Item {n} ({name}): {exc}") from exc


# ---------------------------------------------------------------------------
# Creating a job
# ---------------------------------------------------------------------------


def _snippet(text: str, limit: int = 60) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _masked(text: str | None) -> tuple[str | None, list[str]]:
    if text is None:
        return None, []
    return rai.redact_sensitive(text)


def create_job(db, user, items: list[PreparedItem], *, label: str = "", language: str = "en") -> BatchJob:
    """Create the job and its queued items. The caller commits and enqueues."""
    if not items:
        raise BatchError("empty", "Please add at least one message, link, image or PDF.")
    if len(items) > MAX_ITEMS:
        raise BatchError("too_many", f"A batch can hold up to {MAX_ITEMS} items. You added {len(items)}.")

    store_history = account.may_store_analysis(user)
    store_files = account.may_store_uploads(user)
    now = datetime.now(timezone.utc)
    job = BatchJob(
        user_id=user.id,
        label=" ".join((label or "").split())[:MAX_LABEL_CHARS],
        status=JobStatus.QUEUED.value,
        total_items=len(items),
        completed_items=0,
        failed_items=0,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()

    pending: dict[str, dict] = {}
    for position, item in enumerate(items):
        word = KIND_WORD.get(item.kind, "Item")
        # Mask OTPs, card numbers and the like before anything is stored.
        text, sensitive = _masked(item.text)
        url, url_sensitive = _masked(item.url)
        ocr_text, _ = _masked(item.ocr_text)
        sensitive = sorted(set(sensitive) | set(url_sensitive))
        notes = list(item.notes)
        if sensitive:
            notes.append(
                "Some sensitive details (" + ", ".join(k.replace("_", " ") for k in sensitive)
                + ") were masked before checking and are not stored."
            )

        if not store_history:
            name = f"{word} {position + 1}"
        elif item.kind == InputKind.URL.value:
            name = _snippet(url or "", 120)
        elif item.filename:
            name = item.filename
        else:
            name = f"{word} {position + 1}: {_snippet(text or '')}"

        row = BatchItem(
            job_id=job.id,
            position=position,
            display_name=name[:255],
            status=JobStatus.QUEUED.value,
            created_at=now,
            updated_at=now,
        )
        if item.upload and store_history:
            upload = inputs.record_upload(
                db, user,
                data=item.upload,
                filename=item.filename or "upload",
                content_type=item.content_type,
                kind=item.kind,
                keep_bytes=store_files,
            )
            row.uploaded_file_id = upload.id
        db.add(row)
        pending[str(position)] = {
            "kind": item.kind,
            "text": text or "",
            "url": url,
            "notes": notes,
            "ocr_used": item.ocr_used,
            "ocr_confidence": item.ocr_confidence,
            "ocr_text": ocr_text,
        }

    job.summary = {"language": language, "pending": pending}
    db.flush()
    return job


# ---------------------------------------------------------------------------
# Processing (runs on the job queue)
# ---------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _items(db, job_id) -> list[BatchItem]:
    return list(
        db.execute(
            select(BatchItem).where(BatchItem.job_id == job_id).order_by(BatchItem.position)
        ).scalars()
    )


def _rollup(db, job: BatchJob) -> list[BatchItem]:
    items = _items(db, job.id)
    by_status = {s.value: 0 for s in AnalysisStatus}
    for item in items:
        if item.status == JobStatus.COMPLETED.value and item.result_status in by_status:
            by_status[item.result_status] += 1
    job.total_items = len(items)
    job.completed_items = sum(1 for i in items if i.status == JobStatus.COMPLETED.value)
    job.failed_items = sum(1 for i in items if i.status == JobStatus.FAILED.value)
    summary = dict(job.summary or {})
    summary["by_status"] = by_status
    job.summary = summary
    return items


def _claim(db, item: BatchItem, now: datetime) -> bool:
    """Mark ``item`` as PROCESSING unless another worker holds it."""
    if item.status == JobStatus.PROCESSING.value:
        touched = _aware(item.updated_at)
        if touched is not None and now - touched < STALE_AFTER:
            return False
    result = db.execute(
        update(BatchItem)
        .where(BatchItem.id == item.id, BatchItem.status == item.status)
        .values(status=JobStatus.PROCESSING.value, updated_at=now)
    )
    db.commit()
    return result.rowcount == 1


def _analyse_item(db, user, item: BatchItem, spec: dict | None, *, language: str, store: bool) -> None:
    if spec is None:
        item.status = JobStatus.FAILED.value
        item.error = MISSING_INPUT_MESSAGE
        return
    data = engine.CheckInput(
        kind=spec.get("kind") or InputKind.TEXT.value,
        text=spec.get("text") or "",
        url=spec.get("url"),
        ocr_used=bool(spec.get("ocr_used")),
        ocr_confidence=spec.get("ocr_confidence"),
        ocr_text=spec.get("ocr_text"),
        notes=list(spec.get("notes") or []),
        uploaded_file_id=item.uploaded_file_id,
    )
    analysis = engine.analyse(db, user, data, language=language, persist=store)
    if store:
        analysis.batch_item_id = item.id
        db.flush()
        item.analysis_id = analysis.id
    item.result_status = analysis.status
    item.status = JobStatus.COMPLETED.value
    item.error = None


def process_job(job_id) -> None:
    """Analyse every unfinished item of a batch job. Idempotent; safe to retry."""
    from app.models.user import User

    key = uuid.UUID(str(job_id))
    db = SessionLocal()
    try:
        job = db.get(BatchJob, key)
        if job is None:
            return
        user = db.get(User, job.user_id)
        if user is None:
            return
        summary = dict(job.summary or {})
        pending = dict(summary.get("pending") or {})
        language = summary.get("language") or "en"
        store = account.may_store_analysis(user)

        if any(i.status not in TERMINAL for i in _items(db, job.id)):
            now = datetime.now(timezone.utc)
            job.status = JobStatus.PROCESSING.value
            job.started_at = job.started_at or now
            job.finished_at = None
            db.commit()

        for item in _items(db, job.id):
            if item.status in TERMINAL:
                continue
            if item.analysis_id is not None:
                # Analysed before a crash but not marked finished: just finish it.
                existing = db.get(MessageAnalysis, item.analysis_id)
                item.status = JobStatus.COMPLETED.value
                item.result_status = existing.status if existing else item.result_status
                _rollup(db, job)
                db.commit()
                continue
            if not _claim(db, item, datetime.now(timezone.utc)):
                continue
            db.refresh(item)
            item_id = item.id
            try:
                _analyse_item(db, user, item, pending.get(str(item.position)), language=language, store=store)
                db.flush()
            except Exception:  # noqa: BLE001 - one bad item must not stop the batch
                log.exception("batch item %s failed", item_id)
                db.rollback()
                item = db.get(BatchItem, item_id)
                item.status = JobStatus.FAILED.value
                item.error = ITEM_FAILED_MESSAGE
                item.analysis_id = None
            _rollup(db, job)
            db.commit()

        items = _rollup(db, job)
        if all(i.status in TERMINAL for i in items):
            summary = dict(job.summary or {})
            summary.pop("pending", None)  # drop the prepared text once every item is done
            job.summary = summary
            if items and all(i.status == JobStatus.FAILED.value for i in items):
                job.status = JobStatus.FAILED.value
                job.error = "None of the items in this batch could be analysed."
            else:
                job.status = JobStatus.COMPLETED.value
                job.error = None
            job.finished_at = job.finished_at or datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("batch job %s failed", job_id)
        job = db.get(BatchJob, key)
        if job is not None and job.status not in TERMINAL:
            job.status = JobStatus.FAILED.value
            job.error = "The batch stopped unexpectedly. Items not yet analysed were left unchecked."
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
