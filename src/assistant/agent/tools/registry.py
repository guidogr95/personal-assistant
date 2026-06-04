"""Tool registry for auto-discovery of agent tools.

Importing this module does NOT import any tool modules, avoiding circular
dependencies. Tools are collected at decoration time when each tool module
is imported by the application layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, get_args, overload

# All valid tool category display names. This is the single source of truth —
# the @tool decorator enforces membership at type-check time.
ToolCategory = Literal[
    "📝 Notes",
    "✅ Tasks",
    "⏰ Check-ins",
    "🔔 Reminders",
    "🎬 Video",
    "🔍 Research",
    "🕐 Time",
    "⚙️ System",
    "🧠 Memory",
    "📦 Other",
]

# Any is required: tools have heterogeneous signatures (different parameters and
# return types across all registered tools). This is the honest annotation for a
# polymorphic callable collection; pydantic-ai accepts Callable[..., Any].
ALL_TOOLS: list[Callable[..., Any]] = []

# tool_name → category display name (e.g. "🕐 Time").
# Populated by the @tool decorator so each tool declares its own category.
_TOOL_CATEGORIES: dict[str, ToolCategory] = {}


@overload
def tool[T](fn: Callable[..., T]) -> Callable[..., T]: ...
@overload
def tool[T](
    fn: None = None, *, category: ToolCategory = ...
) -> Callable[[Callable[..., T]], Callable[..., T]]: ...
def tool[T](
    fn: Callable[..., T] | None = None,
    *,
    category: ToolCategory = "📦 Other",
) -> Callable[..., T] | Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that registers a function as an agent tool.

    Each tool declares its own display category. The /tools command builds
    the category list dynamically — no central map to maintain.

    Usage without category (defaults to 📦 Other)::

        @tool
        async def my_tool(ctx: RunContext[AgentDeps], ...) -> str:
            ...

    Usage with category::

        @tool(category="🕐 Time")
        async def get_current_time(ctx: RunContext[AgentDeps]) -> str:
            ...
    """

    def decorator(f: Callable[..., T]) -> Callable[..., T]:
        valid_categories = get_args(ToolCategory)
        if category not in valid_categories:
            raise ValueError(
                f"@tool category {category!r} is not a valid ToolCategory. "
                f"Add it to the ToolCategory Literal in registry.py first."
            )
        if f not in ALL_TOOLS:
            ALL_TOOLS.append(f)
        _TOOL_CATEGORIES[f.__name__] = category
        return f

    if fn is None:
        return decorator
    return decorator(fn)
