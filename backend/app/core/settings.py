import os


def _getenv(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _getenv_bool(name: str, default: bool = False) -> bool:
    raw = _getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    def __init__(self) -> None:
        self.environment = (_getenv("ENVIRONMENT", "development") or "development").lower()
        self.database_url = _getenv("DATABASE_URL", "sqlite:///./sql_app.db") or "sqlite:///./sql_app.db"
        self.db_auto_create = _getenv_bool("DB_AUTO_CREATE", default=True)
        self.basic_auth_enabled = _getenv_bool(
            "BASIC_AUTH_ENABLED",
            default=(self.environment == "production"),
        )
        self.basic_auth_username = _getenv("BASIC_AUTH_USERNAME")
        self.basic_auth_password = _getenv("BASIC_AUTH_PASSWORD")
        self.cors_allow_origins = _getenv("CORS_ALLOW_ORIGINS")

        self.llm_api_key = _getenv("LLM_API_KEY")
        self.llm_base_url = _getenv("LLM_BASE_URL")
        self.llm_model = _getenv("LLM_MODEL")
        self.llm_temperature = float(_getenv("LLM_TEMPERATURE", "0.2") or "0.2")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def resolved_cors_origins(self) -> list[str]:
        raw = self.cors_allow_origins
        if raw is None:
            return ["http://localhost:5173", "http://localhost:8000"]
        if raw.strip() == "*":
            return ["*"]
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins


settings = Settings()
