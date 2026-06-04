"""Telegram handler package with auto-discovery for routers and commands.

Each handler module may export:
- ``router`` (aiogram.Router) — registered automatically via ``discover_routers()``.
- ``COMMANDS`` (list[BotCommand]) — collected automatically via ``discover_commands()``.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import cast

from aiogram import Router
from aiogram.types import BotCommand

__all__ = ["discover_routers", "discover_commands"]


def discover_routers() -> list[tuple[str, Router]]:
    """Auto-discover all aiogram Router instances in this package.

    Returns a list of (module_name, router) tuples so the caller can
    control registration order (e.g. errors first, catch-all message last).
    """
    routers: list[tuple[str, Router]] = []
    for _, name, _ in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{name}")
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if isinstance(obj, Router):
                routers.append((name, obj))
    return routers


def discover_commands() -> list[BotCommand]:
    """Auto-discover all BotCommand lists exported by handler modules."""
    commands: list[BotCommand] = []
    for _, name, _ in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{name}")
        if hasattr(module, "COMMANDS"):
            commands.extend(cast(list[BotCommand], module.COMMANDS))
    return commands
