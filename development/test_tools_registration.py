"""Scratch test: verify ALL_TOOLS is populated correctly after the __init__.py fix.

This script mirrors exactly what the /tools command does at runtime:
  1. Import from the tools package (triggers __init__.py, registers all @tool decorators)
  2. Check every expected tool is in ALL_TOOLS and _TOOL_CATEGORIES
  3. Run _categorize_tools() — the same function /tools calls — and print the output
  4. Exit 0 on success, 1 on any failure

Run from project root:
    python development/test_tools_registration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src))

# ── Import the package. This is what main.py does when it runs
# `from assistant.agent.tools.registry import ALL_TOOLS`.
# __init__.py fires and registers all 8 tool modules.
from assistant.agent.tools.registry import _TOOL_CATEGORIES, ALL_TOOLS  # noqa: E402

EXPECTED: dict[str, str] = {
    # Notes
    "create_note": "📝 Notes",
    "search_notes": "📝 Notes",
    "read_note_by_name": "📝 Notes",
    "update_note": "📝 Notes",
    "list_notes_in_vault": "📝 Notes",
    "delete_note": "📝 Notes",
    # Tasks
    "add_task": "✅ Tasks",
    "get_open_tasks": "✅ Tasks",
    "mark_task_done": "✅ Tasks",
    # Check-ins
    "schedule_checkin": "⏰ Check-ins",
    "list_scheduled_checkins": "⏰ Check-ins",
    "remove_checkin": "⏰ Check-ins",
    # Reminders
    "set_reminder": "🔔 Reminders",
    # Video
    "get_video_transcript": "🎬 Video",
    "get_transcription_queue_status": "🎬 Video",
    # Research
    "search": "🔍 Research",
    "fetch_url": "🔍 Research",
    # Time
    "get_current_time": "🕐 Time",
    # System
    "show_system_prompt": "⚙️ System",
    "update_system_prompt": "⚙️ System",
}

failures: list[str] = []

# ── Check 1: count ────────────────────────────────────────────────────────────
print(f"ALL_TOOLS count : {len(ALL_TOOLS)}")
print(f"Expected        : {len(EXPECTED)}")
if len(ALL_TOOLS) != len(EXPECTED):
    failures.append(f"Count mismatch: got {len(ALL_TOOLS)}, expected {len(EXPECTED)}")

# ── Check 2: every expected tool is registered with the right category ────────
registered_names = {fn.__name__ for fn in ALL_TOOLS}
for name, expected_cat in EXPECTED.items():
    if name not in registered_names:
        failures.append(f"MISSING from ALL_TOOLS: {name}")
        continue
    actual_cat = _TOOL_CATEGORIES.get(name)
    if actual_cat != expected_cat:
        failures.append(
            f"Wrong category for {name!r}: got {actual_cat!r}, expected {expected_cat!r}"
        )

# ── Check 3: no unexpected extras ────────────────────────────────────────────
for name in registered_names:
    if name not in EXPECTED:
        failures.append(f"UNEXPECTED tool in ALL_TOOLS: {name}")

# ── Check 4: run _categorize_tools() — the exact function /tools calls ────────
# Build python_tools dict the same way tool_commands.py does it
from assistant.telegram.handlers.tool_commands import (  # noqa: E402
    _build_all_tools_markdown,
    _categorize_tools,
)

python_tools: dict[str, str] = {fn.__name__: (fn.__doc__ or "").strip() for fn in ALL_TOOLS}
categorized = _categorize_tools(python_tools, mcp_tools=None)

print("\n── /tools output (mcp_tools=None) ─────────────────────────────────────")
chunks = _build_all_tools_markdown(categorized)
for chunk in chunks:
    print(chunk)
    print()

# ── Check 5: every expected category appears in the output ────────────────────
all_output = "\n".join(chunks)
expected_categories = set(EXPECTED.values())
for cat in expected_categories:
    if cat not in all_output:
        failures.append(f"Category {cat!r} missing from _build_all_tools_markdown output")

# ── Result ────────────────────────────────────────────────────────────────────
print("─" * 60)
if failures:
    print(f"\n❌ {len(failures)} failure(s):")
    for f in failures:
        print(f"   • {f}")
    sys.exit(1)
else:
    print(f"\n✅ All {len(EXPECTED)} tools registered with correct categories.")
    sys.exit(0)
