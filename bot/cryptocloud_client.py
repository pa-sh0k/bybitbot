import aiohttp
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CryptoCloudClient:
    def __init__(self, api_key: str, shop_id: str, webhook_url: Optional[str] = None):
        self.api_key = api_key
        self.shop_id = shop_id
        self.webhook_url = webhook_url
        self.base_url = "https://api.cryptocloud.plus"

    async def create_invoice(
            self,
            amount: float,
            currency: str = "USD",
            order_id: Optional[str] = None,
            email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a payment invoice in CryptoCloud

        Args:
            amount: Payment amount
            currency: Currency code (USD, RUB, EUR, etc.)
            order_id: Optional order identifier for tracking
            email: Optional customer email

        Returns:
            Dictionary with invoice data or error information
        """
        url = f"{self.base_url}/v2/invoice/create"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "amount": amount,
            "shop_id": self.shop_id,
            "currency": currency
        }

        if order_id:
            payload["order_id"] = order_id

        if email:
            payload["email"] = email

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_data = await response.json()

                    if response.status == 200 and response_data.get("status") == "success":
                        logger.info(f"Successfully created invoice: {response_data.get('result', {}).get('uuid')}")
                        return {
                            "success": True,
                            "invoice_id": response_data["result"]["uuid"],
                            "payment_url": response_data["result"]["link"],
                            "amount": response_data["result"]["amount"],
                            "currency": response_data["result"]["currency"],
                            "expires_at": response_data["result"].get("expired_at")
                        }
                    else:
                        logger.error(f"Failed to create invoice: {response_data}")
                        return {
                            "success": False,
                            "error": response_data.get("result", {}).get("message", "Unknown error")
                        }

        except Exception as e:
            logger.error(f"Error creating CryptoCloud invoice: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }

    async def get_invoice_info(self, invoice_id: str) -> Dict[str, Any]:
        """
        Get information about an existing invoice

        Args:
            invoice_id: UUID of the invoice

        Returns:
            Dictionary with invoice information
        """
        url = f"{self.base_url}/v2/invoice/merchant/info"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "uuids": [invoice_id]
        }

        # try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_data = await response.json()

                if response.status == 200 and response_data.get("status") == "success":
                    invoices = response_data.get("result", [])
                    if invoices:
                        invoice = invoices[0]
                        logger.info(f"INVOICE {invoice}")
                        return {
                            "success": True,
                            "invoice_id": invoice["uuid"],
                            "status": invoice["status_invoice"],
                            "amount": invoice["amount"],
                            "amount_crypto": invoice.get("amount_crypto"),
                            "currency": invoice["currency"],
                            "paid_at": invoice.get("date_update"),
                            "order_id": invoice.get("order_id")
                        }

                return {
                    "success": False,
                    "error": "Invoice not found"
                }

        # except Exception as e:
        #     logger.error(f"Error getting invoice info: {e}")
        #     return {
        #         "success": False,
        #         "error": f"Network error: {str(e)}"
        #     }

    def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify webhook signature (if using webhook signatures)
        Note: CryptoCloud uses JWT tokens for webhook verification

        Args:
            payload: Webhook payload
            signature: JWT signature from webhook

        Returns:
            True if signature is valid
        """
        try:
            # For now, we'll do basic validation
            # In production, you should implement JWT token verification
            required_fields = ["status", "invoice_id", "amount_crypto", "currency"]
            return all(field in payload for field in required_fields)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False