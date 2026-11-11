import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Dynamically search upward for the .env file
current_dir = Path(__file__).resolve().parent
for parent in current_dir.parents:
    if (parent / ".env").exists():
        ENV_FILE = parent / ".env"
        break
else:
    ENV_FILE = current_dir / ".env"  # Fallback

# Force load the .env file into the system environment
load_dotenv(dotenv_path=ENV_FILE)

class Settings(BaseSettings):
    database_url: str
    whatnot_webhook_secret: str

settings = Settings()