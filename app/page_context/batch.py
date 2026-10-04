"""Batch Analysis: the signed-in user's batch jobs, the selected one and its items.

``build`` shows the latest job; ``job_view`` is shared with ``/api/batch/{id}``
so the page and its live updates render from the same data.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.analysis import BatchJob, MessageAnalysis
from app.config import settings
from app.models.enums import AnalysisStatus, JobStatus, SignalType
from app.page_context.check_a_message import status_meta

CLEAN = AnalysisStatus.NO_OBVIOUS_SIGNALS.value
VERIFY = AnalysisStatus.NEEDS_VERIFICATION.value
MULTIPLE = AnalysisStatus.MULTIPLE_SIGNALS.value

URGENCY_SIGNALS = {
    SignalType.URGENCY.value,
    SignalType.LIMITED_TIME_PRESSURE.value,
    SignalType.FOMO.value,
    SignalType.SOCIAL_PRESSURE.value,
}
CERTAINTY_SIGNALS = {
    SignalType.GUARANTEED_RETURN.value,
    SignalType.UNREALISTIC_RETURN.value,
}

_ICON_BY_EXT = {
    "png": "image", "jpg": "image", "jpeg": "image", "webp": "image",
    "pdf": "picture_as_pdf", "txt": "chat",
}
_ICON_BY_KIND = {"TEXT": "chat", "URL": "link", "IMAGE": "image", "PDF": "picture_as_pdf"}
RUNNING = (JobStatus.QUEUED.value, JobStatus.PROCESSING.value)
PAST_JOBS_LIMIT = 12


def _pct(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def own_job(db, user, job_id) -> BatchJob | None:
    """The user's job with this id, or None (also for someone else's job)."""
    import uuid

    try:
        key = uuid.UUID(str(job_id))
    except ValueError:
        return None
    return db.execute(
        select(BatchJob).where(BatchJob.id == key, BatchJob.user_id == user.id)
    ).scalar_one_or_none()


def past_jobs(db, user) -> list[BatchJob]:
    return list(
        db.execute(
            select(BatchJob)
            .where(BatchJob.user_id == user.id)
            .order_by(BatchJob.created_at.desc())
            .limit(PAST_JOBS_LIMIT)
        ).scalars()
    )


def build(db, user) -> dict:
    jobs = past_jobs(db, user)
    from app.services import analysis as engine
    from app.services import analysis_inputs as inputs
    from app.services.batch import MAX_ITEMS

    return {
        **job_view(db, user, jobs[0] if jobs else None),
        "batch_jobs": jobs,
        "batch_max_items": MAX_ITEMS,
        "batch_max_mb": settings.max_upload_mb,
        "batch_max_chars": engine.MAX_TEXT_CHARS,
        "batch_ocr_available": inputs.ocr_available(),
    }


def job_view(db, user, job: BatchJob | None) -> dict:
    counts = {"total": 0, "clean": 0, "verify": 0, "multiple": 0, "flagged": 0}
    pct = {"clean": 0.0, "verify": 0.0, "multiple": 0.0}
    behaviour = {"urgency": 0.0, "certainty": 0.0}
    items: list[dict] = []

    if job is not None:
        job_items = sorted(job.items, key=lambda i: (i.position, i.created_at))
        analysis_ids = [i.analysis_id for i in job_items if i.analysis_id]
        analyses = {}
        if analysis_ids:
            analyses = {
                a.id: a
                for a in db.execute(
                    select(MessageAnalysis).where(
                        MessageAnalysis.user_id == user.id,
                        MessageAnalysis.id.in_(analysis_ids),
                    )
                ).scalars()
            }

        pending = (job.summary or {}).get("pending") or {}
        urgency_hits = certainty_hits = 0
        for item in job_items:
            analysis = analyses.get(item.analysis_id) if item.analysis_id else None
            result = item.result_status or (analysis.status if analysis else None)
            if result == CLEAN:
                category = "clean"
                counts["clean"] += 1
            elif result in (VERIFY, MULTIPLE):
                category = "flagged"
                counts["verify" if result == VERIFY else "multiple"] += 1
                types = {s.signal_type for s in analysis.signals} if analysis else set()
                urgency_hits += bool(types & URGENCY_SIGNALS)
                certainty_hits += bool(types & CERTAINTY_SIGNALS)
            else:
                category = "pending"

            finding = ""
            if analysis is not None:
                finding = analysis.what_we_detected or next(
                    (s.explanation for s in analysis.signals if s.explanation), ""
                )
            kind = analysis.input_kind if analysis else (pending.get(str(item.position)) or {}).get("kind")
            ext = (item.display_name or "").rsplit(".", 1)[-1].lower()
            items.append(
                {
                    "obj": item,
                    "name": item.display_name or f"Item {item.position + 1}",
                    "category": category,
                    "result": result,
                    "meta": status_meta(result) if result else None,
                    "icon": _ICON_BY_KIND.get(kind) or _ICON_BY_EXT.get(ext, "description"),
                    "when": item.created_at,
                    "finding": finding,
                    "error": item.error,
                    "analysis_id": item.analysis_id,
                }
            )

        counts["total"] = len(job_items)
        counts["flagged"] = counts["verify"] + counts["multiple"]
        pct = {k: _pct(counts[k], counts["total"]) for k in ("clean", "verify", "multiple")}
        behaviour = {
            "urgency": _pct(urgency_hits, counts["flagged"]),
            "certainty": _pct(certainty_hits, counts["flagged"]),
        }

    return {
        "batch_job": job,
        "batch_items": items,
        "batch_counts": counts,
        "batch_pct": pct,
        "batch_behaviour": behaviour,
        "batch_running": bool(job is not None and job.status in RUNNING),
        "batch_done": (job.completed_items + job.failed_items) if job is not None else 0,
    }
