"""Role and ownership enforcement.

The spec requires authorization at three layers. This module is the second and
third: route guards (``require_roles``) and a query-layer guard
(``owned_by``/``OwnedRepo``) that makes it hard to write a cross-user read by
accident. Template visibility is the first layer and is cosmetic only.
"""
from __future__ import annotations

import uuid
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.models.enums import PermissionScope, Role
from app.models.family import FamilyRelationship
from app.models.user import User

T = TypeVar("T")

# Resources an ADMIN may never read just by virtue of being an admin.
# Enforced by `assert_not_private_for_admin`, and mirrored in the admin routes.
PRIVATE_FROM_ADMIN = {
    "journal_entries",
    "memories",
    "voice_messages",
    "voice_sessions",
    "reflection_answers",
    "message_analyses",
}


class Forbidden(HTTPException):
    def __init__(self, detail: str = "You do not have access to this resource.") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class Unauthorized(HTTPException):
    def __init__(self, detail: str = "Please sign in to continue.") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def require_roles(user: User | None, *roles: Role | str) -> User:
    """Assert the user holds at least one of ``roles``."""
    if user is None:
        raise Unauthorized()
    wanted = {str(r) for r in roles}
    if not wanted:
        return user
    if not (user.role_names & wanted):
        raise Forbidden(
            "This area needs " + " or ".join(sorted(wanted)) + " access."
        )
    return user


def require_admin(user: User | None) -> User:
    return require_roles(user, Role.ADMIN)


def owned_by(stmt: Select, model: Any, user: User) -> Select:
    """Force a ``user_id`` predicate onto a select.

    Every user-owned table carries ``user_id``; routing all reads through this
    helper means forgetting the filter raises instead of leaking rows.
    """
    column = getattr(model, "user_id", None)
    if column is None:
        raise TypeError(
            f"{getattr(model, '__name__', model)} has no user_id column; "
            "it is not a user-owned resource."
        )
    return stmt.where(column == user.id)


class OwnedRepo:
    """Narrow repository for user-owned rows.

    Reads and deletes are always scoped to the owning user, so a wrong or
    guessed id returns nothing rather than another person's row.
    """

    def __init__(self, db: DbSession, model: Any, user: User) -> None:
        if not hasattr(model, "user_id"):
            raise TypeError(f"{model!r} is not a user-owned model.")
        self.db = db
        self.model = model
        self.user = user

    def select(self) -> Select:
        return owned_by(select(self.model), self.model, self.user)

    def get(self, row_id: uuid.UUID | str) -> Any | None:
        try:
            key = row_id if isinstance(row_id, uuid.UUID) else uuid.UUID(str(row_id))
        except (ValueError, AttributeError, TypeError):
            return None
        return self.db.execute(self.select().where(self.model.id == key)).scalar_one_or_none()

    def get_or_404(self, row_id: uuid.UUID | str) -> Any:
        row = self.get(row_id)
        if row is None:
            # 404 rather than 403: do not confirm that someone else's id exists.
            raise HTTPException(status_code=404, detail="Not found.")
        return row

    def list(self, *, limit: int = 50, offset: int = 0, order_desc: bool = True) -> list[Any]:
        stmt = self.select()
        created = getattr(self.model, "created_at", None)
        if created is not None:
            stmt = stmt.order_by(created.desc() if order_desc else created.asc())
        return list(self.db.execute(stmt.limit(limit).offset(offset)).scalars())

    def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return int(self.db.execute(owned_by(stmt, self.model, self.user)).scalar() or 0)

    def add(self, **fields: Any) -> Any:
        row = self.model(user_id=self.user.id, **fields)
        self.db.add(row)
        return row

    def delete(self, row_id: uuid.UUID | str) -> bool:
        row = self.get(row_id)
        if row is None:
            return False
        self.db.delete(row)
        return True


def family_scope_allows(
    db: DbSession, *, assistant: User, owner_id: uuid.UUID, scope: PermissionScope | str
) -> bool:
    """True only when an active, consented relationship grants ``scope``.

    Deny-by-default: absent relationship, missing consent, revoked access or an
    unlisted scope all return False.
    """
    rel = db.execute(
        select(FamilyRelationship).where(
            FamilyRelationship.owner_user_id == owner_id,
            FamilyRelationship.assistant_user_id == assistant.id,
            FamilyRelationship.active.is_(True),
            FamilyRelationship.revoked_at.is_(None),
        )
    ).scalar_one_or_none()

    if rel is None or rel.consent_granted_at is None:
        return False
    return rel.allows(scope)


def assert_family_scope(
    db: DbSession, *, assistant: User, owner_id: uuid.UUID, scope: PermissionScope | str
) -> None:
    if not family_scope_allows(db, assistant=assistant, owner_id=owner_id, scope=scope):
        raise Forbidden(
            "This account has not shared that information with you."
        )


def assert_not_private_for_admin(resource_type: str) -> None:
    """Guard used by admin routes.

    Being an ADMIN grants operational access, not access to private content.
    """
    if resource_type in PRIVATE_FROM_ADMIN:
        raise Forbidden(
            "Admin access does not include private user content. "
            "This request was refused and logged."
        )
