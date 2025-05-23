import aiohttp
import logging
import os
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Bot service URL
BOT_SERVICE_URL = os.getenv("BOT_SERVICE_URL", "http://bot:8001")


async def send_message(telegram_id: int, message: str, keyboard: Dict[str, Any] = None):
    """Send a message to a specific user through the bot service."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "telegram_id": telegram_id,
                "message": message
            }
            if keyboard:
                payload["keyboard"] = keyboard

            async with session.post(f"{BOT_SERVICE_URL}/internal/send_message", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to send message: {await response.text()}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


async def send_signal_to_users(signal_id: int, user_ids: List[int]):
    """Send a signal to multiple users through the bot service."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "signal_id": signal_id,
                "user_ids": user_ids
            }
            async with session.post(f"{BOT_SERVICE_URL}/internal/send_signal", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to send signal: {await response.text()}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Error sending signal: {e}")
        return False


async def send_exit_signal_to_users(signal_id: int):
    """Send an exit signal to users who received the entry signal."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "signal_id": signal_id
            }
            async with session.post(f"{BOT_SERVICE_URL}/internal/send_exit_signal", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to send exit signal: {await response.text()}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Error sending exit signal: {e}")
        return False


async def send_daily_summary(date_str: str):
    """Send daily summary to all active users."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "date": date_str
            }
            async with session.post(f"{BOT_SERVICE_URL}/internal/send_daily_summary", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to send daily summary: {await response.text()}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Error sending daily summary: {e}")
        return False