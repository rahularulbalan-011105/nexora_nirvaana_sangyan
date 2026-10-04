"""Learn & Explore content and per-user progress.

All content is educational. Nothing here may carry a buy/sell conclusion.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk

# Categories from the spec, used by the Learn & Explore filter chips.
LEARNING_CATEGORIES = [
    ("basics", "Basics"),
    ("mutual-funds", "Mutual Funds"),
    ("scams", "Scams"),
    ("investor-rights", "Investor Rights"),
    ("digital-safety", "Digital Safety"),
    ("budgeting", "Budgeting"),
    ("market-concepts", "Market Concepts"),
    ("risk-volatility", "Risk & Volatility"),
]


class LearningContent(Base, TimestampMixin):
    __tablename__ = "learning_content"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")

    # Plain-language retelling surfaced by the "Explain Simply" control.
    simple_body: Mapped[str | None] = mapped_column(Text)

    icon: Mapped[str] = mapped_column(String(48), default="school")
    reading_minutes: Mapped[int] = mapped_column(Integer, default=3)
    difficulty: Mapped[str] = mapped_column(String(16), default="beginner")
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Where the material came from, so the UI can attribute it.
    source: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str | None] = mapped_column(Text)

    tags: Mapped[dict | None] = mapped_column(JSONColumn())
    # Available offline through the service-worker precache.
    offline_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    progress: Mapped[list["LearningProgress"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )


class LearningProgress(Base, TimestampMixin):
    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="uq_learning_progress_user_content"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("learning_content.id", ondelete="CASCADE"), nullable=False, index=True
    )

    percent: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)

    content: Mapped[LearningContent] = relationship(back_populates="progress", lazy="joined")

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None


Index("ix_learning_content_cat_lang", LearningContent.category, LearningContent.language)
Index("ix_learning_progress_user_done", LearningProgress.user_id, LearningProgress.completed_at)
