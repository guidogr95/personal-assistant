"""Tests for shared time utilities."""

from __future__ import annotations

import pytest

from assistant.shared.time import get_current_time


class TestGetCurrentTime:
    def test_returns_string_with_timezone(self) -> None:
        result = get_current_time("America/Guayaquil")
        assert result.startswith("Current time: ")
        assert "(America/Guayaquil)" in result

    def test_uses_configured_timezone_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("assistant.shared.time.settings.timezone", "Europe/London")
        result = get_current_time()
        assert "(Europe/London)" in result

    def test_invalid_timezone_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown timezone"):
            get_current_time("NotAReal/Timezone")

    def test_format_includes_date_time_and_tz(self) -> None:
        result = get_current_time("UTC")
        # Expected: "Current time: 2026-06-01 14:30:00 (UTC)"
        parts = result.replace("Current time: ", "").split(" ")
        assert len(parts) == 3  # date, time, (tz)
        assert parts[2].startswith("(") and parts[2].endswith(")")
