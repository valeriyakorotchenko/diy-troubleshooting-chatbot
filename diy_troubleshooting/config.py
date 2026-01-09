from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Security: Never hardcode API keys here; always read them from .env.
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str | None = None

    # Model configuration allows switching providers by changing this string.
    DEFAULT_LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"

    # Generation parameters for LLM calls.
    LLM_TEMPERATURE: float = 0.0
    MAX_RETRIES: int = 2

    # Database connection URL for PostgreSQL.
    DATABASE_URL: str

    # Load settings from a .env file in the root directory.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Singleton instance created at module load time.
settings = Settings()