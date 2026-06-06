from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_DIR / ".env"), str(_REPO_ROOT_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Navigator API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    database_url: str = Field(default="", alias="DATABASE_URL")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_api_base_url: str = Field(default="", alias="LLM_API_BASE_URL")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
    embedding_model: str = Field(default="text-embedding-3-large", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")

    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")
    max_upload_mb: int = Field(default=20, alias="MAX_UPLOAD_MB")
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    min_relevance_threshold: float = Field(default=0.1, alias="MIN_RELEVANCE_THRESHOLD")
    admin_username: str = Field(default="Level1_Admin", alias="ADMIN_USERNAME")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Prefer checked-in/root .env values over inherited shell env vars.
        return init_settings, dotenv_settings, env_settings, file_secret_settings


settings = Settings()
