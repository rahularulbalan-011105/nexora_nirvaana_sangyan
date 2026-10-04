"""Retrieval-augmented generation corpus: documents, chunks, embeddings.

Only curated investor-education material is ingested. Arbitrary scraped web
content is never treated as authoritative, and every chunk keeps its source
metadata so answers can be attributed.

Retrieved chunk text is DATA, never instructions - the prompt builder in
app.services.responsible_ai wraps it in an untrusted-content envelope.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
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
from app.models.types import GUID, Embedding, JSONColumn, TimestampMixin, uuid_pk

# Dimension of the embedding vectors. Must match the configured embed model.
EMBEDDING_DIM = 768

RAG_CATEGORIES = [
    "investor-education",
    "financial-terminology",
    "fraud-awareness",
    "digital-safety",
    "investor-rights",
    "financial-literacy",
]


class RagDocument(Base, TimestampMixin):
    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False, index=True)

    # Provenance - required so the UI can attribute every retrieved claim.
    source: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(32), default="1")

    body: Mapped[str] = mapped_column(Text, default="")
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    # Marks material whose authority has been reviewed by an admin.
    authoritative: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    doc_metadata: Mapped[dict | None] = mapped_column(JSONColumn())

    chunks: Mapped[list["RagChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class RagChunk(Base, TimestampMixin):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunk_position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    heading: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(8), default="en", index=True)

    document: Mapped[RagDocument] = relationship(back_populates="chunks", lazy="joined")
    embeddings: Mapped[list["RagEmbedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class RagEmbedding(Base, TimestampMixin):
    """One vector per chunk per embedding model.

    Keeping the model name lets the corpus be re-embedded incrementally when
    the embedding model changes, without dropping the old index.
    """

    __tablename__ = "rag_embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", "model", name="uq_rag_embedding_chunk_model"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rag_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dim: Mapped[int] = mapped_column(Integer, default=EMBEDDING_DIM)
    vector: Mapped[list[float] | None] = mapped_column(Embedding(EMBEDDING_DIM))
    norm: Mapped[float] = mapped_column(Float, default=0.0)

    chunk: Mapped[RagChunk] = relationship(back_populates="embeddings")


Index("ix_rag_docs_cat_lang", RagDocument.category, RagDocument.language)
Index("ix_rag_chunks_doc_index", RagChunk.document_id, RagChunk.chunk_index)
