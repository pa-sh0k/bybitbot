import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Bot settings
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

    # API settings
    API_URL: str = os.getenv("API_URL", "http://api:8000")

    # Admin settings
    ADMIN_USER_IDS: list = [int(id) for id in os.getenv("ADMIN_USER_IDS", "").split(",") if id]

    # Signal packages
    DEFAULT_PACKAGES: list = [
        {"id": 1, "name": "Basic", "signals_count": 1, "price": 1.0},
        {"id": 2, "name": "Standard", "signals_count": 10, "price": 9.0},
        {"id": 3, "name": "Premium", "signals_count": 30, "price": 25.0}
    ]

    # Payment settings
    PAYMENT_PROVIDER_TOKEN: str = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

    class Config:
        env_file = ".env"


settings = Settings()