from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    app_origin: str = "http://localhost:8000"
    secure_cookies: bool = True
    session_hours: int = 12
    webhook_hosts: str = ""


settings = Settings()
