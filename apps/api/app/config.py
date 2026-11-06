from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    whatnot_webhook_secret: str

    class Config:
        env_file = "../../.env"

settings = Settings()