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

def _getenv_csv_set(name: str) -> set[str]:
    raw = _getenv(name)
    if raw is None:
        return set()
    parts = [p.strip().lower() for p in raw.split(",")]
    return {p for p in parts if p}


class Settings:
    def __init__(self) -> None:
        self.environment = (_getenv("ENVIRONMENT", "development") or "development").lower()
        self.database_url = _getenv("DATABASE_URL", "sqlite:///./sql_app.db") or "sqlite:///./sql_app.db"
        self.db_auto_create = _getenv_bool("DB_AUTO_CREATE", default=True)
        self.supabase_url = _getenv("SUPABASE_URL") or _getenv("VITE_SUPABASE_URL")
        self.supabase_anon_key = _getenv("SUPABASE_ANON_KEY") or _getenv("VITE_SUPABASE_ANON_KEY")
        self.supabase_jwt_audience = _getenv("SUPABASE_JWT_AUD", "authenticated")
        self.supabase_jwt_issuer = _getenv("SUPABASE_JWT_ISSUER")
        self.basic_auth_enabled = _getenv_bool(
            "BASIC_AUTH_ENABLED",
            default=(self.environment == "production"),
        )
        self.basic_auth_username = _getenv("BASIC_AUTH_USERNAME")
        self.basic_auth_password = _getenv("BASIC_AUTH_PASSWORD")
        self.cors_allow_origins = _getenv("CORS_ALLOW_ORIGINS")
        self.frontend_url = _getenv("FRONTEND_URL", "http://localhost:5173") or "http://localhost:5173"

        self.openrouter_api_key = _getenv("OPENROUTER_API_KEY")
        self.openrouter_model = _getenv("OPENROUTER_MODEL")
        self.openrouter_site_url = _getenv("OPENROUTER_SITE_URL")
        self.openrouter_app_name = _getenv("OPENROUTER_APP_NAME")

        self.llm_api_key = _getenv("LLM_API_KEY") or self.openrouter_api_key or _getenv("PERPLEXITY_API_KEY")
        self.llm_base_url = _getenv("LLM_BASE_URL") or ("https://openrouter.ai/api/v1" if self.openrouter_api_key else None)
        self.llm_model = _getenv("LLM_MODEL") or self.openrouter_model
        self.llm_temperature = float(_getenv("LLM_TEMPERATURE", "0.2") or "0.2")
        self.llm_input_cost_per_m = float(_getenv("LLM_INPUT_COST_PER_M", "0.02") or "0.02")
        self.llm_output_cost_per_m = float(_getenv("LLM_OUTPUT_COST_PER_M", "0.05") or "0.05")

        self.serper_api_key = _getenv("SERPER_API_KEY")
        self.serper_endpoint = _getenv("SERPER_ENDPOINT", "https://google.serper.dev/search") or "https://google.serper.dev/search"
        self.serper_gl = _getenv("SERPER_GL", "us") or "us"
        self.serper_hl = _getenv("SERPER_HL", "en") or "en"
        self.serper_num = int(_getenv("SERPER_NUM", "10") or "10")
        self.serper_qps = int(_getenv("SERPER_QPS", "50") or "50")
        self.serper_cost_per_1k = float(_getenv("SERPER_COST_PER_1K", "1.0") or "1.0")

        self.lemonsqueezy_api_key = _getenv("LEMONSQUEEZY_API_KEY")
        self.lemonsqueezy_store_id = _getenv("LEMONSQUEEZY_STORE_ID")
        self.lemonsqueezy_webhook_secret = _getenv("LEMONSQUEEZY_WEBHOOK_SECRET")
        self.lemonsqueezy_variant_trial = _getenv("LEMONSQUEEZY_VARIANT_TRIAL")
        self.lemonsqueezy_variant_entry = _getenv("LEMONSQUEEZY_VARIANT_ENTRY")
        self.lemonsqueezy_variant_pro = _getenv("LEMONSQUEEZY_VARIANT_PRO")
        self.lemonsqueezy_variant_business = _getenv("LEMONSQUEEZY_VARIANT_BUSINESS")
        self.lemonsqueezy_variant_agency = _getenv("LEMONSQUEEZY_VARIANT_AGENCY")
        self.lemonsqueezy_variant_topup = _getenv("LEMONSQUEEZY_VARIANT_TOPUP")

        self.admin_emails = _getenv_csv_set("ADMIN_EMAILS")

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
