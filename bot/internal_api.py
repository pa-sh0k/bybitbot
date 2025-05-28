from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
import aiohttp
from datetime import datetime

from config import settings
from handlers.signals import (
    format_entry_signal,
    format_partial_close_signal,
    format_exit_signal,
    format_increase_signal
)
from cryptocloud_webhook import handle_cryptocloud_webhook

logger = logging.getLogger(__name__)


# Pydantic models for internal API
class SendSignalRequest(BaseModel):
    signal_id: int
    user_ids: List[int]


class SendExitSignalRequest(BaseModel):
    signal_id: int


class SendDailySummaryRequest(BaseModel):
    date: str


class SendMessageRequest(BaseModel):
    telegram_id: int
    message: str
    keyboard: Dict[str, Any] = None


# Create internal API app
internal_app = FastAPI(title="Bot Internal API")

# Global bot instance (will be set by main.py)
bot_instance = None


def set_bot_instance(bot):
    """Set the bot instance for internal API to use."""
    global bot_instance
    bot_instance = bot


@internal_app.post("/internal/send_signal")
async def send_signal_to_users(request: SendSignalRequest):
    """Send a signal to users based on signal type."""
    try:
        signal_id = request.signal_id
        user_ids = request.user_ids

        # Fetch signal details from API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/signals/{signal_id}") as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch signal: {await response.text()}")
                signal = await response.json()

        logger.info(user_ids)
        logger.info(signal)

        # Format signal message based on action
        if signal['action'].lower() == 'open':
            signal_message = format_entry_signal(signal)
        elif signal['action'].lower() == 'partial_close':
            signal_message = format_partial_close_signal(signal)
        elif signal['action'].lower() == 'close':
            signal_message = format_exit_signal(signal)
        elif signal['action'].lower() == 'increase':
            signal_message = format_increase_signal(signal)
        else:
            signal_message = format_entry_signal(signal)  # Default
        # Send signal to each user
        for user_id in user_ids:
            try:
                # Record signal usage in API (only for entry signals)
                if signal['action'].lower() == 'open':
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                                f"{settings.API_URL}/api/signals/{signal_id}/users/{user_id}"
                        ) as response:
                            if response.status != 200:
                                logger.error(f"Failed to record signal use: {await response.text()}")
                                continue

                # Get user's Telegram ID
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{settings.API_URL}/api/users/by_id/{user_id}") as response:
                        if response.status != 200:
                            logger.error(f"Failed to get user: {await response.text()}")
                            continue
                        user = await response.json()

                # Send message to user
                if bot_instance:
                    await bot_instance.send_message(
                        user["telegram_id"],
                        signal_message,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Error sending signal to user {user_id}: {e}")

        return {"status": "success", "message": f"Signal sent to {len(user_ids)} users"}
    except Exception as e:
        logger.error(f"Error in send_signal_to_users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@internal_app.post("/internal/send_exit_signal")
async def send_exit_signal(request: SendExitSignalRequest):
    """Send exit signal to users who received the entry signal."""
    try:
        signal_id = request.signal_id

        # Fetch signal details from API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/signals/{signal_id}") as response:
                # ↑ THIS CALL WORKS (you have this endpoint)
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch signal: {await response.text()}")
                signal = await response.json()

        # ⚠️ ANOTHER MISSING ENDPOINT CALL ⚠️
        # Get users who received the entry signal
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/signals/{signal_id}/users") as response:
                # ↑ THIS ENDPOINT DOESN'T EXIST EITHER!
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch users: {await response.text()}")
                users = await response.json()

        # Format exit signal message
        exit_message = format_exit_signal(signal)

        # Send exit signal to each user
        for user in users:
            try:
                if bot_instance:
                    await bot_instance.send_message(
                        user["telegram_id"],
                        exit_message,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Error sending exit signal to user {user['id']}: {e}")

        return {"status": "success", "message": f"Exit signal sent to {len(users)} users"}
    except Exception as e:
        logger.error(f"Error in send_exit_signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@internal_app.post("/internal/send_daily_summary")
async def send_daily_summary(request: SendDailySummaryRequest):
    """Send daily summary to all active users."""
    try:
        date_str = request.date

        # Fetch daily summary from API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/daily_summary/{date_str}") as response:
                if response.status != 200:
                    raise HTTPException(status_code=400,
                                        detail=f"Failed to fetch daily summary: {await response.text()}")
                summary = await response.json()

        # Format daily summary message
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        summary_message = f"📅 <b>Итоги дня {date_obj.strftime('%d.%m.%Y')}</b>\n\n"

        for signal in summary["signals"]:
            profit_str = f"+{signal['profit_percentage']:.2f}%" if signal[
                                                                       'profit_percentage'] > 0 else f"{signal['profit_percentage']:.2f}%"
            summary_message += f"<b>Сделка №{signal['signal_number']:05d}</b> {profit_str}\n"

        summary_message += f"\n<b>Общая прибыль:</b> {summary['total_profit']:.1f}%"

        # Get all active users
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_URL}/api/users/active") as response:
                if response.status != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to fetch users: {await response.text()}")
                users = await response.json()

        # Send summary to each user
        for user in users:
            try:
                if bot_instance:
                    await bot_instance.send_message(
                        user["telegram_id"],
                        summary_message,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Error sending daily summary to user {user['id']}: {e}")

        return {"status": "success", "message": f"Daily summary sent to {len(users)} users"}
    except Exception as e:
        logger.error(f"Error in send_daily_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@internal_app.post("/internal/send_message")
async def send_message(request: SendMessageRequest):
    """Send a custom message to a specific user."""
    try:
        if bot_instance:
            await bot_instance.send_message(
                request.telegram_id,
                request.message,
                parse_mode="HTML"
            )
            return {"status": "success", "message": "Message sent"}
        else:
            raise HTTPException(status_code=500, detail="Bot instance not available")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# CryptoCloud webhook endpoint
@internal_app.post("/webhook/cryptocloud")
async def cryptocloud_webhook_endpoint(request: Request):
    """CryptoCloud webhook endpoint for payment notifications"""
    return await handle_cryptocloud_webhook(request)


@internal_app.get("/webhook/cryptocloud/test")
async def test_cryptocloud_webhook():
    """Test endpoint to verify webhook is accessible"""
    return {"status": "ok", "message": "CryptoCloud webhook endpoint is active"}


# Health check for internal API
@internal_app.get("/internal/health")
async def health_check():
    return {"status": "ok", "bot_available": bot_instance is not None}