"""Journal, opt-in memory, and the Pause & Reflect flow.

Reflection output is descriptive only. The allowed labels are Good /
Needs Review / Present / Developing - never BUY, SELL, INVEST or DO NOT INVEST.
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
from app.models.enums import MemoryType
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(8), default="en")

    # Set when the entry was created by completing a pause or a reflection.
    reflection_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    pause_seconds: Mapped[int | None] = mapped_column(Integer)
    mood_note: Mapped[str | None] = mapped_column(String(120))

    # Journals are private by default. Family access needs JOURNAL_SHARED scope.
    shared_with_family: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_offline: Mapped[bool] = mapped_column(Boolean, default=False)


class Memory(Base, TimestampMixin):
    """Opt-in personal memory. Disabled by default; the user owns every row.

    Never store credentials, OTPs, PINs, card or bank details. The write path
    runs the sensitive-data scrubber in app.services.responsible_ai first.
    """

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        String(24), default=MemoryType.CONTEXT.value, nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), default="user")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class ReflectionSession(Base, TimestampMixin):
    __tablename__ = "reflection_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional link to the message that prompted the reflection.
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("message_analyses.id", ondelete="SET NULL"), index=True
    )

    language: Mapped[str] = mapped_column(String(8), default="en")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Five descriptive dimensions, each holding a ReflectionLabel value.
    reason_clarity: Mapped[str | None] = mapped_column(String(24))
    evidence_quality: Mapped[str | None] = mapped_column(String(24))
    time_pressure: Mapped[str | None] = mapped_column(String(24))
    external_influence: Mapped[str | None] = mapped_column(String(24))
    understanding: Mapped[str | None] = mapped_column(String(24))

    summary: Mapped[str] = mapped_column(Text, default="")
    # Behavioural flags used by My Journey insights (never a diagnosis).
    signals_noticed: Mapped[dict | None] = mapped_column(JSONColumn())

    pause_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_seconds: Mapped[int] = mapped_column(Integer, default=0)

    answers: Mapped[list["ReflectionAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class ReflectionAnswer(Base, TimestampMixin):
    __tablename__ = "reflection_answers"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("reflection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, default="")
    answer_value: Mapped[str | None] = mapped_column(String(64))
    answer_text: Mapped[str | None] = mapped_column(Text)
    # Contribution of this answer to its dimension, for explainability.
    weight: Mapped[float] = mapped_column(Float, default=0.0)

    session: Mapped[ReflectionSession] = relationship(back_populates="answers")


Index("ix_journal_user_created", JournalEntry.user_id, JournalEntry.created_at)
Index("ix_memories_user_type", Memory.user_id, Memory.type)
Index(
    "ix_reflection_user_completed",
    ReflectionSession.user_id,
    ReflectionSession.completed_at,
)
