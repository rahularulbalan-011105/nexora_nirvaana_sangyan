"""Password hashing and strength checks.

Argon2id with the argon2-cffi defaults. Plaintext passwords are never stored,
logged, or written to the audit trail.
"""
from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Argon2id. Defaults are deliberately left in place: argon2-cffi tracks the
# current OWASP guidance, so hard-coding cost parameters here would age badly.
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 10

# A short deny-list of obvious choices. Not a substitute for length.
_COMMON = {
    "password",
    "password1",
    "12345678",
    "123456789",
    "qwertyuiop",
    "letmein",
    "iloveyou",
    "admin123",
    "nirvaan123",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification. Returns False rather than raising."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses outdated parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_problems(password: str, *, email: str = "", name: str = "") -> list[str]:
    """Human-readable reasons a password is unacceptable. Empty list == OK."""
    problems: list[str] = []
    pw = password or ""

    if len(pw) < MIN_PASSWORD_LENGTH:
        problems.append(
            f"Use at least {MIN_PASSWORD_LENGTH} characters. "
            "A short phrase you can remember works well."
        )
    # Compare against the deny-list with punctuation stripped, so that
    # "password1!" is caught as readily as "password1".
    normalised = re.sub(r"[^a-z0-9]", "", pw.lower())
    if pw.lower() in _COMMON or normalised in _COMMON:
        problems.append("That password is very commonly used. Please choose another.")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        problems.append("Include at least one letter and one number.")

    local = (email or "").split("@")[0].lower()
    if local and len(local) >= 4 and local in pw.lower():
        problems.append("Avoid using your email address inside your password.")
    first = (name or "").strip().split(" ")[0].lower()
    if first and len(first) >= 4 and first in pw.lower():
        problems.append("Avoid using your name inside your password.")

    return problems
