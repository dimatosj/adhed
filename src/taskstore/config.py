from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    database_url_sync: str = ""
    api_port: int = 8100
    log_level: str = "info"
    log_format: str = "plain"  # "plain" | "json"
    # Comma-separated list of origins allowed by CORS. Empty = CORS
    # disabled (default; ADHED is API-first and typically doesn't need
    # to be called from browsers).
    cors_origins: str = ""
    # Max request body size in bytes. Rejected at 413 before endpoint
    # logic runs. Default 1 MiB.
    max_body_bytes: int = 1024 * 1024

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
