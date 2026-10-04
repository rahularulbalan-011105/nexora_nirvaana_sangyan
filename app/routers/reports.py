"""Downloadable reports and the personal data export.

Every report is built from the requesting user's own rows only. Reports render
as a print-ready page (the browser's "Save as PDF" handles Hindi and Tamil
script correctly, which a server-side PDF library would not without bundled
fonts); ``?download=1`` returns the same page as a file attachment.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, inspect, select

from app.deps import DbDep, RequireUser
from app.models.analysis import (
    AnalysisSignal,
    BatchItem,
    BatchJob,
    MessageAnalysis,
    UploadedFile,
)
from app.models.family import FamilyInvitation, FamilyRelationship
from app.models.learning import LearningContent, LearningProgress
from app.models.reflection import JournalEntry, Memory, ReflectionAnswer, ReflectionSession
from app.models.system import Notification
from app.models.voice import VoiceMessage, VoiceSession
from app.services import audit
from app.templating import render

router = APIRouter(tags=["reports"])


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _as_download(response: HTMLResponse, filename: str) -> HTMLResponse:
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _count(db, model, *where) -> int:
    return int(db.execute(select(func.count()).select_from(model).where(*where)).scalar() or 0)


# ---------------------------------------------------------------------------
# My Journey: resilience report
# ---------------------------------------------------------------------------


@router.get("/reports/journey", response_class=HTMLResponse)
def journey_report(request: Request, user: RequireUser, db: DbDep, download: int = 0):
    reflections = (
        db.execute(
            select(ReflectionSession)
            .where(ReflectionSession.user_id == user.id)
            .order_by(ReflectionSession.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    analyses = (
        db.execute(
            select(MessageAnalysis)
            .where(MessageAnalysis.user_id == user.id)
            .order_by(MessageAnalysis.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    learned = db.execute(
        select(LearningContent.title, LearningProgress.completed_at)
        .join(LearningContent, LearningContent.id == LearningProgress.content_id)
        .where(
            LearningProgress.user_id == user.id,
            LearningProgress.completed_at.is_not(None),
        )
        .order_by(LearningProgress.completed_at.desc())
    ).all()

    total_pause_seconds = int(
        db.execute(
            select(func.coalesce(func.sum(ReflectionSession.pause_seconds), 0)).where(
                ReflectionSession.user_id == user.id
            )
        ).scalar()
        or 0
    )
    status_counts: dict[str, int] = {}
    for row in db.execute(
        select(MessageAnalysis.status, func.count())
        .where(MessageAnalysis.user_id == user.id)
        .group_by(MessageAnalysis.status)
    ):
        status_counts[str(row[0])] = int(row[1])

    metrics = [
        ("Reflections completed", _count(
            db, ReflectionSession,
            ReflectionSession.user_id == user.id,
            ReflectionSession.completed_at.is_not(None),
        )),
        ("Pause moments", _count(
            db, ReflectionSession,
            ReflectionSession.user_id == user.id,
            ReflectionSession.pause_completed.is_(True),
        )),
        ("Minutes paused", round(total_pause_seconds / 60, 1)),
        ("Messages checked", _count(db, MessageAnalysis, MessageAnalysis.user_id == user.id)),
        ("Journal entries", _count(db, JournalEntry, JournalEntry.user_id == user.id)),
        ("Concepts learned", len(learned)),
    ]

    response = render(
        request,
        "reports/report.html",
        user=user,
        db=db,
        active_nav="my-journey",
        report_kind="journey",
        report_title="My Resilience Report",
        report_subtitle="Your reflections, pauses, checks and learning in NIRVAAN.",
        generated_at=datetime.now(timezone.utc),
        metrics=metrics,
        status_counts=status_counts,
        reflections=reflections,
        analyses=analyses,
        learned=learned,
        download_url="/reports/journey?download=1",
        csv_url=None,
    )
    audit.record(db, action="report.journey", user_id=user.id, request=request)
    db.commit()
    if download:
        return _as_download(response, f"nirvaan-resilience-report-{_stamp()}.html")
    return response


# ---------------------------------------------------------------------------
# Batch analysis report
# ---------------------------------------------------------------------------


def _owned_job(db, user, job_id: str) -> BatchJob:
    try:
        key = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.") from None
    job = db.execute(
        select(BatchJob).where(BatchJob.id == key, BatchJob.user_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        # Same response for "missing" and "someone else's" - no existence leak.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return job


def _job_items(db, job: BatchJob) -> list[BatchItem]:
    return (
        db.execute(select(BatchItem).where(BatchItem.job_id == job.id).order_by(BatchItem.position))
        .scalars()
        .all()
    )


@router.get("/reports/batch/{job_id}.csv")
def batch_report_csv(job_id: str, user: RequireUser, db: DbDep):
    job = _owned_job(db, user, job_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["#", "Item", "Processing status", "Result", "Error"])
    for item in _job_items(db, job):
        writer.writerow(
            [item.position + 1, item.display_name, item.status, item.result_status or "", item.error or ""]
        )
    # UTF-8 BOM so Excel shows Hindi / Tamil names correctly.
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="nirvaan-batch-{_stamp()}.csv"'},
    )


@router.get("/reports/batch/{job_id}", response_class=HTMLResponse)
def batch_report(request: Request, job_id: str, user: RequireUser, db: DbDep, download: int = 0):
    job = _owned_job(db, user, job_id)
    items = _job_items(db, job)
    result_counts: dict[str, int] = {}
    for item in items:
        key = item.result_status or item.status
        result_counts[key] = result_counts.get(key, 0) + 1

    response = render(
        request,
        "reports/report.html",
        user=user,
        db=db,
        active_nav="batch",
        report_kind="batch",
        report_title="Batch Analysis Summary",
        report_subtitle=job.label or "Batch analysis",
        generated_at=datetime.now(timezone.utc),
        metrics=[
            ("Items", job.total_items or len(items)),
            ("Completed", job.completed_items),
            ("Failed", job.failed_items),
        ],
        status_counts=result_counts,
        job=job,
        items=items,
        download_url=f"/reports/batch/{job.id}?download=1",
        csv_url=f"/reports/batch/{job.id}.csv",
    )
    if download:
        return _as_download(response, f"nirvaan-batch-report-{_stamp()}.html")
    return response


# ---------------------------------------------------------------------------
# Privacy Center: export everything NIRVAAN holds about the user
# ---------------------------------------------------------------------------

# Never exported: credential material and internal security state.
_EXCLUDED_COLUMNS = {"password_hash", "token_hash", "failed_login_count", "locked_until"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _rows(objs) -> list[dict[str, Any]]:
    out = []
    for obj in objs:
        mapper = inspect(obj).mapper
        out.append(
            {
                col.key: _jsonable(getattr(obj, col.key))
                for col in mapper.column_attrs
                if col.key not in _EXCLUDED_COLUMNS
            }
        )
    return out


def _all(db, stmt):
    return db.execute(stmt).scalars().all()


@router.get("/privacy/export.zip")
def privacy_export(request: Request, user: RequireUser, db: DbDep):
    uid = user.id
    analyses = _all(db, select(MessageAnalysis).where(MessageAnalysis.user_id == uid))
    analysis_ids = [a.id for a in analyses]
    sessions = _all(db, select(ReflectionSession).where(ReflectionSession.user_id == uid))
    session_ids = [s.id for s in sessions]
    jobs = _all(db, select(BatchJob).where(BatchJob.user_id == uid))
    job_ids = [j.id for j in jobs]
    voice = _all(db, select(VoiceSession).where(VoiceSession.user_id == uid))
    voice_ids = [v.id for v in voice]

    sections: dict[str, list[dict[str, Any]]] = {
        "profile": _rows([user]),
        "preferences": _rows([user.preferences] if user.preferences else []),
        "privacy_settings": _rows([user.privacy] if user.privacy else []),
        "journal_entries": _rows(_all(db, select(JournalEntry).where(JournalEntry.user_id == uid))),
        "memories": _rows(_all(db, select(Memory).where(Memory.user_id == uid))),
        "reflection_sessions": _rows(sessions),
        "reflection_answers": _rows(
            _all(db, select(ReflectionAnswer).where(ReflectionAnswer.session_id.in_(session_ids)))
        )
        if session_ids
        else [],
        "message_analyses": _rows(analyses),
        "analysis_signals": _rows(
            _all(db, select(AnalysisSignal).where(AnalysisSignal.analysis_id.in_(analysis_ids)))
        )
        if analysis_ids
        else [],
        "batch_jobs": _rows(jobs),
        "batch_items": _rows(_all(db, select(BatchItem).where(BatchItem.job_id.in_(job_ids))))
        if job_ids
        else [],
        "uploaded_files": _rows(_all(db, select(UploadedFile).where(UploadedFile.user_id == uid))),
        "learning_progress": _rows(
            _all(db, select(LearningProgress).where(LearningProgress.user_id == uid))
        ),
        "voice_sessions": _rows(voice),
        "voice_messages": _rows(
            _all(db, select(VoiceMessage).where(VoiceMessage.session_id.in_(voice_ids)))
        )
        if voice_ids
        else [],
        "family_relationships": _rows(
            _all(
                db,
                select(FamilyRelationship).where(
                    (FamilyRelationship.owner_user_id == uid)
                    | (FamilyRelationship.assistant_user_id == uid)
                ),
            )
        ),
        "family_invitations_sent": _rows(
            _all(db, select(FamilyInvitation).where(FamilyInvitation.inviter_user_id == uid))
        ),
        "notifications": _rows(_all(db, select(Notification).where(Notification.user_id == uid))),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt",
            "NIRVAAN personal data export\n"
            f"Account: {user.email}\n"
            f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
            "Each .json file holds one kind of record NIRVAAN stores for you.\n"
            "Passwords and security tokens are never included.\n",
        )
        for name, rows in sections.items():
            archive.writestr(f"{name}.json", json.dumps(rows, ensure_ascii=False, indent=2))

    audit.record(db, action="privacy.export", user_id=uid, request=request)
    db.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="nirvaan-my-data-{_stamp()}.zip"'},
    )
