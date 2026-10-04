"""Family Mode: invitation, explicit consent, scoped access, revocation.

Access is deny-by-default. A relationship grants nothing until the owner
accepts an invitation AND a permission row exists for the scope being read.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import InvitationStatus, PermissionScope
from app.models.types import GUID, TimestampMixin, uuid_pk


class FamilyRelationship(Base, TimestampMixin):
    """Links the account owner to a trusted assistant.

    ``owner_user_id`` is the person whose data may be shared.
    ``assistant_user_id`` is the family member being granted scoped access.
    """

    __tablename__ = "family_relationships"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "assistant_user_id", name="uq_family_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assistant_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    relationship_label: Mapped[str] = mapped_column(String(48), default="family")
    # Consent is recorded explicitly, with a timestamp, and can be withdrawn.
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str] = mapped_column(String(16), default="v1")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    permissions: Mapped[list["FamilyPermission"]] = relationship(
        back_populates="relationship_row", cascade="all, delete-orphan", lazy="selectin"
    )
    invitations: Mapped[list["FamilyInvitation"]] = relationship(
        back_populates="relationship_row", cascade="all, delete-orphan"
    )

    @property
    def granted_scopes(self) -> set[str]:
        if not self.active or self.revoked_at is not None:
            return set()
        return {p.scope for p in self.permissions if p.granted}

    def allows(self, scope: PermissionScope | str) -> bool:
        return str(scope) in self.granted_scopes


class FamilyPermission(Base, TimestampMixin):
    __tablename__ = "family_permissions"
    __table_args__ = (
        UniqueConstraint("relationship_id", "scope", name="uq_family_permission_scope"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    relationship_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("family_relationships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(24), default=PermissionScope.NONE.value, nullable=False
    )
    granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    relationship_row: Mapped[FamilyRelationship] = relationship(back_populates="permissions")


class FamilyInvitation(Base, TimestampMixin):
    __tablename__ = "family_invitations"

    id: Mapped[uuid.UUID] = uuid_pk()
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("family_relationships.id", ondelete="CASCADE"), index=True
    )
    # The account that sent the invitation.
    inviter_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invitee_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default=InvitationStatus.PENDING.value, nullable=False, index=True
    )
    # Scopes the invitation asks for; the owner confirms them on acceptance.
    requested_scopes: Mapped[str] = mapped_column(Text, default="")
    message: Mapped[str | None] = mapped_column(Text)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    relationship_row: Mapped[FamilyRelationship | None] = relationship(
        back_populates="invitations"
    )

    @property
    def requested_scope_list(self) -> list[str]:
        return [s for s in (self.requested_scopes or "").split(",") if s]


Index(
    "ix_family_rel_owner_active",
    FamilyRelationship.owner_user_id,
    FamilyRelationship.active,
)
Index(
    "ix_family_rel_assistant_active",
    FamilyRelationship.assistant_user_id,
    FamilyRelationship.active,
)
