"""Content hashing helpers for raw evidence payloads."""

import hashlib


def content_hash(data: bytes) -> str:
    """Return a lowercase SHA-256 digest for the provided payload."""
    return hashlib.sha256(data).hexdigest()

