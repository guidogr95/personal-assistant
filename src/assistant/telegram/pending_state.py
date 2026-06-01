"""Ephemeral in-process state for Telegram UI interactions requiring confirmation.

This module holds pending deletion requests so both the message handler
(which creates them) and the callback handler (which resolves them) share
the same dict without a circular import.

State is lost on bot restart — buttons from a previous session will show
"no pending deletion" rather than silently deleting or crashing.
"""

from __future__ import annotations

# Maps user_id → filename awaiting delete confirmation.
pending_deletions: dict[int, str] = {}
