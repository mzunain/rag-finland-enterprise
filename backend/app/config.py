from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/rag"
    model_name: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    auth_required: bool = True
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    auth_users_json: str = (
        '[{"username":"admin","password":"change-admin-password","role":"admin","collections":["*"]},'
        '{"username":"viewer","password":"change-viewer-password","role":"viewer","collections":["HR-docs"]}]'
    )
    max_upload_size_mb: int = Field(default=50, ge=1, le=500)
    default_rate_limit: str = "120/minute"
    auth_rate_limit: str = "20/minute"
    chat_rate_limit: str = "60/minute"
    upload_rate_limit: str = "10/minute"
    pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    pool_recycle_seconds: int = Field(default=1800, ge=30, le=86400)
    ivfflat_lists: int = Field(default=100, ge=1, le=2000)
    health_openai_timeout_seconds: int = Field(default=8, ge=1, le=60)
    api_version_prefix: str = "/v1"
    db_auth_enabled: bool = True
    api_key_prefix: str = "rk_"
    default_user_quota_per_month: int = Field(default=10000, ge=100, le=5_000_000)
    default_api_key_quota_per_month: int = Field(default=5000, ge=100, le=5_000_000)
    oidc_issuer_url: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_claim_username: str = "email"
    oidc_claim_role: str = "role"
    oidc_claim_collections: str = "collections"
    llm_provider: str = "openai"  # openai | local | auto
    embedding_provider: str = "openai"  # openai | local | turkunlp | auto
    data_sovereignty_mode: bool = False
    local_provider_api_key: str = "local-inference"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model_default: str = "llama3.1:8b-instruct-q4_K_M"
    local_llm_model_fi: str = "poro-34b-chat"
    local_embedding_base_url: str = "http://localhost:11434/v1"
    local_embedding_model: str = "nomic-embed-text"
    turkunlp_embedding_url: str = ""
    turkunlp_embedding_api_key: str = ""
    connector_fetch_timeout_seconds: int = Field(default=20, ge=3, le=120)
    connector_max_sources_per_import: int = Field(default=20, ge=1, le=200)
    connector_allowed_domains: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
