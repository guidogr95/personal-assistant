from __future__ import annotations

import structlog
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ToolReturnPart

from assistant.agent.domain.agent import _SYSTEM_PROMPT, agent
from assistant.agent.tools.notes_tools import DELETE_CONFIRM_SENTINEL
from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.conversation.domain.turn import Turn, TurnRole
from assistant.prompts.application.get_system_prompt import get_system_prompt
from assistant.prompts.domain.prompt_repository import PromptRepository
from assistant.shared.exceptions import (
    InfrastructureError,
    LLMUnavailableError,
    NoActiveSessionError,
)

logger = structlog.get_logger()

_BILLING_ERROR_TYPES = frozenset({"CreditsError", "InsufficientCredits"})


def _user_message_for_http_error(error: ModelHTTPError) -> str:
    """Derive a Telegram-safe user message from a ModelHTTPError.

    Avoids leaking internal URLs or raw API payloads to the user.
    """
    body = error.body
    if isinstance(body, dict):
        error_type = body.get("type", "")
        if error_type in _BILLING_ERROR_TYPES or "balance" in str(body).lower():
            return "The AI provider rejected the request due to insufficient credits."
        if error.status_code == 429:
            return "The AI provider is rate-limiting requests. Please try again in a moment."
    if error.status_code >= 500:
        return "The AI provider is temporarily unavailable. Please try again shortly."
    return f"The AI provider returned an error (HTTP {error.status_code}). Please try again."


def _find_sentinel_in_messages(messages: list[ModelMessage]) -> str | None:
    """Return the first sentinel string found in tool return parts, or None.

    pydantic-ai feeds tool return values back to the LLM, which then writes
    its own reply.  For sentinels that must reach the Telegram layer verbatim
    (e.g. delete confirmation), we intercept the tool return value here and
    return it as the reply, bypassing the LLM's paraphrase.
    """
    for message in messages:
        for part in message.parts:
            if (
                isinstance(part, ToolReturnPart)
                and isinstance(part.content, str)
                and part.content.startswith(DELETE_CONFIRM_SENTINEL)
            ):
                return part.content
    return None


async def run_turn(
    user_id: int,
    user_message: str,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
    prompt_repo: PromptRepository,
) -> str:
    """Execute one conversational turn: run the agent and persist the exchange.

    Loads the pydantic-ai message history from the session blob so the LLM
    receives full conversation context without reconstructing from Turn rows.

    Raises:
        NoActiveSessionError: if no active session exists for the user.
        LLMUnavailableError: if the LLM provider rejects or fails the request.
    """
    session = await session_repo.get_active_for_user(user_id)
    if session is None:
        raise NoActiveSessionError(f"No active session for user {user_id}")

    message_history = (
        ModelMessagesTypeAdapter.validate_json(session.message_history_json)
        if session.message_history_json
        else []
    )

    # Load the active system prompt from DB.  If the DB is unreachable,
    # fall back to the hardcoded default so the turn never fails because
    # of a prompt table error.
    try:
        instructions = await get_system_prompt(prompt_repo)
    except InfrastructureError:
        logger.warning("prompt_db_unavailable_using_fallback", session_id=session.id)
        instructions = _SYSTEM_PROMPT

    logger.info(
        "run_turn_start",
        session_id=session.id,
        history_messages=len(message_history),
    )

    try:
        result = await agent.run(
            user_message, message_history=message_history, instructions=instructions
        )
    except ModelHTTPError as exc:
        logger.error(
            "llm_http_error",
            session_id=session.id,
            status_code=exc.status_code,
            model=exc.model_name,
        )
        raise LLMUnavailableError(_user_message_for_http_error(exc), cause=exc) from exc

    # If a tool returned a sentinel (e.g. delete confirmation), surface it
    # directly rather than the LLM's chatty paraphrase of it.
    sentinel_reply = _find_sentinel_in_messages(result.new_messages())
    reply: str = sentinel_reply if sentinel_reply is not None else result.output

    user_turn = Turn(session_id=session.id, role=TurnRole.USER, content=user_message)
    assistant_turn = Turn(session_id=session.id, role=TurnRole.ASSISTANT, content=reply)
    await turn_repo.save(user_turn)
    await turn_repo.save(assistant_turn)

    # Persist updated message history blob and refresh last_active on the session
    session.update_message_history(ModelMessagesTypeAdapter.dump_json(result.all_messages()))
    session.touch()
    await session_repo.save(session)

    logger.info("run_turn_complete", session_id=session.id)
    return reply
