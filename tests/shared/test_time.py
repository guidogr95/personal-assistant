"""Tests for shared time utilities."""

from __future__ import annotations

import pytest

from assistant.shared.time import get_current_time


class TestGetCurrentTime:
    def test_returns_string_with_local_and_utc(self) -> None:
        result = get_current_time("America/Guayaquil")
        assert result.startswith("Local: ")
        assert "America/Guayaquil" in result
        assert "UTC-5" in result or "UTC+" in result or "UTC-" in result
        assert "| UTC:" in result

    def test_includes_utc_offset(self) -> None:
        # Guayaquil is permanently UTC-5 (no DST)
        result = get_current_time("America/Guayaquil")
        assert "UTC-5" in result

    def test_uses_configured_timezone_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("assistant.shared.time.settings.timezone", "Europe/London")
        result = get_current_time()
        assert "Europe/London" in result
        assert "| UTC:" in result

    def test_invalid_timezone_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown timezone"):
            get_current_time("NotAReal/Timezone")

    def test_format_includes_local_and_utc_sections(self) -> None:
        result = get_current_time("UTC")
        # Expected: "Local: 2026-06-01 01:50:00 (UTC, UTC+0) | UTC: 2026-06-01 01:50:00"
        assert result.startswith("Local: ")
        assert "| UTC:" in result
        local_part, utc_part = result.split("| UTC:")
        # local part has a date-time and a parenthesised tz block
        assert "UTC" in local_part
        # UTC part is a bare datetime string
        assert utc_part.strip().count(" ") == 1  # "YYYY-MM-DD HH:MM:SS"
