"""API key generation, hashing, and verification utilities.

Keys are generated with secrets.token_urlsafe(32) — 43 URL-safe chars, ~256 bits.
Only SHA-256 hashes are stored. Plaintext keys are shown exactly once on creation.
Comparison uses hmac.compare_digest to prevent timing side-channel attacks.
"""
import hashlib
import hmac
import secrets


def generate_key() -> str:
    """Generate a new cryptographically secure API key.

    Returns 43-character URL-safe base64 string (256 bits of entropy).
    This value is shown ONCE to the admin and NEVER stored anywhere.
    """
    return secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw API key.

    This is the value stored in the database and compared during validation.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_key(raw_key: str, stored_hash: str) -> bool:
    """Return True iff raw_key hashes to stored_hash.

    Uses hmac.compare_digest for constant-time comparison to prevent
    timing side-channel attacks against the hash comparison.
    """
    candidate = hash_key(raw_key)
    return hmac.compare_digest(candidate, stored_hash)


def key_prefix(raw_key: str) -> str:
    """Return first 8 characters of raw_key for display/logging purposes.

    Never log or store more than this prefix — it is not enough to reconstruct
    the full key but sufficient to identify which key was used in audit logs.
    """
    return raw_key[:8]
