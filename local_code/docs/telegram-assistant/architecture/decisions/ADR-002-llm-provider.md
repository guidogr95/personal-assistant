# ADR-002: OpenCode Go as LLM Provider

**Date:** 2025  
**Status:** Accepted

## Context

The agent framework (Pydantic AI) is provider-agnostic via OpenAI-compatible `base_url`. The operator has existing API keys for OpenCode Go and does not want to create additional accounts or billing relationships for a personal project. The provider must support tool/function calling (required for Pydantic AI's agent loop) and work with Pydantic AI's `OpenAIModel`.

## Decision

Use **OpenCode Go** as the sole LLM provider.

```python
# OpenCode Go is OpenAI-API compatible
model = OpenAIModel(
    model_name=settings.OPENCODE_MODEL,   # from /models endpoint
    base_url="https://opencode.ai/zen/go/v1",
    api_key=settings.OPENCODE_API_KEY,
)
```

Model selection: query `GET https://opencode.ai/zen/go/v1/models` at setup time to discover available models. Set `OPENCODE_MODEL` in `.env`.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **OpenAI (gpt-4o)** | Additional billing relationship; operator already has OpenCode Go keys |
| **Anthropic Claude direct** | Not OpenAI-compatible at the API level; requires separate Pydantic AI model class (`AnthropicModel`); adds dependency complexity |
| **Ollama (local)** | VPS RAM constraint (~3GB shared across all services); running a 7B+ model locally would exceed available memory; latency on small VPS unacceptable |
| **Groq** | Free tier has strict rate limits that would impact reliability; no existing account |

## Consequences

- `OPENCODE_API_KEY` and `OPENCODE_MODEL` must be present in `.env`; validated at startup by `pydantic-settings`
- If OpenCode Go changes its API URL or auth scheme, only `shared/config.py` and `.env.example` need updating
- Model is configurable without code changes (env var only)
- If switching providers in future: change `base_url` + `api_key` env vars; Pydantic AI's `OpenAIModel` supports any OpenAI-compatible endpoint
