from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject

from assistant.shared.config import settings

logger = structlog.get_logger()


class AllowedUserMiddleware(BaseMiddleware):
    """Silently reject all updates that do not originate from the configured user.

    This is the single enforcement point for user authorization.
    No handler should duplicate this check.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401 — required by aiogram BaseMiddleware protocol
        user = data.get("event_from_user")
        if user is not None and user.id != settings.telegram_allowed_user_id:
            logger.warning("unauthorized_update_rejected", user_id=user.id)
            return None
        return await handler(event, data)
