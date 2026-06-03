"""Tests for file request state management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from assistant.telegram.pending_state import (
    _MAX_FILE_REQUEST_AGE,
    _pending_file_requests,
    get_file_request,
    store_file_request,
)


class TestFileRequestState:
    """Test cases for file request storage and retrieval."""

    def setup_method(self) -> None:
        """Clear the file requests dict before each test."""
        _pending_file_requests.clear()

    def test_should_store_and_retrieve_file_request(self) -> None:
        store_file_request("hash123", "note.md")
        result = get_file_request("hash123")
        assert result == "note.md"

    def test_should_return_none_for_missing_hash(self) -> None:
        result = get_file_request("nonexistent")
        assert result is None

    def test_should_return_none_for_expired_request(self) -> None:
        store_file_request("hash456", "old_note.md")
        # Manually backdate the entry to simulate expiration
        _pending_file_requests["hash456"] = (
            "old_note.md",
            datetime.now(UTC) - _MAX_FILE_REQUEST_AGE - timedelta(minutes=1),
        )
        result = get_file_request("hash456")
        assert result is None
        assert "hash456" not in _pending_file_requests

    def test_should_remove_expired_entry_on_access(self) -> None:
        store_file_request("hash789", "note.md")
        _pending_file_requests["hash789"] = (
            "note.md",
            datetime.now(UTC) - _MAX_FILE_REQUEST_AGE - timedelta(seconds=1),
        )
        get_file_request("hash789")
        assert "hash789" not in _pending_file_requests

    def test_should_allow_multiple_concurrent_requests(self) -> None:
        store_file_request("hash1", "note1.md")
        store_file_request("hash2", "note2.md")
        assert get_file_request("hash1") == "note1.md"
        assert get_file_request("hash2") == "note2.md"
