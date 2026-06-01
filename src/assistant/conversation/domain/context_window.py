from __future__ import annotations

from assistant.conversation.domain.turn import Turn, TurnRole

MAX_VERBATIM_TURNS = 20


def build_verbatim_window(turns: list[Turn]) -> list[Turn]:
    """Return the last MAX_VERBATIM_TURNS user/assistant turns for display or reconstruction.

    Excludes tool_call, tool_result, and summary roles — those are not useful
    for human-readable history display. The authoritative LLM context is the
    pydantic-ai message_history_json blob on the Session entity.
    """
    llm_turns = [t for t in turns if t.role in (TurnRole.USER, TurnRole.ASSISTANT)]
    return llm_turns[-MAX_VERBATIM_TURNS:]
