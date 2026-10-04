"""Message analysis, safety signals, evidence, uploads and batch processing.

Nothing in this module ever records a verdict of "safe" or "fraud". The schema
only stores observations, the evidence behind them, and what remains unverified.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AnalysisStatus, InputKind, JobStatus, Severity
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk


class UploadedFile(Base, TimestampMixin):
    """A user-supplied artefact. Retained only if privacy settings allow it."""

    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str | None] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=InputKind.IMAGE.value)
    # Set once the bytes are deleted but the analysis record is kept.
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageAnalysis(Base, TimestampMixin):
    __tablename__ = "message_analyses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("uploaded_files.id", ondelete="SET NULL"), index=True
    )
    batch_item_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)

    input_kind: Mapped[str] = mapped_column(String(16), default=InputKind.TEXT.value)
    source_url: Mapped[str | None] = mapped_column(Text)

    raw_text: Mapped[str] = mapped_column(Text, default="")
    # Text after the user has corrected OCR mistakes - this is what we analyse.
    corrected_text: Mapped[str | None] = mapped_column(Text)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)

    detected_language: Mapped[str] = mapped_column(String(8), default="en")
    language_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(
        String(48), default=AnalysisStatus.NEEDS_VERIFICATION.value, index=True
    )
    # Aggregate confidence in the *detection*, never in a fraud judgement.
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Structured NLP output: claims, entities, links, urgency, regulatory claims.
    nlp_result: Mapped[dict | None] = mapped_column(JSONColumn())
    # The four explainability panes rendered in the UI.
    what_we_detected: Mapped[str] = mapped_column(Text, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    what_to_verify: Mapped[str] = mapped_column(Text, default="")
    what_is_uncertain: Mapped[str] = mapped_column(Text, default="")

    # Responsible-AI audit trail for this analysis.
    guardrail_action: Mapped[str | None] = mapped_column(String(16))
    guardrail_notes: Mapped[dict | None] = mapped_column(JSONColumn())
    ai_provider: Mapped[str | None] = mapped_column(String(32))
    processing_ms: Mapped[int | None] = mapped_column(Integer)

    signals: Mapped[list["AnalysisSignal"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", lazy="selectin"
    )
    sources: Mapped[list["AnalysisSource"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def text_for_display(self) -> str:
        return self.corrected_text or self.raw_text


class SafetyRule(Base, TimestampMixin):
    """Admin-editable rule driving the deterministic half of the hybrid engine."""

    __tablename__ = "safety_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", index=True)

    # Regex applied to normalised text. Patterns are authored, never user input.
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(8), default=Severity.MEDIUM.value)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    explanation_en: Mapped[str] = mapped_column(Text, default="")
    explanation_hi: Mapped[str] = mapped_column(Text, default="")
    explanation_ta: Mapped[str] = mapped_column(Text, default="")
    verify_hint_en: Mapped[str] = mapped_column(Text, default="")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    signals: Mapped[list["AnalysisSignal"]] = relationship(back_populates="rule")

    def explanation_for(self, language: str) -> str:
        return {
            "hi": self.explanation_hi,
            "ta": self.explanation_ta,
        }.get(language) or self.explanation_en


class AnalysisSignal(Base, TimestampMixin):
    __tablename__ = "analysis_signals"

    id: Mapped[uuid.UUID] = uuid_pk()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("message_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("safety_rules.id", ondelete="SET NULL"), index=True
    )

    signal_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(8), default=Severity.MEDIUM.value)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # The literal span from the message that triggered this signal.
    evidence: Mapped[str] = mapped_column(Text, default="")
    evidence_start: Mapped[int | None] = mapped_column(Integer)
    evidence_end: Mapped[int | None] = mapped_column(Integer)

    explanation: Mapped[str] = mapped_column(Text, default="")
    verify_hint: Mapped[str] = mapped_column(Text, default="")
    # "rule" | "classifier" | "llm" - shown in the UI so users know the basis.
    detector: Mapped[str] = mapped_column(String(16), default="rule")

    analysis: Mapped[MessageAnalysis] = relationship(back_populates="signals")
    rule: Mapped[SafetyRule | None] = relationship(back_populates="signals")


class AnalysisSource(Base, TimestampMixin):
    """A retrieved knowledge-base citation supporting an explanation."""

    __tablename__ = "analysis_sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("message_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)

    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[float] = mapped_column(Float, default=0.0)

    analysis: Mapped[MessageAnalysis] = relationship(back_populates="sources")


class BatchJob(Base, TimestampMixin):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED.value, index=True)

    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)

    # Rollup across items: how many fell into each status bucket.
    summary: Mapped[dict | None] = mapped_column(JSONColumn())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def progress_percent(self) -> int:
        if not self.total_items:
            return 0
        done = self.completed_items + self.failed_items
        return int(round(done * 100 / self.total_items))


class BatchItem(Base, TimestampMixin):
    __tablename__ = "batch_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("uploaded_files.id", ondelete="SET NULL")
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("message_analyses.id", ondelete="SET NULL")
    )

    position: Mapped[int] = mapped_column(Integer, default=0)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED.value, index=True)
    result_status: Mapped[str | None] = mapped_column(String(48))
    error: Mapped[str | None] = mapped_column(Text)

    job: Mapped[BatchJob] = relationship(back_populates="items")


Index("ix_analyses_user_created", MessageAnalysis.user_id, MessageAnalysis.created_at)
Index("ix_batch_jobs_user_status", BatchJob.user_id, BatchJob.status)
Index("ix_batch_items_job_status", BatchItem.job_id, BatchItem.status)
