import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiohttp.web_app import Application

from config import settings
from handlers import start, balance, signals, admin
from internal_api import internal_app, set_bot_instance
from cryptocloud_webhook import handle_cryptocloud_webhook, set_bot_instance_for_webhook

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# Include routers
dp.include_router(start.router)
dp.include_router(balance.router)
dp.include_router(signals.router)
dp.include_router(admin.router)


async def on_startup():
    """Called when the bot starts up."""
    logger.info("Bot is starting up...")
    # Set webhook URL if provided
    if settings.WEBHOOK_URL:
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}",
            allowed_updates=dp.resolve_used_update_types()
        )
        logger.info(f"Webhook set to {settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}")


async def on_shutdown():
    """Called when the bot shuts down."""
    logger.info("Bot is shutting down...")
    await bot.session.close()


def create_app() -> Application:
    """Create and configure the aiohttp application."""

    # Create main aiohttp app
    app = web.Application()

    # Set up webhook handler for Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)

    # Add CryptoCloud webhook endpoint
    async def cryptocloud_webhook_handler(request):
        """Handle CryptoCloud webhook"""
        try:
            result = await handle_cryptocloud_webhook(request)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error in CryptoCloud webhook: {e}")
            return web.json_response(
                {"error": "Internal server error"},
                status=500
            )

    # Add CryptoCloud webhook route
    app.router.add_post('/webhook/cryptocloud', cryptocloud_webhook_handler)

    # Add test endpoint for CryptoCloud webhook
    async def test_cryptocloud_webhook(request):
        return web.json_response({
            "status": "ok",
            "message": "CryptoCloud webhook endpoint is active"
        })

    app.router.add_get('/webhook/cryptocloud/test', test_cryptocloud_webhook)

    # Mount internal API as a sub-application
    app.add_subapp('/internal/', internal_app)

    # Set bot instance for internal API and webhook
    set_bot_instance(bot)
    set_bot_instance_for_webhook(bot)

    # Add startup and shutdown handlers
    app.on_startup.append(lambda app: asyncio.create_task(on_startup()))
    app.on_shutdown.append(lambda app: asyncio.create_task(on_shutdown()))

    return app


async def main():
    """Main function to run the bot."""
    if settings.WEBHOOK_URL:
        # Webhook mode
        app = create_app()

        # Configure the application
        setup_application(app, dp, bot=bot)

        logger.info("Starting webhook server...")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8001)
        await site.start()

        logger.info("Webhook server started on port 8001")

        # Keep the server running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        finally:
            await runner.cleanup()
    else:
        # Polling mode
        logger.info("Starting bot in polling mode...")
        await on_startup()
        try:
            await dp.start_polling(bot)
        finally:
            await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())