"""Market education: cached series and deterministic teaching scenarios.

Market data is used ONLY to explain concepts (volatility, drawdown, volume,
cycles). It never becomes a price prediction, a return forecast, a ranking or
a personalised recommendation. Synthetic series are flagged via
``is_synthetic`` and the UI must label them as demo data.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.types import GUID, JSONColumn, TimestampMixin, uuid_pk

# Concepts the market module is allowed to teach.
MARKET_CONCEPTS = [
    "volatility",
    "drawdown",
    "volume",
    "market-cycles",
    "diversification",
    "risk",
    "index-movement",
    "compounding",
]


class MarketDataCache(Base, TimestampMixin):
    __tablename__ = "market_data_cache"
    __table_args__ = (
        UniqueConstraint("symbol", "series", "interval", name="uq_market_cache_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    symbol: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    series: Mapped[str] = mapped_column(String(48), default="historical", nullable=False)
    interval: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)

    # Which MarketDataProvider produced this row.
    provider: Mapped[str] = mapped_column(String(32), default="mock", index=True)
    # True for generated/demo series. The UI must say so.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    payload: Mapped[dict | None] = mapped_column(JSONColumn())
    points: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    scenarios: Mapped[list["MarketEducationalScenario"]] = relationship(
        back_populates="cache_row"
    )

    @property
    def label(self) -> str:
        return "Demo / synthetic data" if self.is_synthetic else "Historical data"


class MarketEducationalScenario(Base, TimestampMixin):
    """A teaching scenario or labelled simulation built on a cached series."""

    __tablename__ = "market_educational_scenarios"

    id: Mapped[uuid.UUID] = uuid_pk()
    cache_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("market_data_cache.id", ondelete="SET NULL"), index=True
    )

    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    concept: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", index=True)

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    what_it_means: Mapped[str] = mapped_column(Text, default="")
    how_it_is_calculated: Mapped[str] = mapped_column(Text, default="")
    why_people_care: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    what_this_teaches: Mapped[dict | None] = mapped_column(JSONColumn())

    # Chart series for the educational visual.
    chart_data: Mapped[dict | None] = mapped_column(JSONColumn())
    chart_kind: Mapped[str] = mapped_column(String(24), default="line")

    # True for the "See how volatility affects a hypothetical portfolio" module.
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Rendered verbatim beneath every market visual.
    disclaimer: Mapped[str] = mapped_column(
        Text, default="Educational information only. Not investment advice."
    )

    cache_row: Mapped[MarketDataCache | None] = relationship(back_populates="scenarios")


Index("ix_market_scenarios_concept_lang", MarketEducationalScenario.concept,
      MarketEducationalScenario.language)
