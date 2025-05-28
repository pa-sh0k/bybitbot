import asyncio
import aiohttp
import logging
import sys
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/daily_stats.log")
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_URL = os.getenv("API_URL", "http://api:8000")
BOT_SERVICE_URL = os.getenv("BOT_SERVICE_URL", "http://bot:8001")
RATE_LIMIT_DELAY = float(os.getenv("TELEGRAM_RATE_LIMIT", "0.1"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))


async def get_daily_summary(date_str: str) -> Dict[str, Any]:
    """Get daily summary from API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/api/daily_summary/{date_str}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get daily summary: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error getting daily summary: {e}")
        return None


async def get_all_users() -> List[Dict[str, Any]]:
    """Get ALL users from API (regardless of balance, activity, or signals)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/api/users/all") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get all users: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []


def format_statistics_message(summary: Dict[str, Any]) -> str:
    """Format the daily statistics message."""
    today_text = "📅 <b>Итоги дня:</b>\n"

    if summary and summary.get('signals'):
        for signal in summary['signals']:
            profit = signal.get('profit_percentage', 0)
            profit_str = f"+{profit:.1f}%" if profit > 0 else f"{profit:.1f}%"
            profit_emoji = "🟢" if profit > 0 else "🔴"
            today_text += f"Сделка №{signal['signal_number']:05d}: {profit_emoji} {profit_str}\n"

        total_profit = summary.get('total_profit', 0)
        total_profit_str = f"+{total_profit:.1f}%" if total_profit > 0 else f"{total_profit:.1f}%"
        today_text += f"\n<b>Общая прибыль:</b> {total_profit_str}"
    else:
        today_text += "Сигналов пока не было"

    return today_text


async def send_message_with_retry(session: aiohttp.ClientSession, telegram_id: int, message: str) -> bool:
    """Send message to user with retry logic and rate limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            payload = {
                "telegram_id": telegram_id,
                "message": message
            }

            async with session.post(
                    f"{BOT_SERVICE_URL}/internal/send_message",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    logger.debug(f"Message sent successfully to user {telegram_id}")
                    return True
                elif response.status == 429:  # Rate limit
                    logger.warning(f"Rate limited for user {telegram_id}, waiting...")
                    await asyncio.sleep(RETRY_DELAY * 2)
                    continue
                else:
                    logger.error(f"Failed to send message to user {telegram_id}: {response.status}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout sending message to user {telegram_id}, attempt {attempt + 1}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue
        except Exception as e:
            logger.error(f"Error sending message to user {telegram_id}: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                continue

    logger.error(f"Failed to send message to user {telegram_id} after {MAX_RETRIES} attempts")
    return False


async def send_daily_statistics():
    """Main function to send daily statistics to all users."""
    logger.info("Starting daily statistics broadcast...")

    # Calculate today's date in UTC+3
    utc_plus_3_offset = 3 * 60 * 60
    now_utc = datetime.utcnow()
    now_utc3 = now_utc + timedelta(seconds=utc_plus_3_offset)
    today_utc3 = now_utc3.date()
    today_str = today_utc3.strftime("%Y-%m-%d")

    logger.info(f"Getting daily summary for {today_str}")

    # Get daily summary
    summary = await get_daily_summary(today_str)
    if not summary:
        logger.error("Could not get daily summary, aborting broadcast")
        return

    # Check if there are any signals
    if not summary.get('signals') or len(summary['signals']) == 0:
        logger.info("No signals for today, skipping broadcast")
        return

    # Format the message
    message = format_statistics_message(summary)
    logger.info(f"Formatted message: {message[:100]}...")

    # Get ALL users (regardless of balance or activity)
    users = await get_all_users()
    if not users:
        logger.error("Could not get users, aborting broadcast")
        return

    logger.info(f"Found {len(users)} total users")

    # Send messages to all users with rate limiting
    success_count = 0
    failed_count = 0

    async with aiohttp.ClientSession() as session:
        for i, user in enumerate(users):
            telegram_id = user['telegram_id']

            logger.info(f"Sending message to user {telegram_id} ({i + 1}/{len(users)})")

            success = await send_message_with_retry(session, telegram_id, message)

            if success:
                success_count += 1
            else:
                failed_count += 1

            # Rate limiting: wait between messages
            if i < len(users) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY)

            # Progress logging every 10 users
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(users)} messages sent")

    logger.info(f"Daily statistics broadcast completed: {success_count} sent, {failed_count} failed")


async def main():
    """Main entry point."""
    try:
        await send_daily_statistics()
        logger.info("Daily statistics script completed successfully")
    except Exception as e:
        logger.error(f"Daily statistics script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())