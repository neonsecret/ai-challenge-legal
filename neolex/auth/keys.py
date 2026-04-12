"""API key utility functions — generation, hashing, and prefix extraction.

The raw key is never stored. Only its SHA-256 hash goes to the DB.
The first 8 characters of the raw key are stored as key_prefix for fast lookup.
"""

import hashlib
import secrets


def generate_key() -> str:
    """Return a new random API key (raw, not hashed)."""
    return secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def key_prefix(raw_key: str) -> str:
    """Return the first 8 characters of *raw_key* for fast DB prefix lookups."""
    return raw_key[:8]
