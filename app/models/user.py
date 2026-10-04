"""Identity, authentication, roles, preferences and privacy settings."""
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Language, Role
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Argon2id hash. A plaintext password is never stored or logged.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Optional and self-described; only used to pick the companion avatar.
    gender: Mapped[str | None] = mapped_column(String(16))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    preferences: Mapped["UserPreferences | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    privacy: Mapped["UserPrivacySettings | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    @property
    def role_names(self) -> set[str]:
        return {ur.role.name for ur in self.roles if ur.role is not None}

    def has_role(self, role: Role | str) -> bool:
        return str(role) in self.role_names

    @property
    def is_admin(self) -> bool:
        return self.has_role(Role.ADMIN)

    @property
    def language(self) -> str:
        return self.preferences.language if self.preferences else Language.EN.value

    @property
    def avatar_url(self) -> str:
        """Companion avatar shown on the dashboard, matched to the user's gender."""
        if self.gender == "male":
            return "/static/img/avatar-male.svg"
        return "/static/img/avatar-female.jpg"

    @property
    def first_name(self) -> str:
        return (self.full_name or "").strip().split(" ")[0] or "there"


class RoleRow(Base, TimestampMixin):
    """The roles lookup table. Seeded by scripts/seed.py."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    assignments: Mapped[list["UserRole"]] = relationship(back_populates="role")


class UserRole(Base, TimestampMixin):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[RoleRow] = relationship(back_populates="assignments", lazy="joined")


class Session(Base, TimestampMixin):
    """Server-side session. The cookie carries only an opaque signed token."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 of the session token: a database leak must not yield live sessions.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship()


class EmailVerification(Base, TimestampMixin):
    __tablename__ = "email_verifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class PasswordReset(Base, TimestampMixin):
    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class UserPreferences(Base, TimestampMixin):
    """Accessibility and delivery preferences - the Bharat-first switches."""

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    language: Mapped[str] = mapped_column(String(8), default=Language.EN.value, nullable=False)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    speech_rate: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    large_text: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    simple_language: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_saver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    offline_cache_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    family_mode_ui: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSONColumn())

    user: Mapped[User] = relationship(back_populates="preferences")


class UserPrivacySettings(Base, TimestampMixin):
    """Privacy defaults are the conservative ones. Memory is OFF by default."""

    __tablename__ = "user_privacy_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    store_analysis_history: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    store_voice_transcripts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    store_uploaded_files: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_family_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    analytics_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    on_device_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="privacy")


Index("ix_sessions_user_active", Session.user_id, Session.expires_at)
