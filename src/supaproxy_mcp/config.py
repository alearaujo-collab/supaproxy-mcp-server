"""Settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supaproxy_base_url: str = "https://localhost:7001"
    supaproxy_api_key: str = ""
    supaproxy_connection_name: str = "DefaultConnection"

    # ── AI / Anthropic ─────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_max_retries: int = 6
    ai_model: str = "claude-sonnet-4-6"
    ai_max_tool_iterations: int = 10
    ai_max_tokens: int = 8192

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
