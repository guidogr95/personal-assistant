class AssistantError(Exception):
    """Base exception for all domain errors."""


class SessionNotFoundError(AssistantError):
    """Raised when a requested session does not exist."""


class NoActiveSessionError(AssistantError):
    """Raised when an operation requires an active session but none exists."""


class SessionAlreadyActiveError(AssistantError):
    """Raised when trying to open a session while one is already active."""


class InvalidSessionStateError(AssistantError):
    """Raised when a session state transition is not permitted."""


class InfrastructureError(AssistantError):
    """Wraps external service failures to preserve the cause chain."""


class LLMUnavailableError(AssistantError):
    """Raised when the LLM provider rejects or fails to process a request.

    Carries a user_message suitable for display in Telegram so that the
    Telegram layer never needs to import pydantic-ai exception types.
    """

    def __init__(self, user_message: str, cause: Exception) -> None:
        self.user_message = user_message
        super().__init__(user_message)


class CheckInNotFoundError(AssistantError):
    """Raised when a requested ScheduledCheckIn does not exist."""
