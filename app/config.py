from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Personal Intelligence Monitor"
    database_url: str = "sqlite:///./pim.db"
    ingest_interval_minutes: int = 60
    digest_frequency: str = "daily"
    digest_output_dir: str = "sample_output"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PIM_")


settings = Settings()
