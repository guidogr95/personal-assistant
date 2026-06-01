from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables.

    Raises ValidationError at import time if any required variable is missing or malformed.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Docker Compose vars (VIKUNJA_DB_PASSWORD, TZ, etc.) live in .env too
        # but are not needed by the Python app — ignore them silently.
        extra="ignore",
    )

    # LLM
    opencode_api_key: str
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_model: str

    # Telegram
    telegram_bot_token: str
    telegram_allowed_user_id: int

    # Storage
    sqlite_path: str = "/data/assistant.db"
    notes_vault_path: str = "/srv/notes"

    # Services
    memory_service_url: str
    searxng_url: str
    vikunja_url: str
    vikunja_api_token: str = ""  # required from Phase 5 (task management)

    # Alarms
    autoremote_key: str = ""  # required from Phase 7 (calendar/alarms)

    # Google Calendar — optional until Phase 7
    google_client_id: str = ""
    google_client_secret: str = ""
    google_token_json_path: str = "/data/google_token.json"  # noqa: S105 — file path, not a secret

    # Misc
    log_level: str = "INFO"


settings = Settings()
