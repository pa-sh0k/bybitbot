import asyncio
import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import sys
import uvicorn
from fastapi import FastAPI

from config import settings
from handlers import start, balance, signals, support
from internal_api import internal_app, set_bot_instance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Global bot instance
bot = None


# Setup bot commands
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="balance", description="Проверить баланс")
    ]

    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


# Main function for setting up the bot
async def main():
    global bot

    # Initialize Bot instance
    bot = Bot(token=settings.BOT_TOKEN)

    # Set bot instance for internal API
    set_bot_instance(bot)

    # Initialize dispatcher with memory storage
    dp = Dispatcher(storage=MemoryStorage())

    # Register all routers
    dp.include_router(start.router)
    dp.include_router(balance.router)
    dp.include_router(signals.router)
    dp.include_router(support.router)

    # Setup commands
    await set_commands(bot)

    # Setup webhook if URL is provided
    if settings.WEBHOOK_URL:
        # Remove webhook first
        await bot.delete_webhook()
        # Set webhook
        await bot.set_webhook(url=settings.WEBHOOK_URL + settings.WEBHOOK_PATH)

        # Create combined app
        app = web.Application()

        # Create webhook handler
        webhook_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot
        )

        # Setup webhook routes
        webhook_handler.register(app, path=settings.WEBHOOK_PATH)

        # Mount FastAPI internal app
        async def fastapi_handler(request):
            # Convert aiohttp request to ASGI scope
            scope = {
                "type": "http",
                "method": request.method,
                "path": request.path_qs,
                "headers": [[k.encode(), v.encode()] for k, v in request.headers.items()],
                "query_string": request.query_string.encode(),
            }

            # Create receive callable
            async def receive():
                body = await request.read()
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }

            # Create send callable
            responses = []

            async def send(message):
                responses.append(message)

            # Call FastAPI app
            await internal_app(scope, receive, send)

            # Convert response
            status = 200
            headers = {}
            body = b""

            for response in responses:
                if response["type"] == "http.response.start":
                    status = response["status"]
                    # Convert ASGI headers (list of byte tuples) to dict of strings
                    asgi_headers = response.get("headers", [])
                    headers = {
                        key.decode() if isinstance(key, bytes) else key:
                            value.decode() if isinstance(value, bytes) else value
                        for key, value in asgi_headers
                    }
                elif response["type"] == "http.response.body":
                    body = response.get("body", b"")

            return web.Response(body=body, status=status, headers=headers)

        # Add internal API routes
        app.router.add_route("POST", "/internal/{path:.*}", fastapi_handler)
        app.router.add_route("GET", "/internal/{path:.*}", fastapi_handler)

        # Setup application
        setup_application(app, dp, bot=bot)

        # Start web server - THIS IS THE PROBLEMATIC LINE
        # web.run_app(app, host="0.0.0.0", port=8001)

        # Use the async version instead:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8001)
        await site.start()

        # Keep the application running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    else:
        # For polling mode, run internal API in a separate task
        async def run_internal_api():
            config = uvicorn.Config(
                internal_app,
                host="0.0.0.0",
                port=8001,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()

        # Start internal API in background
        internal_task = asyncio.create_task(run_internal_api())

        # Start polling
        try:
            await dp.start_polling(bot)
        finally:
            internal_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())