from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    service_name: str = "mithu-ai"
    port: int = 8100
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    mithu_mongodb_uri: str = ""
    mithu_database_name: str = "educonnect_mithu"
    mithu_store_conversations: bool = True
    identity_issuer: str = "educonnect-pro"
    identity_audience: str = "mithu-ai"
    identity_public_key_pem: str = ""
    educonnect_api_enabled: bool = False
    educonnect_internal_api_url: str = ""
    educonnect_service_token: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_server_location: str = "in-residency"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
