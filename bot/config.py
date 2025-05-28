import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


# Simple function to parse admin IDs
def parse_admin_ids() -> List[int]:
    admin_ids = os.getenv("ADMIN_USER_IDS", "")
    if not admin_ids:
        return []
    try:
        return [int(id.strip()) for id in admin_ids.split(",") if id.strip()]
    except ValueError:
        return []


# Create a simple class instead of using Pydantic
class Settings:
    def __init__(self):
        # Bot settings
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        self.WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
        self.WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

        # API settings
        self.API_URL = os.getenv("API_URL", "http://api:8000")

        # Admin settings
        self.ADMIN_USER_IDS = parse_admin_ids()

        # CryptoCloud settings
        self.CRYPTOCLOUD_API_KEY = os.getenv("CRYPTOCLOUD_API_KEY", "")
        self.CRYPTOCLOUD_SHOP_ID = os.getenv("CRYPTOCLOUD_SHOP_ID", "")
        self.CRYPTOCLOUD_WEBHOOK_URL = os.getenv("CRYPTOCLOUD_WEBHOOK_URL", "")

        # Signal packages
        self.DEFAULT_PACKAGES = [
            {"id": 1, "name": "Basic", "signals_count": 1, "price": 1.0},
            {"id": 2, "name": "Standard", "signals_count": 10, "price": 9.0},
            {"id": 3, "name": "Premium", "signals_count": 30, "price": 25.0}
        ]

        # Payment settings (legacy)
        self.PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")


# Create settings instance
settings = Settings()