from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match the embedding model's output size (bge-small-en-v1.5 = 384).
# If you ever switch models, change this AND re-embed every job.
EMBED_DIM = 384


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CareerPilot AI"
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    max_upload_mb: int = 5
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cors_origins: str = "*"  # comma separated list in production
    agent_max_steps: int = 5
    agent_history_messages: int = 12

settings = Settings()