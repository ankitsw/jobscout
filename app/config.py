from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    api_key: str = "change_me"
    smtp_email: str = ""
    smtp_password: str = ""
    alert_email: str = ""
    hunter_interval_minutes: int = 30
    google_sheet_id: str = ""
    google_credentials_path: str = ""
    langsmith_api_key: str = ""
    tavily_api_key: str = ""
    sentry_dsn : str = ""
    discord_webhook_url: str = ""
    environment: str = "development"
    log_level: str = "INFO"
    ats_greenhouse_boards: str = "gitlab,asana,discord"
    ats_lever_companies: str = "palantir"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        # Managed providers (Render, Heroku, etc.) hand out plain
        # postgres:// / postgresql:// URLs. SQLAlchemy's async engine
        # needs the asyncpg driver spelled out explicitly.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

settings = Settings()