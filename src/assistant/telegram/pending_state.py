"""Ephemeral in-process state for Telegram UI interactions requiring confirmation.

This module holds pending deletion requests and file download requests so
both the message handler (which creates them) and the callback handler
(which resolves them) share the same dicts without a circular import.

State is lost on bot restart — buttons from a previous session will show
"no pending deletion" or "request expired" rather than silently acting or
 crashing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Maps user_id → filename awaiting delete confirmation.
pending_deletions: dict[int, str] = {}

# Maps hash → (filename, created_at) for long-text file requests.
_pending_file_requests: dict[str, tuple[str, datetime]] = {}
_MAX_FILE_REQUEST_AGE: timedelta = timedelta(hours=1)


def store_file_request(request_hash: str, filename: str) -> None:
    """Store a file request so the callback handler can resolve it later."""
    _pending_file_requests[request_hash] = (filename, datetime.now(UTC))


def get_file_request(request_hash: str) -> str | None:
    """Return the filename for a stored file request, or None if expired/missing."""
    entry = _pending_file_requests.get(request_hash)
    if entry is None:
        return None
    filename, created_at = entry
    if datetime.now(UTC) - created_at > _MAX_FILE_REQUEST_AGE:
        del _pending_file_requests[request_hash]
        return None
    return filename
