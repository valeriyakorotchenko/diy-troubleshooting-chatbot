from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Security: Read from .env, never hardcode defaults here
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str | None = None # Optional for now

    # Model Configuration
    # This allows to switch providers just by changing this string
    DEFAULT_LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"

    # Generation Parameters
    LLM_TEMPERATURE: float = 0.0
    MAX_RETRIES: int = 2

    # Database Configuration
    DATABASE_URL: str

    # Loads from a .env file in the root directory
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Singleton instance
settings = Settings()