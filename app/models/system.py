"""Operational tables: notifications, audit log, system events, feature flags.

The audit log records *that* an action happened and by whom. It deliberately
does not copy private user content (journal text, memories, transcripts) so
that an ADMIN reading the audit trail still cannot read private material.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    kind: Mapped[str] = mapped_column(String(48), default="info", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(48), default="notifications")
    link: Mapped[str | None] = mapped_column(String(300))

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class AuditLog(Base, TimestampMixin):
    """Append-only trail of security- and privacy-relevant actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    # NULL for anonymous or system-originated actions.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Set when an admin or family assistant acted on another account.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), default="success", index=True)

    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    # Non-sensitive context only. Never private user content.
    detail: Mapped[dict | None] = mapped_column(JSONColumn())


class SystemEvent(Base, TimestampMixin):
    """Health and observability signal, e.g. provider failures, job timings."""

    __tablename__ = "system_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    component: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict | None] = mapped_column(JSONColumn())


class FeatureFlag(Base, TimestampMixin):
    """Admin-togglable capability switch, read through app.services.flags."""

    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Optional gradual rollout, 0-100, hashed on user id.
    rollout_percent: Mapped[int] = mapped_column(Integer, default=100)
    config: Mapped[dict | None] = mapped_column(JSONColumn())


Index("ix_audit_user_created", AuditLog.user_id, AuditLog.created_at)
Index("ix_audit_action_created", AuditLog.action, AuditLog.created_at)
Index("ix_notifications_user_read", Notification.user_id, Notification.read_at)
Index("ix_system_events_component_created", SystemEvent.component, SystemEvent.created_at)
