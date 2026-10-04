"""Voice conversation sessions and turns.

Transcripts are persisted only when the user has opted in via
``UserPrivacySettings.store_voice_transcripts``; otherwise rows are written
with the text omitted so the conversation still works but leaves no record.
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
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk


class VoiceSession(Base, TimestampMixin):
    __tablename__ = "voice_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    language: Mapped[str] = mapped_column(String(8), default="en")
    # "browser" (on-device Web Speech) or a cloud provider name.
    stt_provider: Mapped[str] = mapped_column(String(32), default="browser")
    tts_provider: Mapped[str] = mapped_column(String(32), default="browser")
    ai_provider: Mapped[str | None] = mapped_column(String(32))

    title: Mapped[str] = mapped_column(String(200), default="")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    transcripts_retained: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list["VoiceMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class VoiceMessage(Base, TimestampMixin):
    __tablename__ = "voice_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("voice_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | system
    # NULL when the user declined transcript retention.
    content: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="en")

    # Populated for user turns that came through speech-to-text.
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    audio_seconds: Mapped[float | None] = mapped_column(Float)

    # Responsible-AI outcome for assistant turns.
    guardrail_action: Mapped[str | None] = mapped_column(String(16))
    guardrail_notes: Mapped[dict | None] = mapped_column(JSONColumn())
    # Knowledge-base citations used to ground this answer.
    sources: Mapped[dict | None] = mapped_column(JSONColumn())
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    session: Mapped[VoiceSession] = relationship(back_populates="messages")


Index("ix_voice_sessions_user_created", VoiceSession.user_id, VoiceSession.created_at)
Index("ix_voice_messages_session_created", VoiceMessage.session_id, VoiceMessage.created_at)
