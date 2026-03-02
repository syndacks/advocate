"""Unit tests for content hashing helpers."""

from advocate.ingestion.hashing import content_hash


def test_content_hash_returns_sha256_hex_digest() -> None:
    assert (
        content_hash(b"hello world")
        == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )
