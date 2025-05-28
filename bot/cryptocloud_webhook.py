from fastapi import Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import aiohttp
import re

from config import settings

logger = logging.getLogger(__name__)


class CryptoCloudWebhook(BaseModel):
    status: str
    invoice_id: str
    amount_crypto: float
    currency: str
    order_id: Optional[str] = None
    token: Optional[str] = None  # JWT token for verification


async def handle_cryptocloud_webhook(request: Request) -> Dict[str, Any]:
    """
    Handle CryptoCloud webhook notifications for successful payments

    This endpoint will be called by CryptoCloud when a payment is completed
    """
    try:
        # Get JSON payload
        payload = await request.json()
        logger.info(f"Received CryptoCloud webhook: {payload}")

        # Validate required fields
        required_fields = ["status", "invoice_id", "amount_crypto", "currency"]
        for field in required_fields:
            if field not in payload:
                logger.error(f"Missing required field in webhook: {field}")
                raise HTTPException(status_code=400, detail=f"Missing field: {field}")

        webhook_data = CryptoCloudWebhook(**payload)

        # Only process successful payments
        if webhook_data.status.lower() != "success":
            logger.info(f"Ignoring webhook with status: {webhook_data.status}")
            return {"message": "Webhook received", "processed": False}

        # Extract user ID from order_id
        # Format: "deposit_{user_telegram_id}_{timestamp}"
        order_id = webhook_data.order_id
        if not order_id or not order_id.startswith("deposit_"):
            logger.error(f"Invalid order_id format: {order_id}")
            raise HTTPException(status_code=400, detail="Invalid order_id format")

        # Parse user_id from order_id
        try:
            parts = order_id.split("_")
            if len(parts) < 3:
                raise ValueError("Invalid order_id format")
            user_telegram_id = int(parts[1])
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse user_id from order_id {order_id}: {e}")
            raise HTTPException(status_code=400, detail="Invalid order_id format")

        # Convert crypto amount to USDT (assuming 1:1 for USDT payments)
        # In a real system, you might need currency conversion
        usdt_amount = float(webhook_data.amount_crypto)

        # For other cryptocurrencies, you'd need to convert to USDT equivalent
        # For now, we'll assume the payment was made in USDT or equivalent

        logger.info(f"Processing payment: {usdt_amount} USDT for user {user_telegram_id}")

        # Add USDT balance to user account
        try:
            async with aiohttp.ClientSession() as session:
                balance_update = {"usdt_amount": usdt_amount}
                async with session.post(
                        f"{settings.API_URL}/api/users/{user_telegram_id}/add_usdt_balance",
                        json=balance_update
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Successfully added {usdt_amount} USDT to user {user_telegram_id}")

                        # Send success notification to user
                        await send_payment_notification(user_telegram_id, usdt_amount, webhook_data.invoice_id)

                        return {
                            "message": "Payment processed successfully",
                            "processed": True,
                            "user_id": user_telegram_id,
                            "amount": usdt_amount
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to add balance: {error_text}")
                        raise HTTPException(status_code=500, detail="Failed to add balance")

        except Exception as e:
            logger.error(f"Error updating user balance: {e}")
            raise HTTPException(status_code=500, detail="Failed to process payment")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing CryptoCloud webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def send_payment_notification(user_telegram_id: int, amount: float, invoice_id: str):
    """Send notification to user about successful payment"""
    try:
        notification_text = (
            f"✅ <b>Платеж подтвержден!</b>\n\n"
            f"💰 <b>Зачислено:</b> {amount:.2f} USDT\n"
            f"🆔 <b>ID транзакции:</b> <code>{invoice_id}</code>\n\n"
            f"Средства поступили на ваш баланс."
        )

        # Send notification via bot API
        async with aiohttp.ClientSession() as session:
            notification_payload = {
                "telegram_id": user_telegram_id,
                "message": notification_text
            }
            async with session.post(
                    f"{settings.API_URL}/api/bot/send_message",
                    json=notification_payload
            ) as response:
                if response.status == 200:
                    logger.info(f"Payment notification sent to user {user_telegram_id}")
                else:
                    logger.error(f"Failed to send notification: {await response.text()}")

    except Exception as e:
        logger.error(f"Error sending payment notification: {e}")


# Add this to internal_api.py
def add_cryptocloud_webhook_endpoint(app):
    """Add CryptoCloud webhook endpoint to the FastAPI app"""

    @app.post("/webhook/cryptocloud")
    async def cryptocloud_webhook_endpoint(request: Request):
        """CryptoCloud webhook endpoint"""
        return await handle_cryptocloud_webhook(request)

    @app.get("/webhook/cryptocloud/test")
    async def test_cryptocloud_webhook():
        """Test endpoint to verify webhook is accessible"""
        return {"status": "ok", "message": "CryptoCloud webhook endpoint is active"}