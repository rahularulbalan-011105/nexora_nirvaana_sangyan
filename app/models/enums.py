"""Domain enumerations.

Stored as strings so adding a value never needs a Postgres ENUM migration.
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Role(StrEnum):
    USER = "USER"
    FAMILY_ASSISTANT = "FAMILY_ASSISTANT"
    ADMIN = "ADMIN"
    DEMO_USER = "DEMO_USER"


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    TA = "ta"


class AnalysisStatus(StrEnum):
    """Deliberately non-accusatory. There is no 'safe' and no 'is a scam'."""

    MULTIPLE_SIGNALS = "MULTIPLE_SIGNALS_DETECTED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    NO_OBVIOUS_SIGNALS = "NO_OBVIOUS_WARNING_SIGNALS_DETECTED"


class SignalType(StrEnum):
    GUARANTEED_RETURN = "GUARANTEED_RETURN"
    UNREALISTIC_RETURN = "UNREALISTIC_RETURN"
    URGENCY = "URGENCY"
    LIMITED_TIME_PRESSURE = "LIMITED_TIME_PRESSURE"
    FOMO = "FOMO"
    SOCIAL_PRESSURE = "SOCIAL_PRESSURE"
    LOSS_RECOVERY_PROMPT = "LOSS_RECOVERY_PROMPT"
    IMPERSONATION = "IMPERSONATION"
    UNVERIFIED_REGULATORY_CLAIM = "UNVERIFIED_REGULATORY_CLAIM"
    SUSPICIOUS_LINK = "SUSPICIOUS_LINK"
    PAYMENT_REQUEST = "PAYMENT_REQUEST"
    PERSONAL_INFORMATION_REQUEST = "PERSONAL_INFORMATION_REQUEST"
    OTP_REQUEST = "OTP_REQUEST"
    CREDENTIAL_REQUEST = "CREDENTIAL_REQUEST"
    REMOTE_ACCESS_REQUEST = "REMOTE_ACCESS_REQUEST"
    UNKNOWN_DOMAIN = "UNKNOWN_DOMAIN"
    MISLEADING_TESTIMONIAL = "MISLEADING_TESTIMONIAL"
    FAKE_AUTHORITY = "FAKE_AUTHORITY"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InputKind(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    PDF = "PDF"
    URL = "URL"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PermissionScope(StrEnum):
    """What a FAMILY_ASSISTANT may see. Default is NONE."""

    NONE = "NONE"
    SAFETY_ONLY = "SAFETY_ONLY"
    LEARNING_ONLY = "LEARNING_ONLY"
    JOURNAL_SHARED = "JOURNAL_SHARED"


class InvitationStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class MemoryType(StrEnum):
    PREFERENCE = "PREFERENCE"
    GOAL = "GOAL"
    CONCERN = "CONCERN"
    CONTEXT = "CONTEXT"
    LEARNING = "LEARNING"


class ReflectionLabel(StrEnum):
    """The only labels a reflection may produce. Never BUY/SELL/INVEST."""

    GOOD = "Good"
    NEEDS_REVIEW = "Needs Review"
    PRESENT = "Present"
    DEVELOPING = "Developing"


class GuardrailAction(StrEnum):
    ALLOW = "ALLOW"
    TRANSFORM = "TRANSFORM"
    BLOCK = "BLOCK"
