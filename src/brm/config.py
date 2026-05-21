"""Application settings loaded from environment / .env file.

All secrets (database password, Anthropic key, API key) are read exclusively
from environment variables or a git-ignored .env file — never from source code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Bankruptcy Rule Monitor backend.

    Values are loaded from environment variables (case-insensitive) or a
    .env file in the working directory.  Sensitive fields have no default so
    that a missing secret fails loudly at startup rather than silently.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL connection string — must use the psycopg 3 async driver.
    # Example: postgresql+psycopg://brm:brm@localhost:5432/brm
    database_url: str

    # Anthropic API key for LLM-powered change summarization.
    anthropic_api_key: str

    # Shared API key for the review-queue and pull-delivery APIs (X-API-Key header).
    api_key: str


# Module-level singleton — instantiated once; all callers import this object.
settings = Settings()
