"""Aggregated model imports.

Importing this package registers every table on ``Base.metadata``, which is
what Alembic autogenerate and ``create_all`` rely on.
"""
from __future__ import annotations

from app.db import Base
from app.models.analysis import (
    AnalysisSignal,
    AnalysisSource,
    BatchItem,
    BatchJob,
    MessageAnalysis,
    SafetyRule,
    UploadedFile,
)
from app.models.enums import (
    AnalysisStatus,
    GuardrailAction,
    InputKind,
    InvitationStatus,
    JobStatus,
    Language,
    MemoryType,
    PermissionScope,
    ReflectionLabel,
    Role,
    Severity,
    SignalType,
)
from app.models.family import FamilyInvitation, FamilyPermission, FamilyRelationship
from app.models.learning import LEARNING_CATEGORIES, LearningContent, LearningProgress
from app.models.market import (
    MARKET_CONCEPTS,
    MarketDataCache,
    MarketEducationalScenario,
)
from app.models.rag import (
    EMBEDDING_DIM,
    RAG_CATEGORIES,
    RagChunk,
    RagDocument,
    RagEmbedding,
)
from app.models.reflection import (
    JournalEntry,
    Memory,
    ReflectionAnswer,
    ReflectionSession,
)
from app.models.system import AuditLog, FeatureFlag, Notification, SystemEvent
from app.models.user import (
    EmailVerification,
    PasswordReset,
    RoleRow,
    Session,
    User,
    UserPreferences,
    UserPrivacySettings,
    UserRole,
)
from app.models.voice import VoiceMessage, VoiceSession

__all__ = [
    "Base",
    # enums
    "AnalysisStatus",
    "GuardrailAction",
    "InputKind",
    "InvitationStatus",
    "JobStatus",
    "Language",
    "MemoryType",
    "PermissionScope",
    "ReflectionLabel",
    "Role",
    "Severity",
    "SignalType",
    # identity
    "User",
    "RoleRow",
    "UserRole",
    "Session",
    "EmailVerification",
    "PasswordReset",
    "UserPreferences",
    "UserPrivacySettings",
    # family
    "FamilyRelationship",
    "FamilyPermission",
    "FamilyInvitation",
    # reflection
    "JournalEntry",
    "Memory",
    "ReflectionSession",
    "ReflectionAnswer",
    # learning
    "LearningContent",
    "LearningProgress",
    "LEARNING_CATEGORIES",
    # analysis
    "MessageAnalysis",
    "AnalysisSignal",
    "AnalysisSource",
    "SafetyRule",
    "UploadedFile",
    "BatchJob",
    "BatchItem",
    # voice
    "VoiceSession",
    "VoiceMessage",
    # rag
    "RagDocument",
    "RagChunk",
    "RagEmbedding",
    "EMBEDDING_DIM",
    "RAG_CATEGORIES",
    # market
    "MarketDataCache",
    "MarketEducationalScenario",
    "MARKET_CONCEPTS",
    # system
    "Notification",
    "AuditLog",
    "SystemEvent",
    "FeatureFlag",
]
