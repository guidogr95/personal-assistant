"""Root-level pytest configuration.

Sets NOTES_VAULT_PATH to a writable temp directory before any test file is
imported. Without this, notes_tools.py's module-level MarkdownNoteRepository()
creation would fail when /srv/notes is not accessible in the test environment.

This must be done at module level (not inside a fixture) so it runs before pytest
collects and imports test files.
"""

from __future__ import annotations

import os
import tempfile

# Only override if not already set in the environment — preserves local dev
# overrides while ensuring CI and fresh environments always get a writable path.
if "NOTES_VAULT_PATH" not in os.environ:
    os.environ["NOTES_VAULT_PATH"] = tempfile.mkdtemp()
